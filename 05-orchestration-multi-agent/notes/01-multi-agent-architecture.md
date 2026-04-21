# Multi-Agent Architecture — Why One Agent Is Not Enough

## The Single Agent Failure Mode

In Phase 3, we built a ReAct agent that works well on focused tasks: look up a price, calculate a total, read a file. Give it a complex, multi-part task and it starts to break.

**Why?**

```
User: "Review our Q1 sales data, identify the top 3 underperforming regions,
       write a summary for the executive team, and suggest 3 actionable fixes
       for each region."
```

A single agent tackling this in one loop faces four problems:

### Problem 1 — Context Bloat

Each step of a long task fills the context window with intermediate results, tool outputs, and reasoning traces. By step 8, the model is working in a context that looks like:

```
[System prompt: 500 tokens]
[User task: 100 tokens]
[Step 1 thought + action: 200 tokens]
[Step 1 tool output: 800 tokens]   ← large data retrieval
[Step 2 thought + action: 200 tokens]
[Step 2 tool output: 600 tokens]
...
[Step 8: model is now 6,000 tokens in]
```

At 8,192 tokens context, the model's attention is spread thin. The "lost-in-the-middle" problem from Phase 2 kicks in — early instructions lose weight relative to recent content.

### Problem 2 — Reasoning Degradation Over Long Chains

LLMs are trained to be accurate across short-to-medium reasoning chains. Accuracy degrades as the chain grows. A 15-step agent loop that is 95% reliable per step produces a correct final answer only 46% of the time (0.95^15 ≈ 0.46). This is not a model limitation — it is a fundamental property of compounding probabilities.

### Problem 3 — No Parallelism

A single agent loop is sequential: step 1 → step 2 → step 3. If the three underperforming regions could be analysed independently, a single agent still waits for each analysis to complete before starting the next. A well-designed multi-agent system runs those analyses in parallel.

### Problem 4 — One Model Cannot Be Optimal for All Sub-Tasks

Analysing raw sales data requires different strengths than writing executive prose. The model that is best at numerical reasoning is not necessarily best at structured business writing. A single-model agent cannot exploit specialisation.

---

## The Orchestrator / Worker Pattern

The solution splits the problem across two roles:

```
User request
     ↓
[Orchestrator]
  - Understands the full task
  - Breaks it into sub-tasks
  - Assigns each sub-task to a worker
  - Collects results
  - Assembles final output
     ↓              ↓              ↓
[Worker A]      [Worker B]      [Worker C]
sub-task 1      sub-task 2      sub-task 3
```

**The orchestrator never executes sub-tasks directly.** It reasons about the structure of the problem and delegates. Its context stays small — it only needs to hold the task decomposition and the results, not the full execution trace of each sub-task.

**Each worker has a narrow, well-defined task.** Its context is small (just its sub-task), its reasoning chain is short, and it can be the right model for that specific type of work.

---

## What Changes With Two Models

In this phase we use:

- **Claude** as the orchestrator — frontier reasoning capability, handles task decomposition and final synthesis
- **Gemma 4 E2B / 26B** as workers — local inference, no API cost, fast execution on well-defined sub-tasks

This is not arbitrary. The orchestrator needs to understand a complex, ambiguous user request and produce a clean decomposition. That is a hard reasoning task — the right place for a frontier model. The workers receive precise, narrow sub-tasks derived from that decomposition. Those sub-tasks are much easier to execute — the right place for a capable but fast local model.

The cost structure changes significantly:

```
All-Claude approach:
  1 orchestration call + N worker calls, all at cloud API pricing

Hybrid approach:
  1 orchestration call at cloud pricing
  N worker calls at ~$0 (local inference)
```

For tasks decomposed into 5–10 sub-tasks, the hybrid approach reduces API cost by 80–90% while maintaining orchestrator-level reasoning quality on the part that actually needs it.

---

## Task Decomposition

Decomposition is the orchestrator's core skill. Given a complex request, it produces a list of atomic sub-tasks — each one:

- **Self-contained:** completable without knowing the output of other sub-tasks (unless there is a dependency)
- **Typed:** labelled with the task category so it can be routed to the right model
- **Sequenced:** dependencies made explicit so parallel and sequential steps are clear

Example decomposition for the sales analysis task:

