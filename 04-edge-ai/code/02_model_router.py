"""
Model Router — Phase 4

Classifies an incoming prompt and dispatches it to the appropriate
local model based on task type.

Routing table (derived from benchmark results):
  factual   → gemma4:e2b   (identical quality, 2.5x faster)
  summarise → gemma4:e2b   (identical quality, 2.5x faster)
  reasoning → gemma4:26b   (more reliable on multi-step derivation)
  code      → gemma4:26b   (better instruction-following, concise output)

The classifier itself runs on gemma4:e2b — fast, single-word output.
If classification fails or returns an unknown label, defaults to 26b.

Usage:
  python 02_model_router.py
"""

import requests
import time

OLLAMA_URL = "http://localhost:11434/api/chat"

ROUTING_TABLE = {
    "factual":   "gemma4:e2b",
    "summarise": "gemma4:e2b",
    "reasoning": "gemma4:26b",
    "code":      "gemma4:26b",
}

CLASSIFIER_MODEL = "gemma4:e2b"
DEFAULT_MODEL    = "gemma4:26b"

CLASSIFIER_PROMPT = """Classify the following prompt into exactly one of these four categories:

  factual   — asking for a definition, explanation, or fact
  summarise — asking to condense or restate existing content
  reasoning — asking to derive an answer through calculation or multi-step logic
  code      — asking to write, fix, or explain code

Reply with only the single category word. No punctuation. No explanation.

Prompt to classify:
{prompt}"""


# -------------------------------------------------------------------
# CORE FUNCTIONS
# -------------------------------------------------------------------

def call_model(model: str, prompt: str, max_tokens: int = 600) -> tuple[str, float]:
    """Returns (response_text, tokens_per_sec)."""
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
    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()

    text = data["message"]["content"].strip()
    eval_count = data.get("eval_count", 0)
    eval_duration_ms = data.get("eval_duration", 0) / 1_000_000
    tps = round(eval_count / (eval_duration_ms / 1000), 1) if eval_duration_ms > 0 else 0.0

    return text, tps


def classify(prompt: str) -> str:
    """
    Classifies the prompt into a task category.
    Returns one of: factual | summarise | reasoning | code
    Falls back to DEFAULT_MODEL's category if unknown label returned.
    """
    classifier_input = CLASSIFIER_PROMPT.format(prompt=prompt)
    raw, _ = call_model(CLASSIFIER_MODEL, classifier_input, max_tokens=10)

    # Normalise — strip punctuation, lowercase, take first word
    label = raw.strip().lower().rstrip(".,;:").split()[0] if raw.strip() else ""

    if label not in ROUTING_TABLE:
        return "unknown"
    return label


def route(prompt: str, verbose: bool = True) -> dict:
    """
    Classifies the prompt, selects the appropriate model, runs inference.
    Returns a result dict with model, label, response, and timing stats.
    """
    # Step 1: classify
    t0 = time.perf_counter()
    label = classify(prompt)
    classify_ms = round((time.perf_counter() - t0) * 1000, 1)

    model = ROUTING_TABLE.get(label, DEFAULT_MODEL)

    if verbose:
        print(f"  Classifier  : '{label}' ({classify_ms}ms)")
        print(f"  Routed to   : {model}")

    # Step 2: run main inference
    t1 = time.perf_counter()
    response, tps = call_model(model, prompt)
    inference_ms = round((time.perf_counter() - t1) * 1000, 1)

    if verbose:
        print(f"  Inference   : {inference_ms}ms at {tps} tok/s")

    return {
        "label": label,
        "model": model,
        "response": response,
        "classify_ms": classify_ms,
        "inference_ms": inference_ms,
        "tokens_per_sec": tps,
        "total_ms": round(classify_ms + inference_ms, 1),
    }


# -------------------------------------------------------------------
# DEMO
# -------------------------------------------------------------------

DEMO_PROMPTS = [
    {
        "prompt": "What is the difference between supervised and unsupervised learning? Answer in 2 sentences.",
        "expected_label": "factual",
        "expected_model": "gemma4:e2b",
    },
    {
        "prompt": (
            "Summarise the following in 2 sentences:\n\n"
            "Retrieval-Augmented Generation (RAG) is a technique that combines a retrieval "
            "system with a language model. Instead of relying solely on the model's trained "
            "knowledge, RAG fetches relevant documents from an external source at inference "
            "time and includes them in the prompt. This allows the model to answer questions "
            "about data it was not trained on, and reduces hallucination by grounding "
            "responses in retrieved facts."
        ),
        "expected_label": "summarise",
        "expected_model": "gemma4:e2b",
    },
    {
        "prompt": (
            "A server handles 450 requests per minute. Each request takes an average of "
            "200ms to process. How many concurrent worker threads are needed to sustain "
            "this load without queuing? Show your calculation."
        ),
        "expected_label": "reasoning",
        "expected_model": "gemma4:26b",
    },
    {
        "prompt": (
            "Write a Python function called `chunk_list` that takes a list and a chunk size "
            "and returns a list of sublists, each of length chunk_size (the last may be shorter). "
            "No explanation. Just the function."
        ),
        "expected_label": "code",
        "expected_model": "gemma4:26b",
    },
]


def separator(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    print("Model Router — Phase 4")
    print(f"Classifier : {CLASSIFIER_MODEL}")
    print(f"Default    : {DEFAULT_MODEL}")
    print(f"Routes     : {ROUTING_TABLE}")

    for i, item in enumerate(DEMO_PROMPTS, 1):
        separator(f"Prompt {i} — expected: {item['expected_label']} → {item['expected_model']}")
        print(f"\nPrompt: {item['prompt'][:80]}{'...' if len(item['prompt']) > 80 else ''}\n")

        result = route(item["prompt"], verbose=True)

        label_match = "OK" if result["label"] == item["expected_label"] else f"WRONG (got '{result['label']}')"
        model_match = "OK" if result["model"] == item["expected_model"] else f"WRONG (got '{result['model']}')"

        print(f"\n  Label check : {label_match}")
        print(f"  Model check : {model_match}")
        print(f"  Total time  : {result['total_ms']}ms")
        print(f"\n  Response:\n  {result['response'][:300]}{'...' if len(result['response']) > 300 else ''}")

    separator("Router Demo Complete")
    print("\nThe router adds one classification call (~200ms) and then")
    print("routes to the appropriate model for every subsequent request.")
    print("For high-throughput pipelines, cache classification results")
    print("for repeated prompt patterns to eliminate the overhead entirely.\n")
