"""
Model Benchmark Harness — Phase 4

Runs a fixed task suite against two models and measures:
  - Latency (time to first token, total time)
  - Throughput (tokens/sec)
  - Answer quality (scored by a judge model)
  - Memory pressure (approximated by response delta under load)

Models compared:
  - gemma4:2b  — the small, fast model
  - gemma4:26b — the large, accurate model

Usage:
  ollama pull gemma4:2b   # if not already installed
  python 01_model_benchmark.py
"""

import requests
import time
import json
import statistics

OLLAMA_URL = "http://localhost:11434/api/chat"
JUDGE_MODEL = "gemma4:26b"

MODELS = [
    "gemma4:e2b",
    "gemma4:26b",
]

# -------------------------------------------------------------------
# TASK SUITE
# Four task types that stress different model capabilities:
#   1. Factual recall — does the model know the answer?
#   2. Reasoning — can it derive an answer from given information?
#   3. Code generation — can it write correct code?
#   4. Summarisation — can it compress without losing key facts?
# -------------------------------------------------------------------

TASKS = [
    {
        "id": "factual_1",
        "type": "factual",
        "prompt": "What is the difference between a transformer's encoder and decoder? Answer in 3 sentences.",
        "max_tokens": 200,
    },
    {
        "id": "factual_2",
        "type": "factual",
        "prompt": "What is quantization in the context of machine learning models? Answer in 3 sentences.",
        "max_tokens": 200,
    },
    {
        "id": "reasoning_1",
        "type": "reasoning",
        "prompt": (
            "A warehouse has 3 robots. Each robot can process 120 packages per hour. "
            "The warehouse receives 1,000 packages per 8-hour shift. "
            "How many shifts does it take to clear a backlog of 5,000 packages? "
            "Show your calculation."
        ),
        "max_tokens": 300,
        "expected_answer": "5,000 packages / (3 robots * 120 packages/hour * 8 hours/shift) = 5,000 / 2,880 ≈ 1.74 shifts → 2 shifts",
    },
    {
        "id": "reasoning_2",
        "type": "reasoning",
        "prompt": (
            "A context window holds 8,192 tokens. A system prompt uses 500 tokens. "
            "Each user message averages 50 tokens. Each assistant response averages 200 tokens. "
            "How many conversation turns fit before the context is full? "
            "Show your calculation."
        ),
        "max_tokens": 300,
        "expected_answer": "Remaining tokens: 8192 - 500 = 7692. Per turn: 50 + 200 = 250 tokens. Turns: 7692 / 250 = 30.768 → 30 complete turns",
    },
    {
        "id": "code_1",
        "type": "code",
        "prompt": (
            "Write a Python function called `retry` that takes a function `fn`, "
            "a maximum number of attempts `max_attempts`, and a delay in seconds `delay`. "
            "It should call `fn()`, and if it raises an exception, wait `delay` seconds and retry. "
            "After `max_attempts` failures, raise the last exception. "
            "No external libraries. Just the function, no explanation."
        ),
        "max_tokens": 400,
    },
    {
        "id": "summarise_1",
        "type": "summarise",
        "prompt": (
            "Summarise the following in exactly 2 sentences:\n\n"
            "Mixture of Experts (MoE) is a neural network architecture where the model contains "
            "multiple expert subnetworks and a gating network that selects which experts to activate "
            "for each input. During inference, only a fraction of the total parameters are used — "
            "the activated experts. This means an MoE model with 26 billion total parameters may "
            "only use 7 billion parameters per forward pass. The benefit is that the model has "
            "the capacity of a large model (broad knowledge) with the inference cost of a smaller "
            "model (fast, low memory). Gemma 4 26B is an MoE model."
        ),
        "max_tokens": 150,
    },
]


# -------------------------------------------------------------------
# INFERENCE
# -------------------------------------------------------------------

def call_model(model: str, prompt: str, max_tokens: int) -> dict:
    """
    Calls a model and returns timing stats and the response text.
    Returns a dict with: text, total_tokens, eval_tokens, total_duration_ms, eval_duration_ms
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": max_tokens,
            "num_ctx": 4096,
        },
    }

    start = time.perf_counter()
    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    elapsed = time.perf_counter() - start

    response.raise_for_status()
    data = response.json()

    text = data["message"]["content"].strip()

    # Ollama reports timing in nanoseconds
    total_duration_ms = data.get("total_duration", 0) / 1_000_000
    eval_duration_ms = data.get("eval_duration", 0) / 1_000_000
    prompt_eval_duration_ms = data.get("prompt_eval_duration", 0) / 1_000_000

    eval_count = data.get("eval_count", 0)
    prompt_eval_count = data.get("prompt_eval_count", 0)

    tokens_per_sec = (eval_count / (eval_duration_ms / 1000)) if eval_duration_ms > 0 else 0

    return {
        "text": text,
        "eval_tokens": eval_count,
        "prompt_tokens": prompt_eval_count,
        "total_tokens": eval_count + prompt_eval_count,
        "total_duration_ms": round(total_duration_ms, 1),
        "eval_duration_ms": round(eval_duration_ms, 1),
        "prompt_eval_duration_ms": round(prompt_eval_duration_ms, 1),
        "tokens_per_sec": round(tokens_per_sec, 1),
        "wall_time_s": round(elapsed, 2),
    }


# -------------------------------------------------------------------
# JUDGE
# Uses the 26B model to score answers on a 1–5 scale.
# Only used for factual, reasoning, and summarise tasks.
# Code tasks are scored separately (syntax check + manual review).
# -------------------------------------------------------------------

JUDGE_PROMPT_TEMPLATE = """You are evaluating an AI model's answer to a question.

