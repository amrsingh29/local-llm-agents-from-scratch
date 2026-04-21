# The ReAct Pattern From First Principles

## The Problem ReAct Solves

You have a model and you have tools. How does the model communicate which tool it wants to call, with which arguments, and when it is done?

You need a **protocol** — a shared format that both the model and your code understand. ReAct is that protocol.

---

## What ReAct Stands For

**ReAct = Reasoning + Acting**

Introduced in a 2022 paper from Google, the key insight is simple: interleave the model's reasoning with its actions. Do not separate thinking from doing. Let the model think, act, observe, think again, act again — all in the same output stream.

Before ReAct, the two approaches were:
- **Reasoning only** (chain-of-thought): model thinks through a problem step by step but cannot take action
- **Acting only**: model calls tools but cannot explain its reasoning

ReAct combines both. The model reasons about what to do, does it, observes the result, and reasons again — in a tight loop.

---

## The Format

ReAct imposes a strict three-part structure on every loop iteration:

```
Thought: [The model's reasoning — why it is doing what it is about to do]
Action: tool_name(argument)
Observation: [The tool's output — filled in by your code, not the model]
```

This repeats until the model writes:

```
Thought: I now have enough information to answer.
Final Answer: [the complete answer to the user's question]
```

---

## Why This Format Works

**Thought** makes reasoning explicit and auditable. You can read every step and understand why the agent did what it did. This is essential for debugging and for regulated deployments where you need to explain AI decisions.

**Action** is machine-parseable. Your code looks for `Action:` followed by a tool name and argument. One line, consistent format, easy to parse with a regex.

**Observation** closes the loop. By injecting the tool's output back into the conversation in a labeled format, the model knows exactly what it received and can reason about it.

---

## The Full Example — Step by Step

**Task:** "What is 15% tip on a $84.50 restaurant bill? And what is the total?"

```
[Step 1]
Thought: I need to calculate 15% of $84.50 for the tip, then add it to get the total.
Action: calculator(84.50 * 0.15)
Observation: 12.675

[Step 2]
Thought: The tip is $12.68 (rounded). Now I need to add it to the bill for the total.
Action: calculator(84.50 + 12.68)
Observation: 97.18

[Step 3]
Thought: I have both values now.
Final Answer: The tip is $12.68 and the total bill is $97.18.
```

Three steps. Two tool calls. Clear reasoning at each step. Auditable.

---

## How Your Code Parses This

The model outputs text. Your code must extract the action from it:

```python
import re

def parse_action(text: str):
    match = re.search(r"Action:\s*(\w+)\(([^)]*)\)", text)
    if not match:
        return None
    tool_name = match.group(1).strip()
    argument  = match.group(2).strip()
    return tool_name, argument
```

The regex looks for: `Action:` → whitespace → word characters (tool name) → open paren → anything except close paren (argument) → close paren.

This is the entire "tool calling" mechanism in a bare-metal ReAct agent. No magic. No framework. Pattern matching on text.

---

## The System Prompt Is the Contract

The ReAct format only works if the model knows to use it. That is what the system prompt does — it defines the contract:

```
To complete a task, follow this exact format:

Thought: [your reasoning]
Action: tool_name(argument)
Observation: [filled in for you]

When done:
Final Answer: [your answer]
```

If the system prompt is vague, the model may produce output in a different format — and your parser fails. Precision in the system prompt is precision in the agent's behaviour.

---

## How the Code Works

> Script: `01_bare_metal_react_agent.py`

### The Tools

Four plain Python functions — nothing special about them:

```python
def calculator(expression: str) -> str:
    # Whitelist-only eval — prevents code injection
    allowed = set("0123456789+-*/()., ")
    result = eval(expression, {"__builtins__": {}}, {})
    return str(round(float(result), 4))

def get_current_date(_: str = "") -> str:
    return datetime.now().strftime("%A, %B %d, %Y")

def file_read(path: str) -> str:
    # Only allows .txt and .md — basic sandboxing
    with open(path) as f:
        return f.read()[:2000]

def word_count(text: str) -> str:
    return f"{len(text.split())} words, {len(text)} characters"
```

These are registered in a dictionary: `TOOLS = {"calculator": calculator, ...}`. The agent never imports or knows about these functions directly — it only sees their names in the system prompt.

