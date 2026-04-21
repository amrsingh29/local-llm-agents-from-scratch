"""
Tokenization Experiments — Phase 2
Demonstrates what tokens actually are using Ollama's token counter.
No HuggingFace account required — uses prompt_eval_count from the model itself.
"""

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:26b"


def count_tokens(text: str) -> int:
    """Ask Ollama to count tokens in text. num_predict=0 means no generation."""
    payload = {
        "model": MODEL,
        "prompt": text,
        "stream": False,
        "options": {"num_predict": 0},
    }
    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()
    return response.json().get("prompt_eval_count", 0)


def separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# -------------------------------------------------------------------
# Experiment 1: Words are not tokens
# The most common wrong assumption about LLMs.
# -------------------------------------------------------------------

def experiment_words_vs_tokens():
    separator("Experiment 1: Words Are Not Tokens")

    samples = [
        ("Simple words", "cat dog run fast"),
        ("Same words with punctuation", "cat, dog. run! fast?"),
        ("Compound word", "Supercalifragilisticexpialidocious"),
        ("Common phrase", "The quick brown fox"),
        ("Repeated word", "dog dog dog dog dog"),
        ("Capitalization change", "hello Hello HELLO"),
    ]

    print(f"\n{'Text':<45} {'Words':>6} {'Tokens':>7} {'Ratio':>7}")
    print("-" * 68)

    for label, text in samples:
        tokens = count_tokens(text)
        words = len(text.split())
        ratio = round(tokens / words, 2) if words > 0 else 0
        print(f"{label:<45} {words:>6} {tokens:>7} {ratio:>6}x")

    print("\nKey insight: punctuation, capitalization, and rare words")
    print("all affect token count independently of word count.")


# -------------------------------------------------------------------
# Experiment 2: The '4 chars per token' myth
# Different text types tokenize very differently.
# -------------------------------------------------------------------

def experiment_chars_per_token():
    separator("Experiment 2: The '4 Chars Per Token' Myth")

    samples = {
        "Plain English prose": (
            "The meeting was scheduled for Tuesday afternoon. "
            "All team members were expected to attend and bring their laptops."
        ),
        "Technical jargon": (
            "The microservices architecture uses Kubernetes for orchestration, "
            "with Prometheus and Grafana for observability."
        ),
        "Python code": (
            "for i in range(len(items)):\n"
            "    if items[i] > threshold:\n"
            "        results.append(items[i])"
        ),
        "JSON data": (
            '{"user_id": 12345, "email": "user@example.com", '
            '"created_at": "2026-04-20T10:30:00Z", "active": true}'
        ),
        "Non-English (Hindi)": "नमस्ते, आप कैसे हैं? मैं ठीक हूँ।",
        "Numbers": "1 2 3 100 1000 3.14159 9999999 0.000001",
        "Whitespace heavy": "word     word          word               word",
    }

    print(f"\n{'Type':<28} {'Chars':>6} {'Tokens':>7} {'Chars/Token':>12}")
    print("-" * 56)

    for label, text in samples.items():
        tokens = count_tokens(text)
        chars = len(text)
        ratio = round(chars / tokens, 1) if tokens > 0 else 0
        print(f"{label:<28} {chars:>6} {tokens:>7} {ratio:>11.1f}")

    print("\nKey insight: non-English text and special characters use")
    print("far more tokens per character than plain English.")
    print("This directly affects cost and context window usage.")


# -------------------------------------------------------------------
# Experiment 3: Prompt length has a real cost
# Verbose prompts eat into your context window.
# -------------------------------------------------------------------

def experiment_prompt_token_cost():
    separator("Experiment 3: Prompt Length Has a Real Cost")

    prompt_short = "Summarize this document."
    prompt_verbose = (
        "You are an expert technical writer. "
        "Please provide a comprehensive, well-structured summary of the following document. "
        "Focus on the key points, main arguments, and any actionable conclusions. "
        "Write in a professional tone suitable for a business audience."
    )

    tokens_short = count_tokens(prompt_short)
    tokens_verbose = count_tokens(prompt_verbose)
    context_window = 256_000

    print(f"\nShort prompt   : {tokens_short} tokens")
    print(f"  \"{prompt_short}\"")
    print(f"\nVerbose prompt : {tokens_verbose} tokens")
    print(f"  \"{prompt_verbose[:80]}...\"")
    print(f"\nExtra tokens   : {tokens_verbose - tokens_short}")
    print(f"\nGemma 4 26B context window : {context_window:,} tokens")
    print(f"After short prompt         : {context_window - tokens_short:,} tokens for content")
    print(f"After verbose prompt       : {context_window - tokens_verbose:,} tokens for content")
    print(
        f"\nFor a cloud API at $1/million tokens, across 10,000 calls/day:"
    )
    daily_extra = (tokens_verbose - tokens_short) * 10_000
    print(f"  Extra tokens/day : {daily_extra:,}")
    print(f"  Extra cost/day   : ${daily_extra / 1_000_000:.2f}")
    print(f"  Extra cost/year  : ${daily_extra / 1_000_000 * 365:.0f}")


# -------------------------------------------------------------------
# Experiment 4: Same meaning, different token cost
# Phrasing choices have measurable token implications.
# -------------------------------------------------------------------

def experiment_phrasing_impact():
    separator("Experiment 4: Phrasing Choices Have Token Costs")

    pairs = [
        ("Use AI.", "Please utilize artificial intelligence technologies."),
        ("List 3 bugs.", "Please enumerate exactly three software defects present in the code."),
        ("Why?", "Could you please explain the underlying reasoning behind this decision?"),
        ("Fix the error.", "Please correct the mistake and ensure it does not occur again in future."),
    ]

    print(f"\n{'Short':<20} {'Tokens':>6}   {'Verbose':<55} {'Tokens':>6}")
    print("-" * 92)

    for short, verbose in pairs:
        t_short = count_tokens(short)
        t_verbose = count_tokens(verbose)
        overhead = t_verbose - t_short
        print(f"{short:<20} {t_short:>6}   {verbose:<55} {t_verbose:>6}  (+{overhead})")

    print("\nKey insight: in a high-volume production system, prompt verbosity")
    print("is a measurable engineering cost, not just a style preference.")


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Model  : {MODEL}")
    print(f"Server : {OLLAMA_URL}")
    print("\nNote: each token count requires one Ollama API call.")
    print("This script makes ~25 calls — expect ~2 minutes to complete.\n")

    experiment_words_vs_tokens()
    experiment_chars_per_token()
    experiment_prompt_token_cost()
    experiment_phrasing_impact()

    print(f"\n{'=' * 60}")
    print("  Tokenization experiments complete.")
    print(f"{'=' * 60}\n")
