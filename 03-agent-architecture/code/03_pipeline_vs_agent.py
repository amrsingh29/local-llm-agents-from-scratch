"""
Pipeline vs Agent Comparison — Phase 3

Runs the same task through two architectures:
  1. Pipeline — fixed, hardcoded steps
  2. Agent    — dynamic ReAct loop

Task: "Find the price of Product X and calculate the total cost with 15% tax."

The comparison uses three scenarios:
  A. Happy path       — file exists, price readable, calculation clean
  B. Primary fails    — file missing, database fallback required
  C. Both fail        — file missing, database down, no data available

The pipeline must anticipate every scenario in advance and hardcode the response.
The agent discovers what to do at runtime based on what it observes.
"""

import requests
import re
import os
import time

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:26b"
MAX_STEPS = 8

# -------------------------------------------------------------------
# SHARED TOOLS
# Identical functions used by both pipeline and agent.
# The difference is in how they are orchestrated — not what they do.
# -------------------------------------------------------------------

def file_read(path: str) -> str:
    if not path.endswith((".txt", ".md")):
        return "Error: only .txt and .md files are supported"
    if not os.path.exists(path):
        return f"Error: file not found at '{path}'"
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception as e:
        return f"Error reading file: {str(e)}"


def database_lookup(query: str) -> str:
    """Simulates a database — can be configured to work or fail."""
    if DATABASE_DOWN:
        raise ConnectionError("Database connection refused: host unreachable")
    # Simulated response when database is up
    return "Product X price: 89.99"


def calculator(expression: str) -> str:
    allowed = set("0123456789+-*/()., ")
    if not all(c in allowed for c in expression):
        return f"Error: unsafe characters in '{expression}'"
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(round(float(result), 4))
    except Exception as e:
        return f"Error: {str(e)}"


# Scenario control flags — toggled per scenario
DATABASE_DOWN = False


# -------------------------------------------------------------------
# ARCHITECTURE 1: PIPELINE
# Fixed, sequential steps written in advance by the developer.
# Every decision is hardcoded. No runtime reasoning.
# -------------------------------------------------------------------

def run_pipeline(task: str, verbose: bool = True) -> str:
    """
    Fixed pipeline for the price-lookup-and-tax task.

    The developer has anticipated two possible situations:
      - File exists: read price from file
      - File missing: fall back to database

    Any situation outside these two breaks the pipeline.
    """
    if verbose:
        print("\n[PIPELINE]")
        print(f"Task: {task}")
        print("-" * 50)

    price = None

    # Step 1: Try the file (hardcoded path)
    if verbose:
        print("\nStep 1: Read price from file")
    file_result = file_read("/tmp/product_prices.txt")
    if verbose:
        print(f"  Result: {file_result}")

    if not file_result.startswith("Error"):
        # Parse the price — pipeline assumes a fixed format
        try:
            price = float(file_result.split(":")[-1].strip())
            if verbose:
                print(f"  Parsed price: {price}")
        except ValueError:
            if verbose:
                print("  Could not parse price from file content")

    # Step 2: If file failed, try the database (hardcoded fallback)
    if price is None:
        if verbose:
            print("\nStep 2: File unavailable — querying database")
        try:
            db_result = database_lookup("price of Product X")
            if verbose:
                print(f"  Result: {db_result}")
            # Parse the price — pipeline assumes another fixed format
            try:
                price = float(db_result.split(":")[-1].strip())
                if verbose:
                    print(f"  Parsed price: {price}")
            except ValueError:
                if verbose:
                    print("  Could not parse price from database response")
        except Exception as e:
            if verbose:
                print(f"  Database error: {e}")

    # Step 3: Calculate total with tax (hardcoded formula)
    if price is None:
        result = "Pipeline failed: could not retrieve price from any source."
        if verbose:
            print(f"\nStep 3: No price available — cannot calculate")
        return result

    if verbose:
        print(f"\nStep 3: Calculate total with 15% tax")
    tax = price * 0.15
    total = price + tax
    calc_result = f"Price: ${price:.2f}, Tax (15%): ${tax:.2f}, Total: ${total:.2f}"
    if verbose:
        print(f"  {calc_result}")

    return calc_result


