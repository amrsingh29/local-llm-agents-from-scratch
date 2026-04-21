"""
LLM-as-Judge — Phase 6

Uses Gemma 26B to score a model response on a 1–5 scale.
Returns a score and a one-sentence reason.

The judge is designed to be:
  - Consistent: same rubric, same output format, every time
  - Calibrated: rubric descriptions anchor each score level
  - Parseable: always returns JSON {"score": N, "reason": "..."}

Usage:
  python 01_llm_judge.py
"""

import json
import requests

OLLAMA_URL  = "http://localhost:11434/api/chat"
JUDGE_MODEL = "gemma4:26b"

JUDGE_PROMPT = """You are an expert evaluator. Score the following model response on a scale from 1 to 5.
Be critical and precise. A concise, complete answer should score as high as a verbose, complete answer.

Question:
{question}

{reference_block}Model response to evaluate:
{response}

Scoring rubric:
5 — Fully correct and complete. Covers all key points. No errors or misleading statements.
4 — Mostly correct. Minor omission or imprecision, but not misleading.
3 — Partially correct. Answers part of the question but misses important points.
2 — Mostly wrong or incomplete. Has correct fragments but overall misleading or insufficient.
1 — Completely wrong, irrelevant, or no useful content.

Respond ONLY with a JSON object. No explanation outside the JSON.
Format: {{"score": <integer 1-5>, "reason": "<one sentence>"}}"""


def judge(
    question: str,
    response: str,
    reference: str = None,
    verbose: bool = False,
) -> dict:
    """
    Scores a model response using Gemma 26B as judge.

    Returns:
        {"score": int, "reason": str}
        or {"score": 0, "reason": "...", "error": True} on parse failure
    """
    reference_block = (
        f"Reference answer (use as gold standard):\n{reference}\n\n"
        if reference else ""
    )

    prompt = JUDGE_PROMPT.format(
        question=question,
        reference_block=reference_block,
        response=response,
    )

    payload = {
        "model": JUDGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 150, "num_ctx": 4096},
    }

    raw_response = requests.post(OLLAMA_URL, json=payload, timeout=60)
    raw_response.raise_for_status()
    raw = raw_response.json()["message"]["content"].strip()

    if verbose:
        print(f"    Judge raw: {raw}")

    # Parse JSON — strip accidental markdown fences
    try:
        cleaned = raw.strip("`").lstrip("json").strip()
        start = cleaned.index("{")
        end   = cleaned.rindex("}") + 1
        parsed = json.loads(cleaned[start:end])
        return {
            "score":  int(parsed["score"]),
            "reason": parsed.get("reason", ""),
        }
    except (ValueError, KeyError, json.JSONDecodeError):
        return {"score": 0, "reason": f"Parse failed: {raw[:80]}", "error": True}


# -------------------------------------------------------------------
# DEMO — three examples showing judge behaviour across quality levels
# -------------------------------------------------------------------

EXAMPLES = [
    {
        "label": "Good answer (expect 4–5)",
        "question": "What is the difference between a pipeline and an agent in AI systems?",
        "reference": (
            "A pipeline executes a fixed, pre-defined sequence of steps. "
            "An agent uses an LLM to decide what to do next at runtime, "
            "can call tools, observe results, and adapt its path based on what it observes."
        ),
        "response": (
            "A pipeline is a fixed sequence of steps defined at design time — the developer "
            "decides what happens at each step in advance. An agent is dynamic: it uses an LLM "
            "to reason about what to do next, calls tools based on what it observes, and can "
            "take different paths depending on the task. The key difference is that a pipeline "
            "cannot adapt to unexpected situations, while an agent can."
        ),
    },
    {
        "label": "Partial answer (expect 3)",
        "question": "What is the difference between a pipeline and an agent in AI systems?",
        "reference": (
            "A pipeline executes a fixed, pre-defined sequence of steps. "
            "An agent uses an LLM to decide what to do next at runtime, "
            "can call tools, observe results, and adapt its path based on what it observes."
        ),
        "response": (
            "A pipeline runs steps in order. An agent is more flexible and can make decisions."
        ),
    },
    {
        "label": "Wrong answer (expect 1–2)",
        "question": "What is the difference between a pipeline and an agent in AI systems?",
        "reference": (
            "A pipeline executes a fixed, pre-defined sequence of steps. "
            "An agent uses an LLM to decide what to do next at runtime, "
            "can call tools, observe results, and adapt its path based on what it observes."
        ),
        "response": (
            "A pipeline is used for water distribution systems. "
            "An agent is a person who represents actors or musicians."
        ),
    },
]


if __name__ == "__main__":
    print("LLM Judge — Phase 6")
    print(f"Judge model: {JUDGE_MODEL}\n")

    for ex in EXAMPLES:
        print(f"{'─' * 55}")
        print(f"Example : {ex['label']}")
        print(f"Response: {ex['response'][:80]}...")

        result = judge(
            question=ex["question"],
            response=ex["response"],
            reference=ex["reference"],
            verbose=False,
        )

        print(f"Score   : {result['score']}/5")
        print(f"Reason  : {result['reason']}")

    print(f"{'─' * 55}")
