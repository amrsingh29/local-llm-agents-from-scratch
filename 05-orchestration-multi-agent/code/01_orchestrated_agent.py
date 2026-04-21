"""
Orchestrated Multi-Agent System — Phase 5

Architecture:
  Gemma 4 26B (orchestrator) — decomposes the task, synthesises final output
  Gemma 4 E2B / 26B (workers) — execute sub-tasks locally, routed by task type

Flow:
  1. User submits a complex, multi-part task
  2. Gemma 26B decomposes it into typed, sequenced sub-tasks (JSON)
  3. Each sub-task is routed to E2B (factual/summarise) or 26B (reasoning/code)
  4. Workers execute sub-tasks; results stored in shared state
  5. Dependent sub-tasks receive prior results as context
  6. Gemma 26B synthesises all worker outputs into a final response

Fully local — no cloud API required.
"""

import json
import time
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"

ORCHESTRATOR_MODEL = "gemma4:26b"

LOCAL_ROUTING = {
    "factual":   "gemma4:e2b",
    "summarise": "gemma4:e2b",
    "classify":  "gemma4:e2b",
    "reasoning": "gemma4:26b",
    "code":      "gemma4:26b",
}

# -------------------------------------------------------------------
# OLLAMA CALL — shared by orchestrator and workers
# -------------------------------------------------------------------

def call_ollama(model: str, prompt: str, max_tokens: int = 1500) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": max_tokens,
            "num_ctx": 8192,
        },
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=180)
    response.raise_for_status()
    return response.json()["message"]["content"].strip()


# -------------------------------------------------------------------
# ORCHESTRATOR — Gemma 26B
# -------------------------------------------------------------------

DECOMPOSE_PROMPT = """You are a task orchestrator. Break the user's request into atomic sub-tasks
that can be executed by worker agents.

Return ONLY a JSON array. No explanation, no markdown fences, no code block. Raw JSON only.

Each sub-task must have:
  - id: integer starting at 1
  - task: clear, self-contained instruction for the worker
  - type: one of "factual" | "summarise" | "reasoning" | "code" | "classify"
  - depends_on: list of task IDs this task must wait for (empty list if none)
  - output_format: the exact format the worker should return (e.g. "plain text", "Python code only")

Rules:
  - Keep sub-tasks narrow — one clear action each
  - Mark dependencies explicitly — a task that needs a prior result must list it in depends_on
  - Do not create more than 6 sub-tasks

User request:
{user_request}"""


SYNTHESISE_PROMPT = """You are writing the final response to a user's request.

The request was decomposed into sub-tasks and each was handled by a worker.
Use the worker results below to write a single, coherent, well-structured response.

Original request:
{user_request}

Worker results:
{worker_results}

Write the final response now. Be clear and direct."""


def decompose_task(user_request: str, verbose: bool = True) -> list[dict]:
    """Uses Gemma 26B to decompose the user request into sub-tasks."""
    if verbose:
        print(f"  Orchestrator: {ORCHESTRATOR_MODEL}")

    raw = call_ollama(
        ORCHESTRATOR_MODEL,
        DECOMPOSE_PROMPT.format(user_request=user_request),
        max_tokens=1200,
    )

    # Strip any accidental markdown fences Gemma may add
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    return json.loads(cleaned)


def synthesise(user_request: str, shared_state: dict, verbose: bool = True) -> str:
    """Uses Gemma 26B to synthesise worker outputs into a final response."""
    results_text = "\n\n".join(
        f"Sub-task {tid}: {r['output']}" if r["status"] == "success"
        else f"Sub-task {tid}: FAILED — {r.get('error', 'unknown error')}"
        for tid, r in sorted(shared_state.items())
    )

    return call_ollama(
        ORCHESTRATOR_MODEL,
        SYNTHESISE_PROMPT.format(
            user_request=user_request,
            worker_results=results_text,
        ),
        max_tokens=2000,
    )


# -------------------------------------------------------------------
# WORKER — Gemma E2B or 26B depending on task type
# -------------------------------------------------------------------

def build_worker_prompt(sub_task: dict, context: str = "") -> str:
    base = sub_task["task"]
    fmt  = sub_task.get("output_format", "plain text")
    if context:
        return f"{base}\n\nContext from previous steps:\n{context}\n\nRespond in: {fmt}"
    return f"{base}\n\nRespond in: {fmt}"