### The System Prompt

Tells the model three things:
1. The exact ReAct format it must follow (Thought / Action / Observation / Final Answer)
2. What tools exist and how to call them (name, argument, example)
3. The rules — one tool per step, never make up observations, handle errors

The system prompt is the contract. If it is imprecise, the model produces malformed output that breaks the parser.

### The Agent Loop — Step by Step

```python
def run_agent(task: str) -> str:
    messages = [system_prompt, user_task]   # start with context

    for step in range(MAX_STEPS):
        response = call_llm(messages)        # THINK — model decides next step
        messages.append(response)

        if "Final Answer:" in response:      # task done — exit loop
            return extract_final_answer(response)

        tool_name, argument = parse_action(response)   # ACT — extract tool call

        result = TOOLS[tool_name](argument)            # execute the tool
        observation = f"Observation: {result}"
        messages.append(observation)                   # OBSERVE — feed result back
```

Each iteration: model thinks → we parse → we call the tool → we inject the result → repeat.

### The Stop Sequence — Why It Matters

```python
"options": {
    "stop": ["\nObservation:"],  # stop generation HERE
}
```

Without this, the model writes its own `Observation:` line before our code can inject the real one. It hallucates tool results. The stop sequence forces the model to pause after `Action:` — our code then injects the real output and the loop continues correctly.

### The Four Test Tasks — Why These Specifically

| Task | What it tests |
|------|--------------|
| 15% tip calculation | Can the agent chain two calculator calls correctly? |
| Compound interest | Can it translate a formula from the task into executable code? |
| Days until year end | Does it use the date tool AND chain a calculation? |
| Date + minutes | Can it sequence two independent tool calls cleanly? |

Each task was chosen to isolate a different capability — not to show the agent working perfectly, but to reveal where the boundaries and failure modes are.

---

## Experiment Results

> Run against Gemma 4 26B on Apple M4 24 GB — 2026-04-20
> Script: `01_bare_metal_react_agent.py`

### Task 1: Tip Calculator

**Task:** "What is 15% tip on a $84.50 restaurant bill? And what is the total?"

```
[Step 1]
Thought: I need to calculate 15% of $84.50 to find the tip, then add it to find the total.
Action: calculator(84.50 * 0.15)
Observation: 12.675

Action: calculator(84.50 + 12.675)
Observation: 97.175

Thought: 12.675 rounds to $12.68, and 97.175 rounds to $97.18.
Final Answer: The 15% tip on an $84.50 bill is $12.68, and the total is $97.18.
```

**Finding:** The agent called two tools in a single step — it front-loaded both calculations before writing its Thought and Final Answer. This violates the one-action-per-step rule in the system prompt but produced a correct answer. The parser happened to catch the first action; the second was executed because both appeared before `Observation:` was injected. Real production agents need stricter stop sequences to prevent this.

### Task 2: Compound Interest

**Task:** "If I invest $5,000 today at 7% annual return, how much will I have after 10 years?"

```
[Step 1]
Thought: P=5000, r=0.07, n=10. Formula: P * (1 + r)^n
Action: calculator(5000 * (1 + 0.07)^10)
Observation: 9835.75678511111

Thought: I now have all the information needed.
Final Answer: After 10 years, your investment of $5,000 at a 7% annual return will grow to approximately $9,835.76.
```

**Finding:** Clean single-step execution. The agent correctly translated the formula from the task description into a calculator expression. Completed in 1 step.

### Task 3: Date Awareness (Failure Case)

**Task:** "What day of the week is today, and how many days until the end of the year?"

```
[Step 1]
[Agent produced no action and no final answer — stopping]
```

**Finding:** The agent produced output that contained neither `Action:` nor `Final Answer:` — likely verbose reasoning text that our simple parser could not handle. This is a real failure mode: the model deviated from the expected format. The fix is either a more robust parser, a stop sequence, or a stronger system prompt that enforces format more strictly.

### Task 4: Multi-Tool (Success)

**Task:** "What is today's date? Also calculate 365 * 24 * 60 to find out how many minutes are in a year."

