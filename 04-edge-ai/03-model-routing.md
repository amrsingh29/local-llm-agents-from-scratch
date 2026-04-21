# Model Routing

## The Problem Routing Solves

After running the benchmark, you have two models:

| Model | Strength | Cost |
|-------|---------|------|
| gemma4:e2b | 2.5x faster, identical quality on factual/summarise | Lower memory, lower latency |
| gemma4:26b | More reliable on reasoning, better instruction-following | Higher memory, higher latency |

If you always use 26B, you pay a 2.5x latency penalty on every request that did not need it. If you always use E2B, you get worse answers on tasks that needed 26B's precision.

Routing solves this: classify each incoming request and send it to the appropriate model. The classification costs almost nothing. The latency savings are significant at scale.

---

## Three Routing Strategies

### Strategy 1 — Rule-Based Routing

The developer writes explicit rules derived from benchmark data.

```
if task contains math, calculation, or multi-step derivation:
    → gemma4:26b
elif task contains "write", "implement", "function", or "code":
    → gemma4:26b
else:
    → gemma4:e2b
```

**Pros:** deterministic, zero latency overhead, fully auditable  
**Cons:** keyword matching is brittle — "summarise this calculation" would route to 26B unnecessarily

### Strategy 2 — Classifier Routing

A small model (or the fast model itself) classifies the task type before the main call.

```
Step 1: send prompt to gemma4:e2b with classification prompt
        → returns: "factual" | "reasoning" | "code" | "summarise"
Step 2: route to appropriate model based on label
Step 3: send prompt to chosen model, return response
```

**Pros:** handles ambiguous phrasing, generalises beyond keywords  
**Cons:** adds one extra inference call (small — E2B classifies in ~200ms)

### Strategy 3 — Confidence-Based Routing

Send every request to E2B first. If the model signals low confidence or the response is below a quality threshold, retry with 26B.

```
Step 1: call gemma4:e2b
Step 2: evaluate response (rule, judge, or heuristic)
Step 3: if quality acceptable → return
         else → call gemma4:26b and return that response
```

**Pros:** automatically adapts to task difficulty without pre-classification  
**Cons:** worst-case latency is E2B + 26B combined; need a reliable quality signal

---

## What We Build Here

A **classifier router** — Strategy 2. It is the best balance of accuracy and overhead for a local two-model setup:

- One fast classification call to E2B (~200ms warm, ~5s cold)
- One main inference call to the chosen model
- Total overhead per request: classifier time only — no extra cost on the main call

Script: `04-edge-ai/code/02_model_router.py`

---

## The Classification Prompt

The classifier needs to map any incoming prompt to one of four categories derived from the benchmark:

| Category | Route to | Rationale |
|----------|---------|-----------|
| `factual` | e2b | Identical quality, 2.5x faster |
| `summarise` | e2b | Identical quality, 2.5x faster |
| `reasoning` | 26b | 26B more reliable on multi-step derivation |
| `code` | 26b | 26B follows format constraints, produces concise output |

The classifier prompt instructs the model to return a single word with no explanation:

```
Classify the following prompt into exactly one of these four categories:

  factual   — asking for a definition, explanation, or fact
  summarise — asking to condense or restate existing content
  reasoning — asking to derive an answer through calculation or multi-step logic
  code      — asking to write, fix, or explain code

Reply with only the single category word. No punctuation. No explanation.

Prompt to classify:
{prompt}
```

Every extra token in the classifier response is wasted latency. A 10-token cap (`num_predict=10`) enforces this.

---

## Experiment Results

> Run on Apple M4 24 GB — 2026-04-21
> Script: `04-edge-ai/code/02_model_router.py`

Four prompts, one per task type. Each shows the prompt, the label the classifier returned, the model it was routed to, and the final response.

---

### Prompt 1 — Factual

**Prompt:**
> What is the difference between supervised and unsupervised learning? Answer in 2 sentences.

**Classifier output:** `factual` (4,835ms — cold start, E2B loading into memory)

**Routed to:** `gemma4:e2b`

**Inference:** 1,383ms at 54.3 tok/s

**Total time:** 6,218ms (dominated by cold start — warm requests take ~1,800ms total)

**Response:**
> Supervised learning involves training a model on labeled data, where the desired output is already known, while unsupervised learning deals with unlabeled data, aiming to discover hidden patterns or structures within the data. Essentially, supervised learning learns from examples with correct answers, while unsupervised learning finds structure without predefined labels.

**Routing correct:** Yes

---

### Prompt 2 — Summarise

**Prompt:**
> Summarise the following in 2 sentences: [RAG explanation — what it is, how it works, why it reduces hallucination]

**Classifier output:** `summarise` (402ms — E2B now warm)

**Routed to:** `gemma4:e2b`

**Inference:** 1,519ms at 54.7 tok/s

**Total time:** 1,922ms

**Response:**
> Retrieval-Augmented Generation (RAG) is a technique that enhances language models by integrating a retrieval system to fetch relevant external documents at the time of answering. This process allows the model to generate more accurate responses based on retrieved facts, improving knowledge about data the model wasn't directly trained on and reducing hallucination.

**Routing correct:** Yes

**Observation:** With E2B warm, the full round-trip including classification is under 2 seconds. The classification overhead is 402ms — 21% of total time. Acceptable for interactive use; cache-able for batch pipelines.

---

### Prompt 3 — Reasoning

**Prompt:**
> A server handles 450 requests per minute. Each request takes an average of 200ms to process. How many concurrent worker threads are needed to sustain this load without queuing? Show your calculation.

**Classifier output:** `reasoning` (357ms)

**Routed to:** `gemma4:26b`

**Inference:** 33,266ms at 19.6 tok/s

