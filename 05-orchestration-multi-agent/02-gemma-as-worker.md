# Gemma as a Worker Agent

## The Worker's Contract

A worker agent has a simple contract:

1. Receive a single, well-defined sub-task
2. Execute it
3. Return a structured result

The worker does not know about the larger task. It does not know what other workers are doing. It does not decide what to do next. The orchestrator owns all of that. The worker owns only execution quality on its assigned sub-task.

This simplicity is a feature. A narrow contract means:
- The worker's context is small — just its sub-task and any data it needs
- The worker's reasoning chain is short — one task, one answer
- The worker is easy to test in isolation — give it a sub-task, check the output
- The worker can be swapped — replace Gemma with a different model without changing the orchestrator

---

## What Gemma Does Well as a Worker

Based on the Phase 4 benchmark, Gemma's worker strengths break cleanly by task type:

### High Confidence — Route Here Without Hesitation

**Summarisation**
- Phase 4 score: 5/5, matched frontier model quality
- Fast: 51.9 tok/s on E2B
- Use for: condensing tool outputs, compressing retrieved data before passing to orchestrator, generating intermediate summaries

**Factual extraction**
- Phase 4 score: 5/5
- Use for: pulling specific values from structured text, answering direct questions about provided context, entity extraction

**Classification**
- Not explicitly benchmarked, but demonstrated in Phase 4 router
- Classifier accuracy: 4/4 on task type classification
- Use for: labelling, routing decisions, intent detection, sentiment

### Moderate Confidence — Route Here, Validate Output

**Multi-step reasoning**
- Phase 4 score: 4/5 on E2B, 4.5/5 on 26B
- Works well when the problem is well-specified with explicit numbers
- Failure mode: cuts off before final answer when token budget is tight — set `num_predict` generously
- Use 26B for this category, not E2B

**Code generation**
- Phase 4: both models produced correct functions
- 26B follows format instructions more reliably (87 tokens vs 197 tokens for same function)
- Use for: utility functions, data transformations, scripts with clear input/output spec
- Always use 26B for code worker tasks

### Low Confidence — Escalate to Orchestrator or Cloud

**Open-ended synthesis across multiple sources**
- Requires holding many results in working memory and making novel connections
- This is what the orchestrator (Claude) does — do not delegate this to a worker

**Tasks requiring external knowledge beyond training data**
- Gemma has a knowledge cutoff; for recent events or live data, use a retrieval tool rather than model knowledge

---

## The Worker Interface

A well-designed worker receives a structured sub-task object and returns a structured result:

```python
# Sub-task input (produced by orchestrator)
sub_task = {
    "id": 2,
    "task": "Identify the 3 regions with lowest Q1 revenue growth from the data below",
    "type": "reasoning",
    "context": "[data goes here]",
    "output_format": "Return a JSON list: [{region, growth_pct, rank}]"
}

# Worker output (returned to orchestrator)
result = {
    "id": 2,
    "status": "success",
    "output": '[{"region": "North", "growth_pct": -3.2, "rank": 1}, ...]',
    "model": "gemma4:26b",
    "tokens": 120,
    "duration_ms": 4800
}
```

The `output_format` field in the sub-task is critical. It is the worker's schema — the same lesson from Phase 3 tool schema design. If the orchestrator does not specify the expected output format, the worker will produce correct content in an unparseable structure.

**Key rule:** the orchestrator owns the output format specification. The worker produces to spec.

---

## Model Selection Within the Worker

The worker layer applies the Phase 4 routing logic to select E2B or 26B:

```python
def select_model(task_type: str) -> str:
    if task_type in ["factual", "summarise", "classify"]:
        return "gemma4:e2b"
    return "gemma4:26b"
```

This is a sub-routing decision made locally within the worker layer — the orchestrator does not need to know which specific local model ran the sub-task. It only knows "local" vs "cloud."

---

## Passing Context to Workers

Workers often need data to operate on — retrieved documents, previous worker outputs, user-provided files. This data is passed in the `context` field of the sub-task.

**Three patterns:**

### Pattern A — Full Context Inline
Pass the entire data directly in the sub-task. Simple, but limited by context window size.

```python
sub_task["context"] = retrieved_document_text  # up to ~6,000 tokens
```

### Pattern B — Chunked Context
Split large data across multiple sub-tasks, each worker handles one chunk.

```python
# Orchestrator decomposes:
[
  {"id": 1, "task": "Summarise section 1", "context": chunk_1},
  {"id": 2, "task": "Summarise section 2", "context": chunk_2},
  {"id": 3, "task": "Merge summaries from tasks 1 and 2", "depends_on": [1, 2]},
]
```

### Pattern C — Reference by ID
The orchestrator stores results in a shared state dictionary. Workers reference results by ID when they need prior outputs.

```python
shared_state = {}

# After task 1 completes:
shared_state["task_1_output"] = result

# Task 3 receives:
sub_task["context"] = shared_state["task_1_output"]
```

Pattern C is what the `orchestrated_agent.py` script implements in this phase.

---

## Error Handling in the Worker Layer

Workers fail. Tool calls fail, models return unexpected formats, context overflows. The worker must report failures clearly so the orchestrator can decide whether to retry, use a fallback, or abort.

