"""
Temperature and Sampling Experiments — Phase 2
Demonstrates how temperature, top_p, and top_k affect output variance.
Uses open-ended prompts so variance is visible.
"""

import requests
import time

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:26b"


def run_inference(prompt: str, temperature: float, top_p: float = 0.9,
                  top_k: int = 40, max_tokens: int = 150) -> str:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "num_predict": max_tokens,
            "num_ctx": 4096,
        },
    }
    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# -------------------------------------------------------------------
# Experiment 1: Temperature = Randomness
# Same open-ended prompt, 3 runs at each temperature.
# Low temp → consistent. High temp → creative/unpredictable.
# -------------------------------------------------------------------

def experiment_temperature_variance():
    separator("Experiment 1: Temperature Controls Randomness")

    prompt = "Write the opening sentence of a mystery novel set in Tokyo."
    temperatures = [0.0, 0.7, 1.5]
    runs = 3

    print(f"\nPrompt: \"{prompt}\"\n")

    for temp in temperatures:
        print(f"--- Temperature: {temp} ---")
        responses = []
        for i in range(runs):
            r = run_inference(prompt, temperature=temp)
            responses.append(r)
            print(f"  Run {i+1}: {r[:120]}")

        unique = len(set(responses))
        print(f"  Unique responses: {unique}/{runs}")
        if unique == 1:
            print("  -> Deterministic: identical output every run.")
        elif unique == runs:
            print("  -> Maximum variance: every run is different.")
        else:
            print("  -> Partial variance: some runs differ.")
        print()


# -------------------------------------------------------------------
# Experiment 2: Temperature vs Factual Accuracy
# High temperature introduces errors in factual recall.
# -------------------------------------------------------------------

def experiment_temperature_accuracy():
    separator("Experiment 2: Temperature vs Factual Accuracy")

    factual_prompt = (
        "Answer in one sentence: What is the capital of France, "
        "and in what year did the Eiffel Tower open?"
    )
    temperatures = [0.0, 0.7, 1.2, 1.8]

    print(f"\nPrompt: \"{factual_prompt}\"\n")
    print("Correct answer: Paris, 1889\n")

    for temp in temperatures:
        r = run_inference(factual_prompt, temperature=temp, max_tokens=60)
        correct = "paris" in r.lower() and "1889" in r.lower()
        status = "CORRECT" if correct else "WRONG/PARTIAL"
        print(f"  temp={temp}: [{status}] {r[:150]}")


# -------------------------------------------------------------------
# Experiment 3: Top-p (Nucleus Sampling)
# Controls which tokens are eligible — filters out low-probability tokens.
# -------------------------------------------------------------------

def experiment_top_p():
    separator("Experiment 3: Top-p (Nucleus Sampling)")

    prompt = "Describe the colour blue in an unusual way."
    configs = [
        (0.7, 0.1),   # temp=0.7, top_p=0.1 — very narrow token pool
        (0.7, 0.5),   # temp=0.7, top_p=0.5 — moderate
        (0.7, 0.95),  # temp=0.7, top_p=0.95 — wide token pool
    ]

    print(f"\nPrompt: \"{prompt}\"\n")
    print("Temperature fixed at 0.7. Only top_p varies.\n")

    for temp, top_p in configs:
        r = run_inference(prompt, temperature=temp, top_p=top_p, max_tokens=80)
        print(f"  top_p={top_p}: {r[:200]}")
        print()


# -------------------------------------------------------------------
# Experiment 4: Top-k
# Hard limit on how many tokens are candidates for the next token.
# -------------------------------------------------------------------

def experiment_top_k():
    separator("Experiment 4: Top-k (Hard Candidate Limit)")

    prompt = "What should I name my new coffee shop? Give one creative name."
    configs = [
        (0.8, 1),    # top_k=1 — only the single most likely token (greedy)
        (0.8, 10),   # top_k=10 — small candidate pool
        (0.8, 100),  # top_k=100 — large candidate pool
    ]

    print(f"\nPrompt: \"{prompt}\"\n")
    print("Temperature fixed at 0.8. Only top_k varies.\n")

    for temp, top_k in configs:
        r = run_inference(prompt, temperature=temp, top_k=top_k, max_tokens=60)
        print(f"  top_k={top_k:>3}: {r[:200]}")
        print()


# -------------------------------------------------------------------
# Experiment 5: The Right Temperature for the Task
# Shows that temperature is not a quality knob — it is a task knob.
# -------------------------------------------------------------------

def experiment_right_temperature():
    separator("Experiment 5: Right Temperature for the Task")

    tasks = [
        (
            "factual",
            "What is the boiling point of water at sea level in Celsius?",
            0.0,
            "Factual Q&A — temp=0 for deterministic, correct answers"
        ),
        (
            "code",
            "Write a Python function that returns the factorial of n.",
            0.1,
            "Code generation — temp=0.1 for correct logic with minor variation"
        ),
        (
            "creative",
            "Write a haiku about debugging code at 2am.",
            0.9,
            "Creative writing — temp=0.9 for varied, interesting output"
        ),
        (
            "brainstorm",
            "Give me 3 unusual business ideas involving coffee and AI.",
            1.1,
            "Brainstorming — temp=1.1 for maximum idea diversity"
        ),
    ]

    for task_type, prompt, temp, label in tasks:
        print(f"\n{label}")
        print(f"Prompt: \"{prompt}\"")
        r = run_inference(prompt, temperature=temp, max_tokens=100)
        print(f"Answer: {r[:300]}")


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Model  : {MODEL}")
    print(f"Server : {OLLAMA_URL}")
    print("\nThis script makes ~20 inference calls.")
    print("Expect ~8 minutes total runtime.\n")

    experiment_temperature_variance()
    experiment_temperature_accuracy()
    experiment_top_p()
    experiment_top_k()
    experiment_right_temperature()

    print(f"\n{'=' * 60}")
    print("  Temperature experiments complete.")
    print(f"{'=' * 60}\n")
