"""
Bare-Metal ReAct Agent — Phase 3
A from-scratch implementation of the ReAct pattern using Gemma 4 26B locally.
No LangChain. No frameworks. Pure Python + Ollama API.

ReAct = Reasoning + Acting interleaved.
The model alternates between:
  Thought:     reasoning about what to do
  Action:      calling a tool
  Observation: reading the tool result
"""

import requests
import json
import math
import re
import os
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:26b"
MAX_STEPS = 8


# -------------------------------------------------------------------
# TOOLS
# Each tool is a plain Python function.
# The agent calls these based on what it decides to do.
# -------------------------------------------------------------------

def calculator(expression: str) -> str:
    """Evaluate a safe math expression. Returns result as string."""
    allowed = set("0123456789+-*/()., ")
    if not all(c in allowed for c in expression):
        return f"Error: unsafe characters in expression '{expression}'"
    try:
        result = eval(expression, {"__builtins__": {}}, {"math": math})
        return str(round(float(result), 4))
    except Exception as e:
        return f"Error: {str(e)}"


def get_current_date(_: str = "") -> str:
    """Return the current date."""
    return datetime.now().strftime("%A, %B %d, %Y")


def file_read(path: str) -> str:
    """Read a file and return its contents. Only reads .txt and .md files."""
    if not path.endswith((".txt", ".md")):
        return "Error: only .txt and .md files are supported"
    if not os.path.exists(path):
        return f"Error: file not found at path '{path}'"
    try:
        with open(path, "r") as f:
            content = f.read()
        return content[:2000] if len(content) > 2000 else content
    except Exception as e:
        return f"Error reading file: {str(e)}"


def word_count(text: str) -> str:
    """Count the number of words in the provided text."""
    words = len(text.split())
    chars = len(text)
    return f"{words} words, {chars} characters"


TOOLS = {
    "calculator": calculator,
    "get_current_date": get_current_date,
    "file_read": file_read,
    "word_count": word_count,
}

TOOL_DESCRIPTIONS = """
- calculator(expression) → evaluates a math expression. Example: calculator(100 * 1.08)
- get_current_date() → returns today's date. Example: get_current_date()
- file_read(path) → reads a .txt or .md file. Example: file_read(/path/to/file.txt)
- word_count(text) → counts words in the provided text. Example: word_count(Hello world)
"""


# -------------------------------------------------------------------
# SYSTEM PROMPT
# Defines the ReAct format the model must follow.
# -------------------------------------------------------------------

SYSTEM_PROMPT = f"""You are a helpful AI agent with access to tools.

To complete a task, follow this exact format — repeating as many times as needed:

Thought: [your reasoning about what to do next]
Action: tool_name(argument)
Observation: [result of the tool — this will be filled in for you]

When you have the final answer, write:
Thought: I now have all the information needed.
Final Answer: [your complete answer to the user]

Available tools:
{TOOL_DESCRIPTIONS}

Rules:
- Always write a Thought before every Action
- Only call one tool per Action line
- Never make up Observation results — wait for the real output
- If a tool returns an error, acknowledge it and try a different approach
- Do not ask clarifying questions — make reasonable assumptions and proceed
"""


# -------------------------------------------------------------------
# CORE AGENT FUNCTIONS
# -------------------------------------------------------------------

def call_llm(messages: list) -> str:
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 300,
            "num_ctx": 8192,
            "stop": ["\nObservation:"],
        },
    }
    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def parse_action(text: str) -> tuple[str, str] | None:
    """Extract tool name and argument from 'Action: tool_name(argument)' line."""
    match = re.search(r"Action:\s*(\w+)\(([^)]*)\)", text)
    if not match:
        return None
    tool_name = match.group(1).strip()
    argument = match.group(2).strip()
    return tool_name, argument


def run_agent(task: str, verbose: bool = True) -> str:
    """Run the ReAct agent loop until task is complete or max steps reached."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": task},
    ]

    if verbose:
        print(f"\nTask: {task}")
        print("=" * 60)

    for step in range(1, MAX_STEPS + 1):
        if verbose:
            print(f"\n[Step {step}]")

        # THINK
        response = call_llm(messages)
        messages.append({"role": "assistant", "content": response})

        if verbose:
            print(response)

        # Check for final answer
        if "Final Answer:" in response:
            final = re.search(r"Final Answer:\s*(.+)", response, re.DOTALL)
            return final.group(1).strip() if final else response

        # ACT
        parsed = parse_action(response)
        if not parsed:
            if verbose:
                print("[Agent produced no action and no final answer — stopping]")
            break

        tool_name, argument = parsed

        # OBSERVE
        if tool_name not in TOOLS:
            observation = f"Error: unknown tool '{tool_name}'. Available: {list(TOOLS.keys())}"
        else:
            try:
                observation = TOOLS[tool_name](argument)
            except Exception as e:
                observation = f"Error executing {tool_name}: {str(e)}"

        observation_text = f"Observation: {observation}"
        messages.append({"role": "assistant", "content": observation_text})

        if verbose:
            print(observation_text)

    return "Agent reached maximum steps without completing the task."


# -------------------------------------------------------------------
# TEST TASKS
# -------------------------------------------------------------------

def run_all_tasks():
    tasks = [
        # Task 1: Simple calculator
        "What is 15% tip on a $84.50 restaurant bill? And what is the total?",

        # Task 2: Multi-step reasoning
        "If I invest $5,000 today at 7% annual return, how much will I have after 10 years? Use compound interest formula: P * (1 + r)^n",

        # Task 3: Date awareness
        "What day of the week is today, and how many days until the end of the year?",

        # Task 4: Multi-tool task
        "What is today's date? Also calculate 365 * 24 * 60 to find out how many minutes are in a year.",
    ]

    for i, task in enumerate(tasks, 1):
        print(f"\n{'#' * 60}")
        print(f"# TASK {i}")
        print(f"{'#' * 60}")
        result = run_agent(task, verbose=True)
        print(f"\nFINAL ANSWER: {result}")
        print()


if __name__ == "__main__":
    print(f"Model  : {MODEL}")
    print(f"Tools  : {list(TOOLS.keys())}")
    print(f"Max steps per task: {MAX_STEPS}")
    run_all_tasks()
