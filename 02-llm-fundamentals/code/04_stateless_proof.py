"""
Statelessness Experiments — Phase 2
Proves that LLMs have zero memory between API calls.
Shows how chat applications fake memory by sending history every time.
"""

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:26b"


def single_turn(prompt: str, temperature: float = 0.0) -> str:
    """A single stateless call — no history."""
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": temperature, "num_predict": 150},
    }
    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def multi_turn(messages: list, temperature: float = 0.0) -> str:
    """Multi-turn call — full history sent every time."""
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"temperature": temperature, "num_predict": 150},
    }
    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# -------------------------------------------------------------------
# Experiment 1: Prove Statelessness
# Tell the model your name in call 1.
# Ask for your name in call 2 — a completely fresh call.
# The model has no idea.
# -------------------------------------------------------------------

def experiment_prove_statelessness():
    separator("Experiment 1: Proving Statelessness")

    print("\nCall 1: Tell Gemma your name")
    call1_prompt = "My name is Amrendra. Please remember that."
    call1_response = single_turn(call1_prompt)
    print(f"  Prompt   : {call1_prompt}")
    print(f"  Response : {call1_response[:200]}")

    print("\nCall 2: Ask Gemma your name — completely new API call")
    call2_prompt = "What is my name?"
    call2_response = single_turn(call2_prompt)
    print(f"  Prompt   : {call2_prompt}")
    print(f"  Response : {call2_response[:200]}")

    print("\nCall 3: Ask something that assumes context from call 1")
    call3_prompt = "What did I just ask you to remember?"
    call3_response = single_turn(call3_prompt)
    print(f"  Prompt   : {call3_prompt}")
    print(f"  Response : {call3_response[:200]}")

    print("\n--- Finding ---")
    print("Each call is isolated. The model has no memory of previous calls.")
    print("It does not know your name, what you said, or that you exist.")


# -------------------------------------------------------------------
# Experiment 2: How Chat Apps Fake Memory
# Send the full conversation history in every API call.
# The model appears to remember — but it is reading the transcript.
# -------------------------------------------------------------------

def experiment_faked_memory():
    separator("Experiment 2: How Chat Applications Fake Memory")

    print("\nBuilding a conversation turn by turn...\n")

    history = []

    turns = [
        ("user", "My name is Amrendra and I work as a Solutions Engineer."),
        ("user", "I am currently learning about AI agents and LLMs."),
        ("user", "What do you know about me so far?"),
        ("user", "Based on what I told you, what kind of AI projects might be most useful for my role?"),
    ]

    for role, content in turns:
        history.append({"role": role, "content": content})
        print(f"User: {content}")

        response = multi_turn(history)
        history.append({"role": "assistant", "content": response})

        print(f"Gemma: {response[:300]}")
        print(f"[History sent this call: {len(history)} messages]\n")

    print("--- Finding ---")
    print("The model 'remembers' because every call sends the full transcript.")
    print("There is no memory — only context. The model reads, not recalls.")


# -------------------------------------------------------------------
# Experiment 3: The Context Growth Problem
# Show how conversation history grows the prompt over time.
# In a long chat, you eventually run out of context window.
# -------------------------------------------------------------------

def experiment_context_growth():
    separator("Experiment 3: Context Window Fills Up Over Time")

    print("\nSimulating a long conversation and tracking token growth...\n")

    history = []
    questions = [
        "What is a neural network?",
        "How does backpropagation work?",
        "What is the difference between supervised and unsupervised learning?",
        "What are transformers in the context of AI?",
        "How does attention mechanism work?",
    ]

    print(f"{'Turn':>5} {'Messages in History':>20} {'Approx Tokens':>15}")
    print("-" * 45)

    for i, question in enumerate(questions, 1):
        history.append({"role": "user", "content": question})
        response = multi_turn(history, temperature=0.0)
        history.append({"role": "assistant", "content": response})

        total_chars = sum(len(m["content"]) for m in history)
        approx_tokens = total_chars // 4

        print(f"{i:>5} {len(history):>20} {approx_tokens:>15,}")

    print(f"\nAfter {len(questions)} turns:")
    print(f"  Messages in history : {len(history)}")
    print(f"  Approx total tokens : {sum(len(m['content']) for m in history) // 4:,}")
    print(f"\nAt this rate, a 256K context window fills in roughly:")
    avg_tokens_per_turn = (sum(len(m['content']) for m in history) // 4) / len(questions)
    turns_to_fill = int(256_000 / avg_tokens_per_turn)
    print(f"  ~{turns_to_fill} conversation turns")
    print("\nProduction chat systems must summarize or truncate old history")
    print("to prevent hitting the context limit.")


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Model  : {MODEL}")
    print(f"Server : {OLLAMA_URL}")
    print("\nThis script makes ~15 inference calls.")
    print("Expect ~10 minutes total runtime.\n")

    experiment_prove_statelessness()
    experiment_faked_memory()
    experiment_context_growth()

    print(f"\n{'=' * 60}")
    print("  Statelessness experiments complete.")
    print(f"{'=' * 60}\n")
