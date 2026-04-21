"""
Domain Benchmark Harness — Phase 6

Runs a 10-question benchmark covering LLM and agent concepts.
Each question is answered by the model under test, then scored
by the LLM judge (Gemma 26B).

Produces:
  - Per-question scores with judge reasoning
  - Category breakdown (avg score per topic area)
  - Pass/fail against a quality gate (default: avg >= 4.0)
  - Full results saved to /tmp/benchmark_report.json

Usage:
  python 02_benchmark_harness.py
"""

import json
import time
import sys
import importlib
import requests
from pathlib import Path

# Load judge from numeric-prefixed file
_judge_path = Path(__file__).parent / "01_llm_judge.py"
_spec = importlib.util.spec_from_file_location("llm_judge", _judge_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
judge = _module.judge

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_UNDER_TEST = "gemma4:26b"
QUALITY_GATE     = 4.0  # minimum acceptable average score

# -------------------------------------------------------------------
# BENCHMARK — 10 domain-specific questions
# Written before running the model (see note 03)
# -------------------------------------------------------------------

BENCHMARK = [
    # --- Fundamentals ---
    {
        "id": "fund_01",
        "category": "fundamentals",
        "difficulty": "easy",
        "question": "What is a token in the context of large language models, and why does the number of tokens matter?",
        "reference": (
            "A token is a chunk of text — roughly 3–4 characters for English prose. "
            "LLMs process and generate text in tokens, not characters or words. "
            "Token count matters because it determines cost (billed per token by cloud APIs), "
            "context window usage (the model can only see a fixed number of tokens at once), "
            "and throughput (tokens per second is the speed metric)."
        ),
    },
    {
        "id": "fund_02",
        "category": "fundamentals",
        "difficulty": "medium",
        "question": (
            "Explain the 'lost in the middle' problem in LLMs. "
            "When does it occur and how can it be mitigated?"
        ),
        "reference": (
            "Lost in the middle is the phenomenon where LLMs give less attention to information "
            "placed in the middle of a long context window compared to the beginning and end. "
            "It occurs when the relevant signal is buried in a large amount of surrounding text. "
            "Mitigations include: placing the most important information at the start or end of "
            "the context, using RAG to retrieve only the most relevant chunks, and reducing context "
            "size so the signal-to-noise ratio is higher."
        ),
    },
    {
        "id": "fund_03",
        "category": "fundamentals",
        "difficulty": "easy",
        "question": "What does temperature control in an LLM and what happens at temperature=0 vs temperature=1?",
        "reference": (
            "Temperature controls the randomness of the model's output by scaling the probability "
            "distribution over possible next tokens before sampling. "
            "At temperature=0, the model always picks the highest-probability token — output is "
            "deterministic and consistent but less creative. "
            "At temperature=1, the model samples from the unmodified distribution — output is more "
            "varied and creative but less predictable. "
            "Values above 1 amplify randomness further."
        ),
    },
    # --- Agent Architecture ---
    {
        "id": "agent_01",
        "category": "agent_architecture",
        "difficulty": "medium",
        "question": (
            "Describe the ReAct pattern. What problem does it solve and "
            "what are the four components of each step in the loop?"
        ),
        "reference": (
            "ReAct (Reasoning + Acting) is a pattern for building LLM agents that interleaves "
            "reasoning traces with tool calls. It solves the problem of agents taking actions "
            "without explaining why, making them hard to debug and prone to errors. "
            "The four components per step are: Thought (the model's reasoning), "
            "Action (the tool call), Observation (the tool's output), and the next Thought "
            "which decides whether to call another tool or produce a Final Answer."
        ),
    },
    {
        "id": "agent_02",
        "category": "agent_architecture",
        "difficulty": "hard",
        "question": (
            "Why is a stop sequence critical when building a text-based ReAct agent? "
            "What goes wrong without one, and what should the stop sequence be set to?"
        ),
        "reference": (
            "Without a stop sequence, the model continues generating text past the Action line "
            "and hallucinates the Observation — it invents the tool's output instead of waiting "
            "for the real result. The stop sequence should be set to the string that begins an "
            "Observation in the format (typically '\\nObservation:'). When the model generates "
            "an Action, it stops before writing the Observation, allowing the code to execute "
            "the real tool and inject the actual result."
        ),
    },
    {
        "id": "agent_03",
        "category": "agent_architecture",
        "difficulty": "medium",
        "question": (
            "What is the practical difference between a pipeline and an agent when a primary "
            "data source fails? Give a concrete example."
        ),
        "reference": (
            "A pipeline handles failure only if the developer anticipated and coded that specific "
            "failure path. If the file is missing and the pipeline has no fallback, it fails. "
            "An agent observes the error from the tool call and reasons about what to do next — "
            "it can try a fallback tool, ask for clarification, or report failure honestly, "
            "without any pre-written fallback code. "
            "Example: a pipeline that reads a price from a file with a hardcoded database fallback "
            "handles exactly those two scenarios. An agent with both tools described in its system "
            "prompt handles any combination of failures dynamically."
        ),
    },
    # --- Edge AI ---
    {
        "id": "edge_01",
        "category": "edge_ai",
        "difficulty": "medium",
        "question": (
            "Name three scenarios where running an LLM locally is preferable to calling a cloud API, "
            "and explain why for each."
        ),
        "reference": (
            "1. Regulated data (healthcare, finance, legal): data cannot legally leave the device "
            "or organisation. Local inference eliminates the data transfer risk. "
            "2. High-volume batch processing: per-token cloud costs become the dominant expense "
            "at scale. Local inference has near-zero marginal cost after hardware. "
            "3. Offline or air-gapped environments: field devices, industrial systems, and "
            "government infrastructure often have no reliable internet. Local models run without connectivity."
        ),
    },
    {
        "id": "edge_02",
        "category": "edge_ai",
        "difficulty": "medium",
        "question": (
            "In the Gemma 4 E2B vs 26B benchmark on Apple M4, which task types showed "
            "identical quality between the two models, and which showed a meaningful gap? "
            "What routing decision does this suggest?"
        ),
        "reference": (
            "Identical quality (5/5 both): factual recall and summarisation. "
            "Meaningful gap: reasoning tasks (E2B 4/5, 26B 4.5/5) and code instruction-following "
            "(E2B verbose and ignored format constraints, 26B concise and compliant). "
            "Routing decision: always use E2B for factual and summarisation tasks (2.5x faster, "
            "same quality). Use 26B for reasoning tasks requiring precision and code tasks "
            "where format compliance matters."
        ),
    },
    # --- Evaluation ---
    {
        "id": "eval_01",
        "category": "evaluation",
        "difficulty": "medium",
        "question": (
            "What is verbosity bias in LLM evaluation, and how does it affect benchmark results "
            "if the judge prompt does not account for it?"
        ),
        "reference": (
            "Verbosity bias is the tendency of evaluators — human or model — to rate longer, "
            "more detailed responses higher, regardless of whether the extra length adds accuracy "
            "or value. If the judge prompt does not explicitly state that concise correct answers "
            "score as high as verbose correct answers, the benchmark will systematically reward "
            "models that pad their outputs and penalise models that are precise and brief. "
            "This leads to selecting for verbose models even when brevity is preferred."
        ),
    },
    {
        "id": "eval_02",
        "category": "evaluation",
        "difficulty": "hard",
        "question": (
            "Why should benchmark questions be written before running the model, "
            "and what bias is introduced if you write questions after seeing model outputs?"
        ),
        "reference": (
            "If questions are written after seeing model outputs, the question writer unconsciously "
            "selects or frames questions that the model answered well — because those outputs are "
            "top of mind and seem 'natural.' This inflates benchmark scores because the test set "
            "no longer represents the actual difficulty distribution of real user requests. "
            "The benchmark measures how well the model answers questions derived from its own "
            "outputs, not how well it handles the full range of user intent. "
            "Writing questions before running the model ensures the test set is independent of "
            "what the model can or cannot answer."
        ),
    },
]


# -------------------------------------------------------------------
# MODEL UNDER TEST — single call per question
# -------------------------------------------------------------------

def ask_model(question: str) -> tuple[str, float]:
    """Returns (response_text, tokens_per_sec)."""
    payload = {
        "model": MODEL_UNDER_TEST,
        "messages": [{"role": "user", "content": question}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 600, "num_ctx": 4096},
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()
    text = data["message"]["content"].strip()
    eval_count = data.get("eval_count", 0)
    eval_ms    = data.get("eval_duration", 0) / 1_000_000
    tps = round(eval_count / (eval_ms / 1000), 1) if eval_ms > 0 else 0.0
    return text, tps


# -------------------------------------------------------------------
# HARNESS
# -------------------------------------------------------------------

def run_benchmark(verbose: bool = True) -> dict:
    results     = []
    total_start = time.perf_counter()

    for i, item in enumerate(BENCHMARK, 1):
        if verbose:
            print(f"\n[{i}/{len(BENCHMARK)}] {item['id']} ({item['category']}, {item['difficulty']})")
            print(f"  Q: {item['question'][:80]}...")

        # Step 1: model answers the question
        response, tps = ask_model(item["question"])
        if verbose:
            print(f"  A: {response[:100]}... ({tps} tok/s)")

        # Step 2: judge scores the answer
        judgment = judge(
            question=item["question"],
            response=response,
            reference=item.get("reference"),
        )
        if verbose:
            print(f"  Score: {judgment['score']}/5 — {judgment['reason']}")

        results.append({
            "id":         item["id"],
            "category":   item["category"],
            "difficulty": item["difficulty"],
            "question":   item["question"],
            "response":   response,
            "reference":  item.get("reference"),
            "score":      judgment["score"],
            "reason":     judgment["reason"],
            "tps":        tps,
        })

    total_s = round(time.perf_counter() - total_start, 1)
    return {"results": results, "total_seconds": total_s}


def print_report(data: dict):
    results = data["results"]
    scored  = [r for r in results if r["score"] > 0]

    print(f"\n{'=' * 60}")
    print("  BENCHMARK REPORT")
    print(f"  Model : {MODEL_UNDER_TEST}")
    print(f"  Total time: {data['total_seconds']}s")
    print(f"{'=' * 60}\n")

    # Category breakdown
    categories = sorted(set(r["category"] for r in results))
    print(f"{'Category':<22} {'Avg':>5}  {'Min':>5}  {'Max':>5}  {'N':>4}")
    print("─" * 45)
    for cat in categories:
        cat_results = [r for r in scored if r["category"] == cat]
        if not cat_results:
            continue
        scores = [r["score"] for r in cat_results]
        avg = sum(scores) / len(scores)
        print(f"{cat:<22} {avg:>5.1f}  {min(scores):>5}  {max(scores):>5}  {len(scores):>4}")

    overall_scores = [r["score"] for r in scored]
    overall_avg    = sum(overall_scores) / len(overall_scores) if overall_scores else 0
    print("─" * 45)
    print(f"{'OVERALL':<22} {overall_avg:>5.1f}  {min(overall_scores):>5}  {max(overall_scores):>5}  {len(overall_scores):>4}")

    # Quality gate
    gate_status = "PASS" if overall_avg >= QUALITY_GATE else "FAIL"
    print(f"\n  Quality gate ({QUALITY_GATE}/5): {gate_status}")

    # Per-question detail
    print(f"\n{'─' * 60}")
    print("  Per-question results\n")
    for r in results:
        flag = "  " if r["score"] >= 4 else "! "
        print(f"  {flag}{r['id']:<12} {r['score']}/5  {r['reason'][:60]}")

    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    print("Domain Benchmark Harness — Phase 6")
    print(f"Model under test : {MODEL_UNDER_TEST}")
    print(f"Questions        : {len(BENCHMARK)}")
    print(f"Quality gate     : {QUALITY_GATE}/5")

    data = run_benchmark(verbose=True)
    print_report(data)

    with open("/tmp/benchmark_report.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Full report saved to /tmp/benchmark_report.json")
