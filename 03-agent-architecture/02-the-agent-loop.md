# The Agent Loop

## The Core Pattern

Every agent — regardless of framework, language, or model — runs the same fundamental loop:

```
┌─────────────────────────────────────────┐
│                                         │
│   PERCEIVE → THINK → ACT → OBSERVE     │
│        ↑__________________________|     │
│                                         │
└─────────────────────────────────────────┘
```

This loop runs repeatedly until the agent decides the task is complete. Understanding this loop at the code level is the difference between using agent frameworks and being able to build, debug, and extend them.

---

## Each Step in Detail

### 1. PERCEIVE — Read the Environment

The agent reads its current state:
- The original task from the user
- All previous thoughts, actions, and observations
- Any context injected by the system (documents, memory, instructions)

In code, this is simply building the message list that gets sent to the LLM:

```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user",   "content": original_task},
    # All previous turns in the loop:
    {"role": "assistant", "content": "Thought: I need to look up the stock price..."},
    {"role": "assistant", "content": "Action: stock_lookup(AAPL)"},
    {"role": "assistant", "content": "Observation: AAPL = $189.50"},
    # ... and so on
]
```

The agent has no memory — as we proved in Phase 2. Everything it "knows" is in the message list it receives on each loop iteration.

### 2. THINK — Reason About What to Do Next

The LLM reads the full context and produces the next step. This is where the intelligence lives.

The model might output:
- "I should call the calculator tool with 189.50 * 50"
- "I have enough information to answer. The final answer is $9,475."
- "The stock lookup failed. I should try a different approach."

The key: **the model decides what happens next**. The developer does not pre-program the sequence.

### 3. ACT — Execute the Decision

The agent parses the model's output and executes the action:
- If the model wants to call a tool → call it
- If the model says the task is done → return the final answer
- If the model is confused → ask for clarification or fail gracefully

```python
if "Action:" in model_output:
    tool_name, args = parse_action(model_output)
    result = tools[tool_name](**args)
elif "Final Answer:" in model_output:
    return extract_final_answer(model_output)
```

### 4. OBSERVE — Feed the Result Back

The tool's output becomes the next input to the LLM:

```python
messages.append({
    "role": "assistant",
    "content": f"Observation: {result}"
})
```

The loop restarts. The model now sees the observation and decides its next move.

---

## The Loop in Code — Skeleton

```python
def run_agent(task: str, tools: dict, max_steps: int = 10) -> str:
    messages = [
        {"role": "system", "content": build_system_prompt(tools)},
        {"role": "user",   "content": task},
    ]

    for step in range(max_steps):
        # THINK
        response = call_llm(messages)
        messages.append({"role": "assistant", "content": response})

        # Check for final answer
        if "Final Answer:" in response:
            return extract_final_answer(response)

        # ACT
        if "Action:" in response:
            tool_name, args = parse_action(response)

            # OBSERVE
            try:
                result = tools[tool_name](**args)
                observation = f"Observation: {result}"
            except Exception as e:
                observation = f"Observation: Error — {str(e)}"

            messages.append({"role": "assistant", "content": observation})

    return "Agent reached maximum steps without completing the task."
```

This is the entire agent loop. Everything else — memory, planning, multi-agent coordination — is built on top of this skeleton.

---

## The System Prompt Is the Agent's Identity

The system prompt tells the agent:
1. What tools it has and how to use them
2. The format it must follow (Thought / Action / Observation)
3. When to stop
4. How to handle errors

A typical ReAct agent system prompt:

```
You are an agent with access to the following tools:

- calculator(expression: str) → evaluates a math expression, returns result
- stock_lookup(ticker: str) → returns current stock price
- file_read(path: str) → reads a file and returns its contents

To use a tool, write:
Thought: [your reasoning]
Action: tool_name(argument)

When you have the final answer, write:
Final Answer: [your answer]

Never make up tool results. If a tool fails, say so and try a different approach.
```

The format (Thought / Action / Observation) is the ReAct pattern — covered in detail in the next note.

---

## The Termination Problem

The loop must end. There are three ways:

**1. Final Answer** — the model decides it has completed the task and outputs "Final Answer:"

**2. Max steps** — a hard limit prevents infinite loops. If the agent has not finished in N steps, stop and return an error. This is critical — without it, a confused agent runs forever and burns tokens.

**3. Error** — a tool fails in an unrecoverable way, or the model produces output that cannot be parsed.

Always set a `max_steps` limit. In production, also set a timeout and a token budget.

---

## What Can Go Wrong

### Hallucinated tool calls
The model outputs `Action: stock_lookup(APPL)` (typo). The tool does not exist. The agent must handle the error gracefully, not crash.

### Infinite loops
The model keeps calling the same tool with the same arguments, getting the same result, and not making progress. Max steps prevents this.

### Premature termination
The model outputs "Final Answer:" before it actually has enough information. Usually caused by insufficient context in the system prompt or ambiguous task.

### Observation ignored
The model calls a tool, gets the result, then ignores it and calls the same tool again. This happens when the observation format is inconsistent and the model does not recognize it.

All of these failure modes are visible in the message history — which is why logging every step of the agent loop is non-negotiable in production.

---

## Enterprise Implication

The agent loop is the audit trail.

Every enterprise AI deployment in regulated industries needs to answer: "What did the AI do and why?" The message history of an agent loop is the answer — every thought, every action, every observation, in order.

This is not incidental. Design your agent loop so that the full message history is logged, stored, and queryable. The loop is not just computation — it is the compliance record.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Agent loop | The perceive → think → act → observe cycle that runs until task completion |
| Tool | A function the agent can call to interact with the world |
| Observation | The result of a tool call, fed back into the model's context |
| Max steps | Hard limit on loop iterations to prevent infinite loops |
| Termination | The condition under which the loop exits (final answer, max steps, error) |
| Audit trail | The full message history of an agent run — every thought and action logged |

---


## Full Code

```python title="01_bare_metal_react_agent.py"
--8<-- "03-agent-architecture/code/01_bare_metal_react_agent.py"
```

## Next

**The ReAct Pattern** — the specific thought/action/observation format that makes agent output parseable, and why this particular structure works so well.
