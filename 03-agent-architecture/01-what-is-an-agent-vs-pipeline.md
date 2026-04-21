# What Is an Agent vs a Pipeline vs a Chatbot

## Three Things People Call "AI" — Only One Is an Agent

The industry uses the word "agent" loosely. Before building one, you need a precise definition — because the architecture is fundamentally different depending on which thing you are actually building.

---

## The Chatbot

A chatbot takes a user message and returns a response. That is all.

```
User message → [LLM] → Response
```

No tools. No decisions. No loops. One call, one answer.

**Example:** "What is the capital of France?" → "Paris."

A chatbot is stateless (as we proved in Phase 2), has no ability to take action in the world, and can only respond with text. Most of what people call "AI assistants" in consumer apps are chatbots with conversation history — nothing more.

---

## The Pipeline

A pipeline is a fixed sequence of steps. Each step takes input and produces output for the next step. The sequence is defined in advance and never changes.

```
Step 1: Extract keywords from document
     ↓
Step 2: Search database for each keyword
     ↓
Step 3: Rank results by relevance
     ↓
Step 4: Summarize top 3 results
     ↓
Output
```

A pipeline can use an LLM at each step, but the LLM does not decide what happens next. The developer decided that in advance. The LLM is a function call, not a decision-maker.

**Example:** A document processing pipeline that always extracts → searches → ranks → summarizes, regardless of the document content.

**The failure mode:** pipelines break on anything non-linear. What if step 2 returns no results? What if the document needs a different approach? A pipeline has no way to adapt — it follows its fixed path to a bad output or crashes.

---

## The Agent

An agent is a system that:
1. **Perceives** its environment (reads input, tool outputs, context)
2. **Decides** what to do next (using an LLM to reason)
3. **Acts** (calls a tool, writes a file, sends a message)
4. **Observes** the result
5. **Repeats** until the task is complete

The key difference: **the agent decides the sequence of steps at runtime**, not the developer at design time.

```
User task → [LLM decides: what tool do I need?]
                    ↓
              [Tool call]
                    ↓
              [Observe result]
                    ↓
              [LLM decides: is the task done? what next?]
                    ↓
              [Another tool call or final answer]
```

The same agent given a simple task might complete it in 2 steps. Given a complex task, it might take 10 steps, backtrack, try a different approach, and ask for clarification. A pipeline cannot do any of this.

---

## The Conceptual Difference — Stock Price Example

**Task:** "Find the current price of Apple stock and calculate how much 50 shares would cost."

**Pipeline approach:**
```
Step 1: Call stock API → get AAPL price ($189.50)
Step 2: Multiply by 50 → $9,475
Step 3: Format response
```

This works — if the task is always exactly this. But what if the user asks "What about Apple and Microsoft?"? The pipeline fails. It was not designed for two stocks.

**Agent approach:**
```
LLM reads task: "I need to look up a stock price and do math."
LLM decides: call stock_lookup("AAPL")
Observes: $189.50
LLM decides: call calculator(189.50 * 50)
Observes: $9,475
LLM decides: task complete, return answer.

[User asks "What about Apple and Microsoft?"]

LLM reads new task: "Two stocks this time."
LLM decides: call stock_lookup("AAPL"), then stock_lookup("MSFT")
Observes both prices
LLM decides: call calculator for each
Observes results
LLM decides: format both results, return answer.
```

The agent handled the variation without any code change. The pipeline would need a rewrite.

---

## The Spectrum

```
Chatbot → RAG Chatbot → Pipeline → Simple Agent → Multi-Agent System
  (no tools)  (one tool)  (fixed)   (dynamic)      (multiple agents)
```

Where does your system sit? Most "AI automation" projects that fail are pipelines pretending to be agents — they work on the demo cases, break on edge cases, and cannot recover.

---

## Experiment: Same Task, Three Scenarios

> Run against Gemma 4 26B on Apple M4 24 GB — 2026-04-20
> Script: `03_pipeline_vs_agent.py`

The clearest way to see the difference is to run the same task through both architectures and watch what happens when things go wrong.

**Task:** "Find the price of Product X from our data sources and calculate the total cost including 15% tax."

