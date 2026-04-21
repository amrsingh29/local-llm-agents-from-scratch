import requests
import time

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:26b"


def run_inference(prompt: str) -> dict:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
    }

    start = time.time()
    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()
    elapsed = time.time() - start

    data = response.json()
    return {
        "response": data["message"]["content"],
        "tokens_generated": data.get("eval_count", 0),
        "duration_seconds": round(elapsed, 2),
        "tokens_per_second": round(data.get("eval_count", 0) / elapsed, 1),
    }


def print_result(result: dict) -> None:
    print("\n--- Response ---")
    print(result["response"])
    print("\n--- Stats ---")
    print(f"Tokens generated : {result['tokens_generated']}")
    print(f"Duration         : {result['duration_seconds']}s")
    print(f"Throughput       : {result['tokens_per_second']} tokens/sec")


if __name__ == "__main__":
    prompt = "In one sentence, what is a large language model?"
    print(f"Model  : {MODEL}")
    print(f"Prompt : {prompt}")

    result = run_inference(prompt)
    print_result(result)
