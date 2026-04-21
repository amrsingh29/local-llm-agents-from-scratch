import requests
import time
import statistics

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:26b"


def run_inference(prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> dict:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
        },
    }

    start = time.time()
    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()
    elapsed = time.time() - start

    data = response.json()
    tokens_generated = data.get("eval_count", 0)

    return {
        "response": data["message"]["content"],
        "tokens_generated": tokens_generated,
        "duration_seconds": round(elapsed, 2),
        "tokens_per_second": round(tokens_generated / elapsed, 1) if elapsed > 0 else 0,
        "prompt_tokens": data.get("prompt_eval_count", 0),
    }


def separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def experiment_short_vs_long():
    separator("Experiment 1: Short vs Long Response Throughput")

    prompt = (
        "Explain how a transformer neural network works. "
        "Be as detailed as possible."
    )

    configs = [
        ("Short  (~100 tokens)", 100),
        ("Medium (~300 tokens)", 300),
        ("Long   (~800 tokens)", 800),
    ]

    for label, max_tokens in configs:
        print(f"\nRunning: {label}")
        result = run_inference(prompt, max_tokens=max_tokens, temperature=0.0)
        print(f"  Tokens generated : {result['tokens_generated']}")
        print(f"  Duration         : {result['duration_seconds']}s")
        print(f"  Throughput       : {result['tokens_per_second']} tokens/sec")


def experiment_temperature():
    separator("Experiment 2: Temperature Effect on Output Variance")

    prompt = "In exactly two sentences, describe what causes thunder."
    temperatures = [0.0, 0.7, 1.5]
    runs_per_temp = 3

    for temp in temperatures:
        print(f"\n--- Temperature: {temp} ---")
        responses = []
        for i in range(runs_per_temp):
            result = run_inference(prompt, max_tokens=100, temperature=temp)
            responses.append(result["response"].strip())
            print(f"  Run {i + 1}: {result['response'].strip()[:120]}...")

        unique = len(set(responses))
        print(f"  Unique responses out of {runs_per_temp}: {unique}")
        if unique == 1:
            print("  -> Output is deterministic at this temperature.")
        else:
            print("  -> Output varies between runs at this temperature.")


def experiment_throughput_stability():
    separator("Experiment 3: Throughput Stability Across Runs")

    prompt = "List 5 key differences between relational and non-relational databases."
    runs = 5

    print(f"\nRunning same prompt {runs} times...\n")
    tps_values = []

    for i in range(runs):
        result = run_inference(prompt, max_tokens=200, temperature=0.0)
        tps = result["tokens_per_second"]
        tps_values.append(tps)
        print(f"  Run {i + 1}: {result['tokens_generated']} tokens in {result['duration_seconds']}s → {tps} tok/sec")

    print(f"\n  Min      : {min(tps_values)} tok/sec")
    print(f"  Max      : {max(tps_values)} tok/sec")
    print(f"  Average  : {round(statistics.mean(tps_values), 1)} tok/sec")
    print(f"  Std dev  : {round(statistics.stdev(tps_values), 2)} tok/sec")


if __name__ == "__main__":
    print(f"Model: {MODEL}")
    print(f"Server: {OLLAMA_URL}")

    experiment_short_vs_long()
    experiment_temperature()
    experiment_throughput_stability()

    print(f"\n{'=' * 60}")
    print("  Benchmark complete.")
    print(f"{'=' * 60}\n")