```json
[
  {
    "id": 1,
    "task": "Summarise the Q1 sales data for each region in 2 sentences",
    "type": "summarise",
    "depends_on": [],
    "route_to": "local"
  },
  {
    "id": 2,
    "task": "Identify the 3 regions with the lowest Q1 revenue growth",
    "type": "reasoning",
    "depends_on": [1],
    "route_to": "local"
  },
  {
    "id": 3,
    "task": "Write an executive summary of the 3 underperforming regions",
    "type": "summarise",
    "depends_on": [2],
    "route_to": "local"
  },
  {
    "id": 4,
    "task": "Suggest 3 actionable fixes for each underperforming region",
    "type": "reasoning",
    "depends_on": [2],
    "route_to": "cloud"
  }
]
```

Tasks 3 and 4 both depend on task 2 but not on each other — they can run in parallel once task 2 is complete.

---

## Execution Modes

### Sequential

Each sub-task runs after the previous completes. Simple to implement, slow for independent tasks.

```
Task 1 → Task 2 → Task 3 → Task 4
```

### Parallel (Fan-Out / Fan-In)

Independent sub-tasks run simultaneously. Results collected before dependent tasks begin.

```
Task 1 → Task 2 → [Task 3, Task 4 in parallel] → Synthesise
```

### Hierarchical

Workers can themselves be orchestrators — sub-tasks are further decomposed into micro-tasks. Used for very long-horizon work. Not covered in this phase.

---

## The Routing Decision

Each sub-task is routed based on two signals:

1. **Task type** — from the routing table built in Phase 4 (factual/summarise → local, reasoning/code → local-26b or cloud)
2. **Sensitivity flag** — if the sub-task involves data that cannot leave the device, it is forced to local regardless of type

```
route(task):
  if task.sensitive:
      return local_model
  if task.type in ["factual", "summarise"]:
      return gemma_e2b
  if task.type in ["reasoning", "code"]:
      return gemma_26b
  if task.requires_frontier:
      return claude_api
```

The orchestrator sets the `sensitive` and `requires_frontier` flags when it decomposes the task. The router enforces them.

---

## What This Phase Builds

```
User task (complex, multi-part)
         ↓
  [Gemma 26B — Orchestrator]
  Decomposes into typed, sequenced sub-tasks
         ↓
  [Router — from Phase 4]
  Routes each sub-task to the right model
         ↓
  [Gemma E2B / 26B — Workers]
  Execute sub-tasks locally
         ↓
  [Gemma 26B — Synthesiser]
  Assembles worker outputs into final response
```

Fully local — no cloud API required. Gemma 26B handles orchestration and synthesis (the reasoning-heavy steps). E2B handles factual and summarise sub-tasks at 2.5x the speed. Everything runs on-device.

> **Note on hybrid systems:** In production, the orchestrator role is often given to a frontier cloud model (Claude, GPT-4) for stronger task decomposition on ambiguous or complex requests. The worker layer stays local. That hybrid pattern becomes viable once Claude API credits are available — the architecture and worker code are identical, only the orchestrator call changes.

---

## Experiment — Multi-Agent System in Action

> Run on Apple M4 24 GB — 2026-04-21
> Script: `05-orchestration-multi-agent/code/01_orchestrated_agent.py`

### What the Code Does

The script has three stages:

**Stage 1 — Decompose.** Gemma 26B receives the full user request and a structured prompt instructing it to return a raw JSON array of sub-tasks. Each sub-task has an `id`, a `task` description, a `type` (used for routing), a `depends_on` list, and an `output_format` spec. No markdown, no explanation — just the JSON.

**Stage 2 — Execute.** The execution engine reads the sub-task list, finds tasks with no unmet dependencies, and runs them in order. Each sub-task is passed to `run_worker()`, which looks up the task type in the routing table, selects E2B or 26B, and calls Ollama. If a sub-task depends on a prior one, the prior result is injected into the prompt as context.

**Stage 3 — Synthesise.** Once all workers are done, Gemma 26B receives the original request and all worker outputs, and produces the final response.

### The Request

```
I'm learning about transformer models. Can you:
1) Explain what the attention mechanism is in simple terms,
2) Compare self-attention vs cross-attention,
3) Give me a Python code snippet showing a minimal dot-product attention calculation,
and 4) Summarise when I would use an encoder-only vs decoder-only vs encoder-decoder architecture.
```

This request has four independent parts — no sub-task depends on another. All four can run in any order.

### Step 1 — Decomposition Output

Gemma 26B decomposed the request into 4 sub-tasks and assigned correct types:

| ID | Type | Task (truncated) | Routed to |
|----|------|-----------------|-----------|
| 1 | summarise | Explain the attention mechanism using simple terms... | gemma4:e2b |
| 2 | reasoning | Compare and contrast self-attention vs cross-attention... | gemma4:26b |
| 3 | code | Write a minimal Python snippet showing dot-product attention... | gemma4:26b |
| 4 | summarise | Summarise when to use encoder-only vs decoder-only vs encoder-decoder... | gemma4:e2b |

