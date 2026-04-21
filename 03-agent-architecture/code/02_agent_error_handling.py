"""
Agent Error Handling — Phase 3
Deliberately breaks tools and shows how the agent responds.
Tests four failure scenarios:
  1. Tool not found
  2. Tool returns an error
  3. Tool times out (simulated)
  4. Tool returns unexpected format
"""

import requests
import re
import time

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:26b"
MAX_STEPS = 6


# -------------------------------------------------------------------
# TOOLS — including broken ones
# -------------------------------------------------------------------

def calculator(expression: str) -> str:
    allowed = set("0123456789+-*/()., ")
    if not all(c in allowed for c in expression):
        return f"Error: unsafe characters in expression '{expression}'"
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(round(float(result), 4))
    except Exception as e:
        return f"Error: {str(e)}"


def broken_database(query: str) -> str:
    """Simulates a database that always fails."""
    raise ConnectionError("Database connection refused: host unreachable")


def slow_api(query: str) -> str:
    """Simulates a slow API that times out."""
    time.sleep(2)
    return "timeout"


def bad_format_tool(query: str) -> str:
    """Returns data in an unexpected format."""
    return '{"data": null, "error": null, "status": 503, "retry_after": 30}'


def file_read(path: str) -> str:
    if not path.endswith((".txt", ".md")):
        return "Error: only .txt and .md files are supported"
    return "Error: file not found"


TOOLS_NORMAL = {
    "calculator": calculator,
    "file_read": file_read,
}

TOOLS_WITH_BROKEN = {
    "calculator": calculator,
    "database_lookup": broken_database,
    "stock_api": bad_format_tool,
    "file_read": file_read,
}


SYSTEM_PROMPT_TEMPLATE = """You are a helpful AI agent with access to tools.

Follow this exact format:

Thought: [your reasoning]
Action: tool_name(argument)
Observation: [result — filled in for you]

When done:
Final Answer: [your answer]

Available tools:
{tools}

Rules:
- If a tool returns an error, acknowledge it and try a different approach
- If all tools fail, say so clearly in your Final Answer
- Never make up results
- Always write a Thought before an Action
"""


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


def parse_action(text: str):
    match = re.search(r"Action:\s*(\w+)\(([^)]*)\)", text)
    if not match:
        return None
    return match.group(1).strip(), match.group(2).strip()


def run_agent(task: str, tools: dict, tool_descriptions: str, verbose: bool = True) -> str:
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(tools=tool_descriptions)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": task},
    ]

    if verbose:
        print(f"\nTask: {task}")
        print("=" * 60)

    for step in range(1, MAX_STEPS + 1):
        if verbose:
            print(f"\n[Step {step}]")

        response = call_llm(messages)
        messages.append({"role": "assistant", "content": response})

        if verbose:
            print(response)

        if "Final Answer:" in response:
            final = re.search(r"Final Answer:\s*(.+)", response, re.DOTALL)
            return final.group(1).strip() if final else response

        parsed = parse_action(response)
        if not parsed:
            break

        tool_name, argument = parsed

        if tool_name not in tools:
            observation = f"Error: tool '{tool_name}' does not exist. Available tools: {list(tools.keys())}"
        else:
            try:
                observation = tools[tool_name](argument)
            except Exception as e:
                observation = f"Error: {type(e).__name__}: {str(e)}"

        observation_text = f"Observation: {observation}"
        messages.append({"role": "assistant", "content": observation_text})

        if verbose:
            print(observation_text)

    return "Agent stopped without a final answer."


def separator(title: str) -> None:
    print(f"\n{'#' * 60}")
    print(f"# {title}")
    print(f"{'#' * 60}")


# -------------------------------------------------------------------
# SCENARIO 1: Agent calls a tool that doesn't exist
# -------------------------------------------------------------------

def scenario_nonexistent_tool():
    separator("Scenario 1: Agent Calls a Non-Existent Tool")

    tools = {"calculator": calculator}
    tool_desc = "- calculator(expression) → evaluates math. Example: calculator(10 * 5)"

    task = "Look up the weather in London using the weather_api tool, then tell me if I need an umbrella."

    result = run_agent(task, tools, tool_desc)
    print(f"\nFINAL: {result}")


# -------------------------------------------------------------------
# SCENARIO 2: Tool raises an exception
# -------------------------------------------------------------------

def scenario_tool_exception():
    separator("Scenario 2: Tool Raises an Exception")

    tools = {
        "calculator": calculator,
        "database_lookup": broken_database,
    }
    tool_desc = """- calculator(expression) → evaluates math
- database_lookup(query) → queries the customer database"""

    task = "Look up the order status for customer ID 12345 in the database."

    result = run_agent(task, tools, tool_desc)
    print(f"\nFINAL: {result}")


# -------------------------------------------------------------------
# SCENARIO 3: Tool returns an error string (not an exception)
# -------------------------------------------------------------------

def scenario_tool_error_string():
    separator("Scenario 3: Tool Returns Error String")

    tools = {
        "calculator": calculator,
        "stock_api": bad_format_tool,
    }
    tool_desc = """- calculator(expression) → evaluates math
- stock_api(ticker) → returns current stock price"""

    task = "What is the current price of AAPL stock?"

    result = run_agent(task, tools, tool_desc)
    print(f"\nFINAL: {result}")


# -------------------------------------------------------------------
# SCENARIO 4: Agent recovers and uses fallback
# -------------------------------------------------------------------

def scenario_recovery_with_fallback():
    separator("Scenario 4: Agent Recovers Using a Fallback Tool")

    tools = {
        "calculator": calculator,
        "database_lookup": broken_database,
        "file_read": file_read,
    }
    tool_desc = """- calculator(expression) → evaluates math
- database_lookup(query) → queries the live database (may be unavailable)
- file_read(path) → reads a local file as fallback"""

    task = (
        "Get the price of Product X from the database. "
        "If the database is unavailable, check the file at /tmp/prices.txt"
    )

    result = run_agent(task, tools, tool_desc)
    print(f"\nFINAL: {result}")


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Model     : {MODEL}")
    print(f"Max steps : {MAX_STEPS}")
    print("\nTesting agent behaviour under various failure conditions.\n")

    scenario_nonexistent_tool()
    scenario_tool_exception()
    scenario_tool_error_string()
    scenario_recovery_with_fallback()

    print(f"\n{'=' * 60}")
    print("  Error handling experiments complete.")
    print(f"{'=' * 60}\n")