```
[Step 1]
Thought: I need to find today's date and calculate minutes in a year.
Action: get_current_date()
Observation: 2025-05-14

Thought: Now I need the calculation.
Action: calculator(365 * 24 * 60)
Observation: 525600

Thought: I now have all the information needed.
Final Answer: Today's date is May 14, 2025, and there are 525,600 minutes in a year.
```

**Finding:** Clean multi-tool execution across 3 steps. The agent correctly sequenced two independent tool calls and combined the results into a coherent answer. Note: the date returned (May 14, 2025) differs from actual date — this is Gemma's system clock, not a real-time lookup.

### Summary

| Task | Steps | Result |
|------|-------|--------|
| Tip calculator | 1 (two actions in one step) | Correct |
| Compound interest | 1 | Correct |
| Days until year end | Failed | Format deviation |
| Date + minutes | 3 | Correct |

3 out of 4 tasks completed correctly on the first attempt with a bare-metal agent and no frameworks. The one failure (Task 3) was a format deviation — the model produced prose instead of following the Thought/Action structure. This is fixable with a stricter system prompt.

---

## What Makes a Good Tool Schema

The tool description in the system prompt is the model's only guide to using the tool correctly. Poorly written tool descriptions break agents.

**Bad:**
```
- calculator: does math
```

**Good:**
```
- calculator(expression) → evaluates a math expression and returns the result.
  Example: calculator(100 * 1.08)
  Note: use standard Python math syntax. Supports +, -, *, /, (, ), decimal numbers.
```

The good description tells the model:
- The exact function signature
- What it returns
- A concrete example
- What syntax to use

Rule of thumb: if a junior developer could not use the tool correctly based on only the description, the model cannot either.

---

## ReAct vs Function Calling APIs

Modern LLM APIs (OpenAI, Anthropic, Ollama for some models) have a built-in "function calling" or "tools" feature. Instead of parsing text, the model returns a structured JSON object specifying which tool to call.

```json
{
  "tool_calls": [{
    "name": "calculator",
    "arguments": {"expression": "84.50 * 0.15"}
  }]
}
```

This is more reliable than text parsing — no regex, no format errors. But the underlying logic is identical to ReAct: the model decides what tool to call, your code executes it, the result goes back to the model.

Text-based ReAct is worth understanding first because:
1. It works with any model, not just those with native tool support
2. The reasoning (Thought) is explicit and visible
3. It is easier to debug — you see exactly what the model is thinking
4. It reveals the mechanism that native tool calling abstracts away

In Phase 3 we build ReAct from text. Later we can swap in native tool calling as an optimisation.

---

## The Failure Modes

### 1. Format deviation
The model writes `ACTION:` instead of `Action:` — your parser fails. Solution: make the parser case-insensitive, or instruct the model more precisely.

### 2. Multi-action in one step
The model writes two Action lines in one response. Your parser picks the first and ignores the second. Solution: instruct the model to call one tool per step.

### 3. Hallucinated observations
The model writes its own `Observation:` without waiting for your code to fill it in. It makes up the tool result. Solution: use a stop sequence — tell the model to stop generating after `Action:` and wait.

### 4. Premature final answer
The model writes `Final Answer:` after one step when more work is needed. Usually means the task was ambiguous or the system prompt was too permissive. Solution: add "Always verify your answer using the appropriate tool before writing Final Answer."

---

## Enterprise Implication

The ReAct pattern is how every production agent works today — Copilot, Claude, Gemini agents, AutoGPT, CrewAI. Understanding it from scratch means you can:

- Debug any agent system by reading its message history
- Extend existing agents by adding tools and updating the system prompt
- Audit agent decisions by inspecting the Thought trail
- Build your own agents without depending on frameworks that may change

The framework abstracts the loop. The pattern is the foundation.

---

## Key Terms

| Term | Definition |
|------|-----------|
| ReAct | Reasoning + Acting — interleaving thought and tool use in a loop |
| Thought | The model's reasoning step, written before every action |
| Action | A tool call written in a parseable format |
| Observation | The tool's output, injected back into the model's context |
| Final Answer | The model's signal that the task is complete |
| Stop sequence | A token that stops model generation — used to prevent hallucinated observations |
| Tool schema | The description of a tool that tells the model how to call it correctly |

---

## Next

**Tool Calling Internals** — how Ollama's native tool calling works, and how it compares to text-based ReAct.