**Data sources:** a local file (primary) and a database (fallback).

**Three scenarios:**
- A: File exists — happy path
- B: File missing — fallback required
- C: File missing and database down — total failure

### How the Pipeline Is Written

Every decision is hardcoded by the developer in advance:

```python
def run_pipeline(task: str) -> str:
    price = None

    # Step 1: Try the file (hardcoded path)
    file_result = file_read("/tmp/product_prices.txt")
    if not file_result.startswith("Error"):
        price = float(file_result.split(":")[-1].strip())

    # Step 2: If file failed, try database (hardcoded fallback)
    if price is None:
        try:
            db_result = database_lookup("price of Product X")
            price = float(db_result.split(":")[-1].strip())
        except Exception as e:
            pass  # database also failed

    # Step 3: Calculate with tax (hardcoded formula)
    if price is None:
        return "Pipeline failed: could not retrieve price from any source."
    total = price * 1.15
    return f"Price: ${price:.2f}, Tax (15%): ${price * 0.15:.2f}, Total: ${total:.2f}"
```

The pipeline is a decision tree baked into Python. Every branch is written by hand. Add a third data source, a new fallback condition, or a different output format — and you rewrite the pipeline.

### How the Agent Is Written

The developer registers tools. The model decides the sequence at runtime:

```python
TOOLS = {
    "file_read": file_read,
    "database_lookup": database_lookup,
    "calculator": calculator,
}
# System prompt describes what each tool does.
# The agent decides which tool to call, and when, based on what it observes.
```

The developer does not write "if file fails, try database." The developer writes the tools and describes them. The model reads the descriptions and chooses.

---

### Scenario A: Happy Path — File Exists

**Setup:** `/tmp/product_prices.txt` contains `Product X: 89.99`. Database available.

**Pipeline:**
```
Step 1: Read price from file
  Result: Product X: 89.99, Parsed price: 89.99

Step 3: Calculate total with 15% tax
  Price: $89.99, Tax (15%): $13.50, Total: $103.49
```

**Agent:**
```
[Step 1]
Thought: I need to find the price of Product X. I will use database_lookup.
Action: database_lookup(query="Product X")
Observation: Product X price: 89.99

[Step 2]
Thought: I have the price. Now calculate total with 15% tax.
Action: calculator(89.99 * 1.15)
Observation: 103.4885

[Step 3]
Final Answer: The price of Product X is 89.99, and the total cost including 15% tax is 103.49.
```

**Finding:** Both arrive at the correct answer. The pipeline followed its hardcoded sequence (file first). The agent chose the database first — a different path, same result. Both correct on the happy path.

---

### Scenario B: Primary Fails — File Missing, Database Works

**Setup:** File does not exist. Database available.

**Pipeline:**
```
Step 1: Read price from file
  Result: Error: file not found at '/tmp/product_prices.txt'

Step 2: File unavailable — querying database
  Result: Product X price: 89.99, Parsed price: 89.99

Step 3: Price: $89.99, Tax (15%): $13.50, Total: $103.49
```

**Agent:**
```
[Step 1]
Action: database_lookup(query="Product X")
Observation: Product X price: 89.99

[Step 2]
Action: calculator(89.99 * 1.15)
Observation: 103.4885

[Step 3]
Final Answer: The price of Product X is 89.99, total including 15% tax is 103.49.
```

**Finding:** Both correct. The pipeline's hardcoded fallback worked exactly as designed. The agent went directly to the database — it had no instruction to try the file first.

---

### Scenario C: All Sources Fail — File Missing, Database Down

**Setup:** File does not exist. Database raises `ConnectionError`.

**Pipeline:**
```
Step 1: Read price from file
  Result: Error: file not found

Step 2: File unavailable — querying database
  Database error: Database connection refused: host unreachable

Step 3: No price available — cannot calculate

FINAL: Pipeline failed: could not retrieve price from any source.
```

**Agent:**
```
[Step 1]
Action: database_lookup(query="Product X")
Observation: Error: ConnectionError: Database connection refused: host unreachable

[Step 2]
Thought: The database lookup failed. I have no other data sources available.

Final Answer: I am unable to find the price of Product X because the database
              connection failed. Therefore, I cannot calculate the total cost.
```