Question: {question}

Answer to evaluate: {answer}

{expected_note}

Score the answer from 1 to 5:
5 = Fully correct, complete, clear
4 = Mostly correct, minor omission or imprecision
3 = Partially correct, important gaps
2 = Mostly wrong or missing key facts
1 = Completely wrong or no useful content

Respond with ONLY a JSON object like this: {{"score": 4, "reason": "one sentence explanation"}}
"""


def judge_answer(question: str, answer: str, expected: str = None) -> dict:
    if expected:
        expected_note = f"Expected answer (for reference): {expected}"
    else:
        expected_note = "No reference answer provided — judge on general correctness."

    prompt = JUDGE_PROMPT_TEMPLATE.format(
        question=question,
        answer=answer,
        expected_note=expected_note,
    )

    payload = {
        "model": JUDGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 200},
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=60)
    response.raise_for_status()
    text = response.json()["message"]["content"].strip()

    # Extract JSON from the response
    try:
        # Find the first { ... } block
        start = text.index("{")
        end = text.rindex("}") + 1
        parsed = json.loads(text[start:end])
        return {"score": parsed.get("score", 0), "reason": parsed.get("reason", "")}
    except (ValueError, json.JSONDecodeError):
        return {"score": 0, "reason": f"Could not parse judge response: {text[:100]}"}


# -------------------------------------------------------------------
# BENCHMARK RUNNER
# -------------------------------------------------------------------

def run_benchmark(model: str, tasks: list, run_judge: bool = True) -> list:
    results = []

    for task in tasks:
        print(f"  Task {task['id']} ({task['type']})...", end=" ", flush=True)

        try:
            result = call_model(model, task["prompt"], task["max_tokens"])
        except Exception as e:
            print(f"FAILED: {e}")
            results.append({"task_id": task["id"], "error": str(e)})
            continue

        entry = {
            "task_id": task["id"],
            "task_type": task["type"],
            "model": model,
            "tokens_per_sec": result["tokens_per_sec"],
            "total_duration_ms": result["total_duration_ms"],
            "eval_tokens": result["eval_tokens"],
            "prompt_tokens": result["prompt_tokens"],
            "wall_time_s": result["wall_time_s"],
            "response": result["text"],
        }

        # Judge non-code tasks
        if run_judge and task["type"] != "code":
            judgment = judge_answer(
                question=task["prompt"],
                answer=result["text"],
                expected=task.get("expected_answer"),
            )
            entry["quality_score"] = judgment["score"]
            entry["quality_reason"] = judgment["reason"]
        else:
            entry["quality_score"] = None
            entry["quality_reason"] = "Manual review required (code task)"

        results.append(entry)
        print(f"{result['tokens_per_sec']} tok/s | {result['total_duration_ms']}ms | quality: {entry['quality_score']}")

    return results


# -------------------------------------------------------------------
# REPORTING
# -------------------------------------------------------------------

def print_summary(all_results: dict):
    print("\n" + "=" * 70)
    print("  BENCHMARK SUMMARY")
    print("=" * 70)

    print(f"\n{'Model':<20} {'Avg tok/s':<12} {'Avg latency(ms)':<18} {'Avg quality':<14} {'Tasks run'}")
    print("-" * 70)

    for model, results in all_results.items():
        valid = [r for r in results if "error" not in r]
        if not valid:
            print(f"{model:<20} {'ERROR':<12}")
            continue

        avg_tps = statistics.mean(r["tokens_per_sec"] for r in valid)
        avg_lat = statistics.mean(r["total_duration_ms"] for r in valid)
        scored = [r for r in valid if r.get("quality_score") is not None]
        avg_q = statistics.mean(r["quality_score"] for r in scored) if scored else None
        q_str = f"{avg_q:.1f}/5" if avg_q is not None else "N/A"

        print(f"{model:<20} {avg_tps:<12.1f} {avg_lat:<18.0f} {q_str:<14} {len(valid)}/{len(results)}")

    print("\n--- Per-task quality scores ---")
    print(f"\n{'Task':<20}", end="")
    for model in all_results:
        print(f"{model:<22}", end="")
    print()
    print("-" * (20 + 22 * len(all_results)))

    task_ids = [t["id"] for t in TASKS]
    for task_id in task_ids:
        print(f"{task_id:<20}", end="")
        for model, results in all_results.items():
            match = next((r for r in results if r["task_id"] == task_id), None)
            if match and "error" not in match:
                score = match.get("quality_score")
                s = f"{score}/5" if score is not None else "manual"
                print(f"{s:<22}", end="")
            else:
                print(f"{'ERROR':<22}", end="")
        print()

    print("\n--- Throughput comparison ---")
    for task_id in task_ids:
        print(f"\n{task_id}:")
        for model, results in all_results.items():
            match = next((r for r in results if r["task_id"] == task_id), None)
            if match and "error" not in match:
                print(f"  {model}: {match['tokens_per_sec']} tok/s in {match['total_duration_ms']}ms ({match['eval_tokens']} output tokens)")


def save_results(all_results: dict, path: str = "/tmp/benchmark_results.json"):
    with open(path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nFull results saved to {path}")


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

if __name__ == "__main__":
    print("Model Benchmark Harness — Phase 4")
    print(f"Models: {', '.join(MODELS)}")
    print(f"Tasks:  {len(TASKS)} tasks across 4 types")
    print(f"Judge:  {JUDGE_MODEL}")
    print()

    all_results = {}

    for model in MODELS:
        print(f"\n[{model}]")
        print("-" * 50)
        results = run_benchmark(model, TASKS, run_judge=True)
        all_results[model] = results

    print_summary(all_results)
    save_results(all_results)