# -------------------------------------------------------------------
# ARCHITECTURE 2: AGENT
# Dynamic ReAct loop — reasons about what to do based on observations.
# -------------------------------------------------------------------

TOOLS = {
    "file_read": file_read,
    "database_lookup": database_lookup,
    "calculator": calculator,
}

SYSTEM_PROMPT = """You are a helpful AI agent with access to tools.

To complete a task, follow this exact format:

Thought: [your reasoning]
Action: tool_name(argument)
Observation: [filled in for you]

When done:
Final Answer: [your answer]

Available tools:
- file_read(path) → reads a .txt file and returns its contents
- database_lookup(query) → queries the product database
- calculator(expression) → evaluates a math expression. Example: calculator(89.99 * 1.15)

Rules:
- Always write a Thought before an Action
- If a tool returns an error, try an alternative approach
- If all sources fail, say so clearly in your Final Answer
- Never make up prices or results
"""


def call_llm(messages: list) -> str:
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 400,
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


def run_agent(task: str, verbose: bool = True) -> str:
    if verbose:
        print("\n[AGENT]")
        print(f"Task: {task}")
        print("-" * 50)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": task},
    ]

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
            if verbose:
                print("[No action parsed — stopping]")
            break

        tool_name, argument = parsed

        if tool_name not in TOOLS:
            observation = f"Error: unknown tool '{tool_name}'. Available: {list(TOOLS.keys())}"
        else:
            try:
                observation = TOOLS[tool_name](argument)
            except Exception as e:
                observation = f"Error: {type(e).__name__}: {str(e)}"

        observation_text = f"Observation: {observation}"
        messages.append({"role": "assistant", "content": observation_text})

        if verbose:
            print(observation_text)

    return "Agent reached max steps without completing the task."


# -------------------------------------------------------------------
# SCENARIOS
# -------------------------------------------------------------------

TASK = "Find the price of Product X from our data sources and calculate the total cost including 15% tax."


def separator(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def run_scenario(name: str, setup_fn):
    global DATABASE_DOWN
    separator(name)

    # Setup: create or remove test file, configure database
    DATABASE_DOWN = False
    setup_fn()

    print("\n--- PIPELINE ---")
    pipeline_result = run_pipeline(TASK)
    print(f"\nPIPELINE FINAL: {pipeline_result}")

    print("\n--- AGENT ---")
    agent_result = run_agent(TASK)
    print(f"\nAGENT FINAL: {agent_result}")

    # Cleanup
    if os.path.exists("/tmp/product_prices.txt"):
        os.remove("/tmp/product_prices.txt")


# Scenario A: File exists — happy path
def setup_happy_path():
    with open("/tmp/product_prices.txt", "w") as f:
        f.write("Product X: 89.99")
    print("Setup: /tmp/product_prices.txt created with price 89.99")
    print("Setup: Database available")


# Scenario B: File missing, database works
def setup_file_missing():
    global DATABASE_DOWN
    DATABASE_DOWN = False
    if os.path.exists("/tmp/product_prices.txt"):
        os.remove("/tmp/product_prices.txt")
    print("Setup: /tmp/product_prices.txt does NOT exist")
    print("Setup: Database available")


# Scenario C: File missing, database also down
def setup_all_fail():
    global DATABASE_DOWN
    DATABASE_DOWN = True
    if os.path.exists("/tmp/product_prices.txt"):
        os.remove("/tmp/product_prices.txt")
    print("Setup: /tmp/product_prices.txt does NOT exist")
    print("Setup: Database is DOWN")


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Model : {MODEL}")
    print(f"Task  : {TASK}")
    print(f"\nRunning same task through Pipeline and Agent under three scenarios.")
    print("Observation: which architecture handles failure gracefully?")

    run_scenario("Scenario A: Happy Path — File Exists", setup_happy_path)
    run_scenario("Scenario B: Primary Fails — File Missing, DB Works", setup_file_missing)
    run_scenario("Scenario C: All Sources Fail — File Missing, DB Down", setup_all_fail)

    print(f"\n{'=' * 60}")
    print("  Pipeline vs Agent comparison complete.")
    print(f"{'=' * 60}\n")
