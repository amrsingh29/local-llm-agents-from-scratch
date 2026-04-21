"""
Context Window Limits — Phase 2
Demonstrates the 'lost in the middle' problem:
models pay less attention to content buried in the middle of long contexts.
"""

import requests
import time

OLLAMA_URL_GENERATE = "http://localhost:11434/api/generate"
OLLAMA_URL_CHAT = "http://localhost:11434/api/chat"
MODEL = "gemma4:26b"

# The secret fact we will hide at different positions in a long document
SECRET_FACT = "The quarterly revenue target for Project Nightingale is $4.7 million."

# Filler text — realistic-sounding business content to pad the document
FILLER_PARAGRAPH = (
    "The engineering team completed the migration of legacy services to the new "
    "microservices architecture. Load testing confirmed that the system handles "
    "10,000 concurrent requests with a p99 latency of 120 milliseconds. The database "
    "connection pool was tuned to reduce idle connections by 40 percent. Deployment "
    "pipelines were updated to include automated rollback triggers on error rate "
    "thresholds exceeding 2 percent. The on-call rotation was updated and all team "
    "members completed incident response training. Documentation was updated to "
    "reflect the new service boundaries and API contracts. "
)


def build_document(position: str, filler_paragraphs: int = 80) -> str:
    """Build a long document with the secret fact at beginning, middle, or end."""
    filler = FILLER_PARAGRAPH * filler_paragraphs

    half = len(filler) // 2

    if position == "beginning":
        return SECRET_FACT + "\n\n" + filler
    elif position == "middle":
        return filler[:half] + "\n\n" + SECRET_FACT + "\n\n" + filler[half:]
    elif position == "end":
        return filler + "\n\n" + SECRET_FACT
    else:
        raise ValueError(f"Unknown position: {position}")


def ask_gemma(document: str, question: str) -> dict:
    content = (
        f"Read the following document carefully, then answer the question.\n\n"
        f"Document:\n{document}\n\n"
        f"Question: {question}"
    )

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 100,
            "num_ctx": 16384,
        },
    }

    start = time.time()
    response = requests.post(OLLAMA_URL_CHAT, json=payload)
    response.raise_for_status()
    elapsed = time.time() - start

    data = response.json()
    return {
        "answer": data["message"]["content"].strip(),
        "prompt_tokens": data.get("prompt_eval_count", 0),
        "duration_seconds": round(elapsed, 1),
    }


def count_tokens(text: str) -> int:
    payload = {
        "model": MODEL,
        "prompt": text,
        "stream": False,
        "options": {"num_predict": 0},
    }
    response = requests.post(OLLAMA_URL_GENERATE, json=payload)
    response.raise_for_status()
    return response.json().get("prompt_eval_count", 0)


def separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def check_answer(answer: str) -> bool:
    """Check if the answer contains the revenue figure and is not a denial."""
    answer_lower = answer.lower()
    has_figure = "4.7" in answer_lower
    is_denial = "no mention" in answer_lower or "not mention" in answer_lower or "does not" in answer_lower
    return has_figure and not is_denial


# -------------------------------------------------------------------
# Experiment 1: Lost in the Middle
# The same fact, at three different positions — does Gemma find it?
# -------------------------------------------------------------------

def experiment_lost_in_middle():
    separator("Experiment 1: Lost in the Middle")

    question = "What is the quarterly revenue target for Project Nightingale?"

    print(f"\nSecret fact : \"{SECRET_FACT}\"")
    print(f"Question    : \"{question}\"")
    print(f"\nBuilding documents and running queries...\n")

    positions = ["beginning", "middle", "end"]
    results = []

    for position in positions:
        document = build_document(position, filler_paragraphs=80)
        result = ask_gemma(document, question)
        found = check_answer(result["answer"])
        results.append({
            "position": position,
            "found": found,
            **result,
        })

        status = "FOUND" if found else "MISSED"
        print(f"Position : {position.upper()}")
        print(f"Tokens   : {result['prompt_tokens']:,}")
        print(f"Duration : {result['duration_seconds']}s")
        print(f"Answer   : {result['answer'][:200]}")
        print(f"Result   : {status}")
        print()

    print("--- Summary ---")
    print(f"{'Position':<12} {'Tokens':>8} {'Found?':>8}")
    print("-" * 32)
    for r in results:
        found_str = "YES" if r["found"] else "NO"
        print(f"{r['position']:<12} {r['prompt_tokens']:>8,} {found_str:>8}")


# -------------------------------------------------------------------
# Experiment 2: Context Size vs Throughput
# How does prompt token count affect tokens/sec?
# -------------------------------------------------------------------

def experiment_context_vs_throughput():
    separator("Experiment 2: Context Size vs Throughput")

    prompt_template = "Summarize the following text in one sentence:\n\n{}\n\nSummary:"
    filler_sizes = [10, 40, 80, 150]

    print(f"\n{'Filler Paras':>12} {'Prompt Tokens':>14} {'Duration (s)':>13} {'Output tok/s':>13}")
    print("-" * 56)

    for n in filler_sizes:
        filler = FILLER_PARAGRAPH * n
        prompt = prompt_template.format(filler)

        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"temperature": 0.0, "num_predict": 30, "num_ctx": 16384},
        }

        start = time.time()
        response = requests.post(OLLAMA_URL_CHAT, json=payload)
        response.raise_for_status()
        elapsed = time.time() - start

        data = response.json()
        prompt_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)
        tps = round(output_tokens / elapsed, 1) if elapsed > 0 else 0

        print(f"{n:>12} {prompt_tokens:>14,} {elapsed:>12.1f}s {tps:>12.1f}")

    print("\nKey insight: as prompt size grows, the model must attend to more")
    print("tokens at each generation step — throughput drops accordingly.")


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Model  : {MODEL}")
    print(f"Server : {OLLAMA_URL}")
    print("\nWarning: this script sends large prompts to Gemma.")
    print("Expect 5-15 minutes total runtime.\n")

    experiment_lost_in_middle()
    experiment_context_vs_throughput()

    print(f"\n{'=' * 60}")
    print("  Context window experiments complete.")
    print(f"{'=' * 60}\n")