def run_worker(sub_task: dict, context: str = "", verbose: bool = True) -> dict:
    """Executes a single sub-task on the appropriate local model."""
    task_type = sub_task.get("type", "factual")
    model     = LOCAL_ROUTING.get(task_type, "gemma4:26b")
    prompt    = build_worker_prompt(sub_task, context)

    if verbose:
        print(f"    Model : {model}")
        print(f"    Task  : {sub_task['task'][:80]}{'...' if len(sub_task['task']) > 80 else ''}")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 800,
            "num_ctx": 8192,
        },
    }

    t0 = time.perf_counter()
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=180)
        response.raise_for_status()
        data       = response.json()
        output     = data["message"]["content"].strip()
        duration   = round((time.perf_counter() - t0) * 1000, 1)
        eval_count = data.get("eval_count", 0)
        eval_ms    = data.get("eval_duration", 0) / 1_000_000
        tps        = round(eval_count / (eval_ms / 1000), 1) if eval_ms > 0 else 0.0

        if verbose:
            print(f"    Result: {output[:120]}{'...' if len(output) > 120 else ''}")
            print(f"    Stats : {duration}ms | {tps} tok/s | {eval_count} tokens")

        return {
            "id":          sub_task["id"],
            "status":      "success",
            "output":      output,
            "model":       model,
            "tokens":      eval_count,
            "duration_ms": duration,
            "tps":         tps,
        }

    except Exception as e:
        duration = round((time.perf_counter() - t0) * 1000, 1)
        if verbose:
            print(f"    ERROR : {e}")
        return {
            "id":          sub_task["id"],
            "status":      "error",
            "error":       str(e),
            "model":       model,
            "duration_ms": duration,
        }


# -------------------------------------------------------------------
# EXECUTION ENGINE — resolves dependencies, runs sub-tasks in order
# -------------------------------------------------------------------

def build_context(sub_task: dict, shared_state: dict) -> str:
    """Assembles context from prior worker outputs for dependent tasks."""
    dep_ids = sub_task.get("depends_on", [])
    if not dep_ids:
        return ""
    parts = [
        f"[Task {dep_id} output]\n{shared_state[dep_id]['output']}"
        for dep_id in dep_ids
        if dep_id in shared_state and shared_state[dep_id]["status"] == "success"
    ]
    return "\n\n".join(parts)


def execute_plan(sub_tasks: list[dict], verbose: bool = True) -> dict:
    """Executes all sub-tasks respecting dependency order."""
    shared_state  = {}
    pending       = {t["id"]: t for t in sub_tasks}
    completed_ids = set()

    while pending:
        ready = [
            t for t in pending.values()
            if all(dep in completed_ids for dep in t.get("depends_on", []))
        ]

        if not ready:
            for fid in list(pending.keys()):
                shared_state[fid] = {
                    "id": fid, "status": "error",
                    "error": "Unresolvable dependency"
                }
            break

        for task in ready:
            if verbose:
                print(f"\n  [Sub-task {task['id']} — {task['type']}]")

            context = build_context(task, shared_state)
            result  = run_worker(task, context=context, verbose=verbose)
            shared_state[task["id"]] = result
            completed_ids.add(task["id"])
            del pending[task["id"]]

    return shared_state


# -------------------------------------------------------------------
# MAIN PIPELINE
# -------------------------------------------------------------------

def run(user_request: str, verbose: bool = True) -> str:
    if verbose:
        print("\n" + "=" * 60)
        print("  STEP 1 — Decompose")
        print("=" * 60)

    sub_tasks = decompose_task(user_request, verbose=verbose)

    if verbose:
        print(f"\n  {len(sub_tasks)} sub-tasks:\n")
        for t in sub_tasks:
            deps    = t.get("depends_on", [])
            dep_str = f" [after: {deps}]" if deps else ""
            print(f"  {t['id']}. [{t['type']}]{dep_str} {t['task'][:70]}...")

        print("\n" + "=" * 60)
        print("  STEP 2 — Execute workers")
        print("=" * 60)

    shared_state = execute_plan(sub_tasks, verbose=verbose)

    if verbose:
        print("\n" + "=" * 60)
        print("  STEP 3 — Synthesise")
        print("=" * 60 + "\n")

    final = synthesise(user_request, shared_state, verbose=verbose)

    if verbose:
        print(final)
        print("\n" + "=" * 60)

        total_tokens = sum(
            r.get("tokens", 0) for r in shared_state.values() if r["status"] == "success"
        )
        successful = sum(1 for r in shared_state.values() if r["status"] == "success")
        print(f"\n  Sub-tasks completed : {successful}/{len(sub_tasks)}")
        print(f"  Total worker tokens : {total_tokens}")
        print(f"  All inference       : local (no API cost)")
        print("=" * 60 + "\n")

    return final


# -------------------------------------------------------------------
# DEMO
# -------------------------------------------------------------------

DEMO_REQUEST = (
    "I'm learning about transformer models. Can you: "
    "1) Explain what the attention mechanism is in simple terms, "
    "2) Compare self-attention vs cross-attention, "
    "3) Give me a Python code snippet showing a minimal dot-product attention calculation, "
    "and 4) Summarise when I would use an encoder-only vs decoder-only vs encoder-decoder architecture."
)

if __name__ == "__main__":
    print("Orchestrated Multi-Agent System — Phase 5")
    print(f"Orchestrator : {ORCHESTRATOR_MODEL}")
    print(f"Workers      : E2B (factual/summarise) | 26B (reasoning/code)")
    print(f"\nRequest: {DEMO_REQUEST[:100]}...")

    run(DEMO_REQUEST, verbose=True)