```python
# Success
{"id": 2, "status": "success", "output": "...", "model": "gemma4:26b"}

# Failure — orchestrator decides what to do
{"id": 2, "status": "error", "error": "Output format did not match spec", "raw_output": "..."}
```

The orchestrator has three options on worker failure:
1. **Retry** — resend the same sub-task, possibly with a clarified format instruction
2. **Escalate** — send the sub-task to a more capable model (cloud)
3. **Abort** — return a partial result to the user with an explanation

The orchestrator in this phase implements retry and escalate. Abort is the fallback if both fail.

---

## What the Worker Does NOT Do

- Does not decide what to do next after completing its task
- Does not call other workers
- Does not know the user's original request
- Does not store state between sub-tasks
- Does not choose its own model

All of these are orchestrator responsibilities. The worker is stateless and focused. Keeping the worker dumb is what makes the system debuggable and replaceable.

---

## Experiment — Worker Behaviour in Practice

> Run on Apple M4 24 GB — 2026-04-21
> Script: `05-orchestration-multi-agent/code/01_orchestrated_agent.py`

The experiment ran a 4-part transformer explainer request through the full system. Each worker received exactly one sub-task. Here is what each worker was given and what it returned.

---

**Worker 1 — Sub-task type: `summarise` → routed to: `gemma4:e2b`**

Sub-task received:
```
Explain the concept of the attention mechanism in transformer models using simple,
non-technical language. Respond in: plain text
```

Worker returned (excerpt):
> Imagine you're reading a long, complicated sentence, and you need to understand the most important words to grasp the meaning. The attention mechanism allows a model to do exactly this — it looks at every word, calculates a score for how relevant each word is to the current word being processed, and creates a weighted summary.

Result: accurate, followed the plain text format instruction, 570 tokens at 50.9 tok/s.

---

**Worker 2 — Sub-task type: `reasoning` → routed to: `gemma4:26b`**

Sub-task received:
```
Compare and contrast the differences between self-attention and cross-attention in
transformer architectures. Respond in: plain text
```

Worker returned: a structured comparison covering Query/Key/Value sources for each, the intra-sequence vs inter-sequence distinction, and primary use cases. 642 tokens at 9.4 tok/s.

The low speed (9.4 tok/s vs E2B's ~51 tok/s) is a memory pressure effect — 26B was partially displaced while E2B ran sub-task 1, causing a reload. The output quality was unaffected.

---

**Worker 3 — Sub-task type: `code` → routed to: `gemma4:26b`**

Sub-task received:
```
Write a minimal Python code snippet using NumPy to demonstrate a basic dot-product
attention calculation. Respond in: Python code only
```

Worker returned:
```python
def scaled_dot_product_attention(Q, K, V):
    d_k = Q.shape[-1]
    scores = np.matmul(Q, K.swapaxes(-2, -1)) / np.sqrt(d_k)
    exp_scores = np.exp(scores - np.max(scores, axis=-1, keepdims=True))
    weights = exp_scores / np.sum(exp_scores, axis=-1, keepdims=True)
    return np.matmul(weights, V)
```

287 tokens at 16.2 tok/s. Clean, concise, followed the format instruction. No prose explanation included — the output format spec worked.

---

**Worker 4 — Sub-task type: `summarise` → routed to: `gemma4:e2b`**

Sub-task received:
```
Summarise the specific use cases and architectural differences for encoder-only,
decoder-only, and encoder-decoder transformer models. Respond in: plain text
```

Worker returned: correct three-way breakdown — encoder-only (BERT) for classification and understanding, decoder-only (GPT) for generation, encoder-decoder (T5/BART) for translation and summarisation. 450 tokens at 51.2 tok/s.

---

### What the Experiment Confirms

- The worker contract worked as designed: each worker received one narrow task and returned a structured result
- Output format spec controlled response shape — the code worker returned code only, the summarise workers returned prose
- Routing was fully automatic: the orchestrator assigned `type`, the routing table selected the model, no additional instruction needed
- Workers had no knowledge of each other's outputs — isolation was complete
- All four workers succeeded on the first attempt — no retries or escalations needed

---

## Enterprise Implication

The worker pattern maps to microservices architecture. Each worker is a service with a defined interface:
- Input: a structured sub-task
- Output: a structured result
- Contract: execute the task correctly and return in the specified format

This means workers can be:
- Independently deployed and scaled
- Versioned without touching the orchestrator
- Swapped for different models as better options become available
- Tested in isolation against a sub-task test suite

In production multi-agent systems, the worker interface is an API contract — the same versioning and deprecation discipline that applies to microservice APIs applies here. A worker that changes its output format without updating the contract breaks every orchestrator that depends on it.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Worker contract | The interface a worker exposes: accepts a sub-task, returns a structured result |
| Output format spec | The orchestrator's instruction to the worker about how to structure its response |
| Shared state | A dictionary maintained by the orchestrator that stores worker outputs for use by dependent tasks |
| Worker isolation | Workers do not know about each other or the full task — they only see their sub-task |
| Escalation | Routing a failed worker sub-task to a more capable model |

---


## Full Code

```python title="01_orchestrated_agent.py"
--8<-- "05-orchestration-multi-agent/code/01_orchestrated_agent.py"
```

## Next

**`code/01_orchestrated_agent.py`** — the full system: Gemma 26B decomposes and synthesises, E2B/26B workers execute sub-tasks locally by task type. The code makes every concept in these two notes concrete.