The routing is automatic — the orchestrator assigned `type`, the routing table selected the model. No explicit routing instruction was needed.

### Step 2 — Worker Results

**Sub-task 1 — Attention mechanism (summarise → E2B)**

- 50.9 tok/s | 570 tokens | 17,527ms
- E2B explained attention as: "when your brain doesn't treat every word with equal importance — the model looks at every other word, assigns importance scores, and creates a weighted summary." Correct, approachable, followed the format instruction.

**Sub-task 2 — Self-attention vs cross-attention (reasoning → 26B)**

- 9.4 tok/s | 642 tokens | 83,379ms
- 26B produced a structured comparison: self-attention relates positions within the same sequence (intra-sequence); cross-attention bridges two sequences, e.g. encoder output → decoder input (inter-sequence). Included a table with Query/Key/Value sources for each.

**Sub-task 3 — Dot-product attention code (code → 26B)**

- 16.2 tok/s | 287 tokens | 19,056ms
- 26B produced a clean NumPy implementation of `scaled_dot_product_attention(Q, K, V)` — three steps: compute scores, apply softmax, multiply by V. Concise, no unnecessary comments.

**Sub-task 4 — Architecture guide (summarise → E2B)**

- 51.2 tok/s | 450 tokens | 16,105ms
- E2B correctly covered all three: encoder-only (BERT) for understanding/classification, decoder-only (GPT) for generation, encoder-decoder (T5, BART) for seq-to-seq translation and summarisation.

### Step 3 — Synthesised Final Output

Gemma 26B assembled all four worker outputs into a single structured response with:
- A plain-English attention explanation with a concrete pronoun-resolution example
- A comparison table (self-attention vs cross-attention — Q/K/V sources, relationship type, primary goal)
- The working NumPy code block
- A three-section architecture guide with use cases per type

The synthesis was publication-quality on the first run.

### Results Summary

| Sub-task | Type | Model | Speed | Tokens | Duration |
|----------|------|-------|-------|--------|----------|
| Attention mechanism | summarise | E2B | 50.9 tok/s | 570 | 17.5s |
| Self vs cross-attention | reasoning | 26B | 9.4 tok/s | 642 | 83.4s |
| Dot-product attention code | code | 26B | 16.2 tok/s | 287 | 19.1s |
| Architecture guide | summarise | E2B | 51.2 tok/s | 450 | 16.1s |
| **Total workers** | | | | **1,949** | **136s** |

**Routing accuracy:** 4/4 correct — the orchestrator assigned types that matched exactly what Phase 4 identified as the right model per task.

**Speed observation:** Sub-task 2 (reasoning) ran at 9.4 tok/s vs E2B's ~51 tok/s. The reasoning task generated 642 tokens — with both models competing for the same 24 GB of unified memory, 26B was partially displaced by E2B's prior run, causing a reload. In a production system, the orchestrator would schedule 26B tasks first to avoid cold-start penalties.

**All inference local — zero API cost.**

---

## Enterprise Implication

The orchestrator/worker pattern maps directly to how enterprises structure knowledge work:

- A senior analyst (orchestrator) scopes a problem and assigns components to junior analysts (workers)
- Each junior analyst has a focused task, reports back a structured result
- The senior analyst synthesises the findings into a client deliverable

AI multi-agent systems are the same structure. The enterprise value is that the "senior analyst" reasoning (Claude) is applied only where it is needed — decomposition and synthesis — while the volume work (data extraction, summarisation, analysis of individual components) runs locally at near-zero cost.

This is the architecture behind every enterprise AI assistant that reports "80% cost reduction vs naive API usage." The cost reduction comes from routing, not from using a worse model everywhere.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Orchestrator | The agent responsible for task decomposition, routing, and final synthesis |
| Worker | An agent that executes a single, well-defined sub-task and returns a result |
| Task decomposition | Breaking a complex request into atomic, typed, sequenced sub-tasks |
| Fan-out | Dispatching multiple independent sub-tasks in parallel |
| Fan-in | Collecting results from parallel workers before proceeding |
| Dependency graph | The ordered relationship between sub-tasks — defines what can run in parallel |
| Hybrid routing | Using local models for worker tasks and cloud models for orchestration |

---

## Next

**Gemma as a Worker** — what kinds of sub-tasks Gemma handles well in a worker role, how to structure the worker interface, and how results flow back to the orchestrator.