**Finding:** Both correctly report failure. Neither invents a price. The pipeline's pre-written error path handled total failure — because the developer anticipated it. The agent reasoned to the same conclusion dynamically — without any pre-written "what to do if everything fails" code.

---

### Results Summary

| Scenario | Pipeline | Agent |
|----------|---------|-------|
| Happy path | Correct | Correct |
| Primary source fails | Correct (hardcoded fallback) | Correct (dynamic) |
| All sources fail | Correct (hardcoded error) | Correct (reasoned to failure) |

Both architectures produced identical outcomes on every scenario.

---

## Then Why Use an Agent?

The results look the same. So why does the distinction matter?

**The pipeline hardcodes everything the developer anticipated.** It works perfectly for scenarios A, B, and C because those were written into the code. Add a scenario D — a fourth data source, a cache layer, a different error condition, a reformatted response — and you open the pipeline code and add another branch.

**The agent reasons about what it has.** It did not need separate code for each scenario. It read the tool descriptions, called tools, and made decisions based on what it observed. Add a fourth data source: update the system prompt with the new tool description, register the function. The agent discovers it and uses it when appropriate.

The table of results conceals the real difference — not in outcomes on known scenarios, but in what happens when reality diverges from the developer's assumptions.

The practical threshold: **if you find yourself writing more than 3-4 nested if/else branches in a pipeline, you probably need an agent.**

---

## When to Use Each

| Dimension | Pipeline | Agent |
|-----------|---------|-------|
| Predictability | Every run follows the same path | Path varies — harder to audit |
| Latency | No LLM inference overhead in the logic layer | Each reasoning step costs inference time |
| Cost | Zero LLM tokens for the orchestration | Token cost per reasoning step |
| Debuggability | Read the code, see the path | Read the message history, trace reasoning |
| Reliability | Deterministic | Model can deviate from expected reasoning |
| Handles variation | No | Yes |
| Handles failure | Only anticipated failures | Can reason about unanticipated failures |

**Use a pipeline when:** the task is well-defined, always follows the same structure, and cost/latency predictability matters.

**Use an agent when:** the task is open-ended, requires dynamic decision-making, or the path to completion cannot be known in advance.

Most production AI systems are hybrid: a fixed outer pipeline with one or more agent steps inside for the parts that require dynamic reasoning.

---

## Enterprise Implication

Most enterprise AI systems start as pipelines — because the task is well-defined, the scenarios are known, and pipelines are easier to audit. The business understands what will happen at every step.

The difference between a pipeline and an agent is the difference between:
- A script that runs your monthly report (pipeline)
- An assistant that investigates a support ticket, decides what to look up, tries different approaches, and escalates when stuck (agent)

Enterprises already have pipelines — they are called ETL jobs, workflows, and scripts. What they cannot build with pipelines is autonomous work.

As requirements evolve — new data sources, new edge cases, new user needs — pipelines accumulate branches. At some point the branching logic becomes more complex than the underlying task. That is when teams switch to agent-based orchestration. Understanding both architectures means you can make that switch deliberately, rather than discovering you need it after the pipeline has grown too complex to maintain.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Chatbot | Takes a message, returns a response. No tools, no decisions, no loops. |
| Pipeline | Fixed sequence of steps defined at design time. LLM is a function call, not a decision-maker. |
| Agent | System that perceives, decides, acts, and observes in a loop until a task is complete. |
| Tool | Any function the agent can call to interact with the world (API, calculator, file system, etc.) |
| Autonomy | The degree to which the agent decides its own next steps vs following pre-defined logic |
| Hardcoded fallback | A pre-written alternative path that executes when the primary path fails |
| Dynamic fallback | A fallback the agent discovers and chooses at runtime based on observed errors |
| Orchestration logic | The code (or reasoning) that decides what to do next — the core of both pipelines and agents |

---


## Full Code

```python title="03_pipeline_vs_agent.py"
--8<-- "03-agent-architecture/code/03_pipeline_vs_agent.py"
```

## Next

**The Agent Loop** — the perceive → think → act → observe cycle that underlies every agent, and how it maps to actual code.