**Total time:** 33,624ms

**Response (excerpt):**
> To find the number of concurrent worker threads required to handle a specific load without queuing, we use Little's Law.
>
> Arrival Rate: 450 requests/minute = 7.5 requests/second
> Service Time: 200ms = 0.2 seconds
> Concurrent threads needed = Arrival Rate × Service Time = 7.5 × 0.2 = 1.5 → 2 threads minimum

**Routing correct:** Yes

**Observation:** 26B correctly applied Little's Law (L = λW), converted units, and arrived at 2 threads. The reasoning inference is slow (33s) because 26B generated a detailed step-by-step derivation up to the token limit. For a production system, the response is correct — the latency is the cost of routing to the capable model. E2B routed here would have been faster but less reliable on the unit conversion and formula selection.

---

### Prompt 4 — Code

**Prompt:**
> Write a Python function called `chunk_list` that takes a list and a chunk size and returns a list of sublists, each of length chunk_size (the last may be shorter). No explanation. Just the function.

**Classifier output:** `code` (5,201ms — classifier hit cold start again after 26B occupied memory)

**Routed to:** `gemma4:26b`

**Inference:** 15,148ms at 13.6 tok/s

**Total time:** 20,349ms

**Response:**

```python
def chunk_list(lst, chunk_size):
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
```

**Routing correct:** Yes

**Observation:** 26B produced a one-liner list comprehension — correct, concise, no comments, no explanation. This is exactly the instruction-following behaviour the benchmark identified. The same prompt sent to E2B in the benchmark produced 197 tokens of verbose output with comments. 26B produced 87 tokens including the wrapper. Here it produced a single line. The format instruction was followed precisely.

---

## Summary Table

| Prompt | Expected label | Got | Expected model | Got | Classify time | Inference time | Total |
|--------|--------------|-----|---------------|-----|--------------|----------------|-------|
| Supervised vs unsupervised | factual | factual | e2b | e2b | 4,835ms (cold) | 1,383ms | 6,218ms |
| RAG summarise | summarise | summarise | e2b | e2b | 402ms | 1,519ms | 1,922ms |
| Server threads | reasoning | reasoning | 26b | 26b | 357ms | 33,266ms | 33,624ms |
| chunk_list function | code | code | 26b | 26b | 5,201ms (cold) | 15,148ms | 20,349ms |

**Classification accuracy: 4/4 (100%)** on the first run.

**Cold start observation:** Prompts 1 and 4 had 4–5 second classification times because E2B was evicted from memory while 26B was running (both models cannot be resident simultaneously on 24 GB when 26B takes ~20 GB). In a production system this is solved by keeping the classifier model pinned in memory as a dedicated service, separate from the main inference models.

---

## Routing in a Multi-Model Agent

The router becomes more powerful when embedded in an agent loop. Instead of routing once per user request, the agent routes each individual tool call:

```
User task: "Summarise this document, then write a Python function
            to extract all dates from the summary."

Agent loop:
  Step 1: classify("Summarise this document")
          → "summarise" → gemma4:e2b
          → fast summary returned

  Step 2: classify("Write a Python function to extract all dates")
          → "code" → gemma4:26b
          → clean, concise function returned
```

The same task uses both models — E2B where it is sufficient, 26B where it is not. The agent does not need to know which model ran which step.

This is the pattern Phase 5 scales up: replace 26B with a cloud API (Claude) for the steps that require frontier capability, and keep E2B as the local worker for the rest.

---

## Failure Modes in Routing

### Misclassification

The classifier calls a task "factual" when it requires reasoning. E2B is routed and returns an incomplete answer. 

**Mitigation:** log every routing decision and the final response quality. When misclassifications cluster around a pattern (e.g., "calculate" in a non-math context), add a correction rule.

### Classifier Hallucination

The classifier returns something other than the four valid labels.

**Mitigation:** always validate the classifier output. If it returns anything outside the known label set, default to 26B — it is safer to over-route to the capable model than to under-route to the fast one.

### Latency Amplification

In the worst case (confidence-based routing), a request hits E2B, fails quality check, and then hits 26B. Total latency = E2B time + 26B time.

**Mitigation:** use classifier routing (Strategy 2) instead of confidence-based routing (Strategy 3) for latency-sensitive applications.

---

## Enterprise Implication

In production multi-model deployments, routing is infrastructure — not application logic. It lives in a dedicated service that:

- Receives every LLM request from every application
- Classifies and routes to the appropriate model tier
- Logs every routing decision for cost accounting and quality monitoring
- Can be updated (new rules, new models, new tiers) without touching application code

The same routing layer that dispatches between E2B and 26B today can be extended to dispatch between local models and cloud APIs tomorrow. The application never changes — only the routing table does.

This is why routing is worth building as a standalone component, not inline logic inside each agent.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Classifier routing | Using a model to label each request's task type before dispatching to the appropriate model |
| Rule-based routing | Keyword or pattern matching to determine which model handles a request |
| Confidence-based routing | Sending requests to the fast model first, escalating to the capable model on low-quality responses |
| Routing overhead | The extra latency introduced by the classification step |
| Default route | The model used when classification is ambiguous or fails — should be the more capable model |

---


## Full Code

```python title="02_model_router.py"
--8<-- "04-edge-ai/code/02_model_router.py"
```

## Next

**Phase 5 — Orchestration and Multi-Agent Systems.** The router built here dispatches between two local models. Phase 5 extends it to dispatch between a local model (Gemma, the worker) and a cloud API (Claude, the orchestrator). The orchestrator breaks complex tasks into sub-tasks, routes each sub-task to the appropriate model, and aggregates the results. This is the production multi-agent pattern.
