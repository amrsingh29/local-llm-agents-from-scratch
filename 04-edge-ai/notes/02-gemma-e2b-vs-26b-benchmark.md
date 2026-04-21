# Gemma E2B vs 26B — Benchmark and Decision Framework

## What We Are Testing

Gemma 4 comes in two local variants:

| Model | Parameters | Architecture | Download size | Use case |
|-------|-----------|-------------|---------------|---------|
| gemma4:e2b | ~2 billion (effective) | Dense | 7.2 GB | Fast inference, constrained hardware |
| gemma4:26b | 26 billion (MoE) | Mixture of Experts | ~17 GB | Higher capability, sufficient for most tasks |

The MoE architecture means 26B does not activate all 26B parameters per token — only the expert subnetworks relevant to each input are activated. In practice, the active parameter count per forward pass is closer to 7B. This is why 26B fits in 24 GB unified memory and delivers competitive throughput despite its total size.

The benchmark answers: **when is the quality difference large enough to justify the latency difference?**

---

## Setup

```bash
# Pull E2B (7.2 GB)
ollama pull gemma4:e2b

# Run the benchmark
python 04-edge-ai/code/01_model_benchmark.py
```

**Hardware:** Apple M4, 24 GB Unified Memory
**Date:** 2026-04-21
**Judge model:** gemma4:26b (scores factual, reasoning, summarisation answers 1–5)

---

## Task Suite

Four task types, six tasks total:

| Task ID | Type | What it tests |
|---------|------|---------------|
| factual_1 | Factual | Transformer encoder vs decoder — standard ML knowledge |
| factual_2 | Factual | Quantization definition — standard ML knowledge |
| reasoning_1 | Reasoning | Multi-step arithmetic with unit tracking |
| reasoning_2 | Reasoning | Context window capacity calculation |
| code_1 | Code | Python retry function — real implementation |
| summarise_1 | Summarise | MoE explanation — compression without loss |

---

## Benchmark Results

> Run against Gemma 4 E2B and 26B on Apple M4 24 GB — 2026-04-21
> Script: `04-edge-ai/code/01_model_benchmark.py`

### Throughput

| Model | Avg tok/s | Avg latency (ms) |
|-------|----------|-----------------|
| gemma4:e2b | 51.9 | 8,149 |
| gemma4:26b | 20.6 | 8,643 |

**Speedup factor:** 51.9 / 20.6 = **2.5x faster** on token generation rate

Note: average latency is similar because task length varies — E2B generates more tokens per task in roughly the same wall time. The throughput ratio is the meaningful number: 2.5x more tokens per second from the smaller model.

### Quality Scores (1–5, judged by gemma4:26b)

| Task | gemma4:e2b | gemma4:26b |
|------|-----------|-----------|
| factual_1 | 5/5 | 5/5 |
| factual_2 | 5/5 | 5/5 |
| reasoning_1 | 4/5 | 4/5 |
| reasoning_2 | 4/5 | 5/5 |
| code_1 | manual | manual |
| summarise_1 | 5/5 | 5/5 |
| **Average (scored tasks)** | **4.6/5** | **4.8/5** |

---

## Per-Task Breakdown

Each task is shown with the exact prompt, both model responses verbatim, and the judge's score and reasoning.

---

### Task: factual_1 — Transformer Encoder vs Decoder

**Prompt:**
> What is the difference between a transformer's encoder and decoder? Answer in 3 sentences.

**gemma4:e2b** (71 tokens, 49.7 tok/s) — Score: **5/5**
> In a transformer model, the **encoder** processes the input sequence to create a rich, contextualized representation of the entire input. This representation captures the relationships and dependencies between all the elements in the input. The **decoder** takes this encoded information and generates the output sequence, one element at a time, based on the context provided by the encoder.

**gemma4:26b** (84 tokens, 26.0 tok/s) — Score: **5/5**
> The encoder's role is to process the input sequence and generate a rich, contextualized numerical representation of the data. In contrast, the decoder uses this representation along with previously generated tokens to predict the next element in an output sequence. While the encoder uses bidirectional self-attention to understand the entire input at once, the decoder employs masked self-attention to ensure it only attends to past information during the generation process.

**Observation:** Both answers are accurate and concise. 26B added the technical detail of bidirectional vs masked self-attention — a more precise answer. E2B covered the functional difference correctly without the attention mechanism detail. Either answer would pass a technical interview.

---

### Task: factual_2 — Quantization Definition

**Prompt:**
> What is quantization in the context of machine learning models? Answer in 3 sentences.

**gemma4:e2b** (111 tokens, 49.2 tok/s) — Score: **5/5**
> Quantization in machine learning is the process of reducing the precision of the numerical representations (weights and activations) within a neural network, typically by converting them from high-precision floating-point numbers (like 32-bit) to lower-precision integers (like 8-bit). This reduction significantly decreases the model's memory footprint and the computational requirements for inference, making the model smaller and faster to run. While this process can introduce a small loss in accuracy, it is a key technique for deploying large models on resource-constrained devices.

**gemma4:26b** (105 tokens, 18.8 tok/s) — Score: **5/5**
> Quantization is a model compression technique that reduces the precision of a neural network's weights and activations by converting them from high-precision floating-point numbers (like 32-bit) to lower-bit formats (like 8-bit integers). By decreasing the number of bits required to represent each parameter, the model's memory footprint and computational requirements are significantly reduced. This process enables faster inference speeds and allows large models to run efficiently on hardware with limited resources, such as mobile phones and edge devices.

**Observation:** Nearly identical answers. Both correctly cover the mechanism (precision reduction), the benefit (smaller, faster), and the trade-off (accuracy loss). E2B's answer is marginally more explicit about the accuracy cost; 26B ends with a concrete example (mobile phones, edge devices). Both 5/5.

---

### Task: reasoning_1 — Warehouse Robot Backlog

**Prompt:**
> A warehouse has 3 robots. Each robot can process 120 packages per hour. The warehouse receives 1,000 packages per 8-hour shift. How many shifts does it take to clear a backlog of 5,000 packages? Show your calculation.

**Expected path:** 3 × 120 × 8 = 2,880 processed/shift. 5,000 / 2,880 ≈ 1.74 → 2 shifts.

**gemma4:e2b** (300 tokens, 53.7 tok/s) — Score: **4/5**

Correctly calculated: 3 robots × 120 = 360/hr, 360 × 8 = 2,880/shift, 5,000 / 2,880 ≈ 1.736. Then cut off mid-sentence before stating the final answer of 2 shifts. Hit the 300-token output limit.

```
...5,000 / 2,880 ≈ 1.736

4. Interpret the result: Since you cannot have a fraction of a shift
   when clearing a backlog, you must round up to the  [CUT OFF]
```

**gemma4:26b** (300 tokens, 18.3 tok/s) — Score: **4/5**

Took a different — and arguably more correct — interpretation: subtracted the 1,000 incoming packages per shift from the 2,880 processed, giving a net reduction of 1,880/shift. 5,000 / 1,880 ≈ 2.66 → 3 shifts. Also cut off before the final answer due to the token limit.

```
...Net reduction per shift = 2,880 - 1,000 = 1,880 packages/shift

4. Calculate the number of shifts to clear the backlog:
   Number of shifts = 5,000 / 1,880  [CUT OFF]
```

**Observation:** Both models hit the 300-token output limit and did not finish. The judge scored both 4/5 for correct reasoning with incomplete output. 26B's interpretation (accounting for new arrivals during the clear) is actually a more realistic reading of the problem. E2B ignored the 1,000 arrivals/shift — technically a reasoning error, though the judge did not penalize it. Both need a higher `num_predict` to complete this task.

---

### Task: reasoning_2 — Context Window Capacity

**Prompt:**
> A context window holds 8,192 tokens. A system prompt uses 500 tokens. Each user message averages 50 tokens. Each assistant response averages 200 tokens. How many conversation turns fit before the context is full? Show your calculation.

**Expected answer:** (8192 − 500) / (50 + 200) = 7692 / 250 = 30.768 → 30 complete turns.

**gemma4:e2b** (300 tokens, 53.4 tok/s) — Score: **4/5**

Correctly set up all variables and intermediate calculations (remaining space = 7,692, tokens per turn = 250). Cut off before computing the final division and stating 30 turns.

```
...Space per Turn = U + A
   Space per Turn = 50 + 200 = 250 tokens/turn  [CUT OFF]
```

**gemma4:26b** (300 tokens, 24.9 tok/s) — Score: **5/5**

Completed all four steps including the final division: 7,692 / 250 = 30.768, and correctly noted that only complete turns count. Cut off one word before explicitly saying "30 turns" but the judge gave 5/5 because the derivation is unambiguously complete.

```
...Number of turns = 7,692 / 250 = 30.768

Since you cannot have a partial turn that completes the context
without exceeding  [CUT OFF]
```

**Observation:** This is the one task where 26B clearly outperformed E2B. 26B got to the final numerical result; E2B stopped earlier in the derivation. Both hit the token limit, but 26B produced more per token on this task (24.9 tok/s vs 53.4 tok/s — 26B is slower but its tokens are structurally more complete). The score difference (4 vs 5) reflects that E2B left the actual answer implicit.

---

### Task: code_1 — Python Retry Function

**Prompt:**
> Write a Python function called `retry` that takes a function `fn`, a maximum number of attempts `max_attempts`, and a delay in seconds `delay`. It should call `fn()`, and if it raises an exception, wait `delay` seconds and retry. After `max_attempts` failures, raise the last exception. No external libraries. Just the function, no explanation.

**gemma4:e2b** (197 tokens, 52.4 tok/s) — Score: manual

```python
def retry(fn, max_attempts, delay):
    last_exception = None
    for attempt in range(max_attempts):
        try:
            result = fn()
            return result
        except Exception as e:
            last_exception = e
            if attempt < max_attempts - 1:
                pass  # Continue to the next attempt
            else:
                # This is the last attempt, we will raise the exception after the loop
                break
            
            # Wait before retrying
            import time
            time.sleep(delay)

    # If the loop finishes without returning, it means all attempts failed
    if last_exception:
        raise last_exception
    # This part should theoretically not be reached if max_attempts > 0 and an exception occurred,
    # but we handle the edge case where fn() succeeds on the last attempt.
```

**gemma4:26b** (87 tokens, 17.1 tok/s) — Score: manual

```python
import time

def retry(fn, max_attempts, delay):
    last_exception = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            last_exception = e
            if attempt < max_attempts - 1:
                time.sleep(delay)
    raise last_exception
```

**Manual review:**

Both functions are logically correct and produce the same behaviour. The differences are in execution quality:

- **E2B used 197 tokens vs 26B's 87 tokens** — 2.3x more output for the same function. E2B included inline comments despite being told "no explanation," imported `time` inside the loop (avoids the standard module import pattern), and added a redundant `if last_exception` guard before the final raise.
- **26B followed the instruction literally** — no comments, `import time` at module level, clean loop with a direct `raise last_exception` at the end. 87 tokens. Exactly what was asked.

This is the most practically significant finding in the benchmark: **instruction-following on format constraints is measurably better in 26B**. For agents that parse model output programmatically, verbosity and deviation from format instructions are bugs, not style preferences.

---

### Task: summarise_1 — MoE Explanation

**Prompt:**
> Summarise the following in exactly 2 sentences: [MoE architecture explanation — Gemma 4 26B context]

**gemma4:e2b** (58 tokens, 53.0 tok/s) — Score: **5/5**
> Mixture of Experts (MoE) is a neural network architecture that uses a gating network to selectively activate only a subset of expert subnetworks for any given input. This design allows models to possess the capacity of very large models while maintaining the inference cost and memory usage of smaller models.

**gemma4:26b** (62 tokens, 18.6 tok/s) — Score: **5/5**
> Mixture of Experts (MoE) utilizes a gating network to activate only specific sub-networks, allowing a model to possess vast knowledge while maintaining low inference costs. The Gemma 4 26B model employs this architecture to provide the capacity of a large model with the efficiency of a smaller one.

**Observation:** Both answers are accurate, both fit exactly 2 sentences, both capture the key mechanism (gating) and the key benefit (large capacity at small inference cost). 26B's answer anchored the example to Gemma 4 26B specifically, which is marginally more contextual. No practical difference — both 5/5 at roughly the same token count.

---

## Analysis

### Where E2B Is Sufficient

E2B matched 26B on three of the five scored task types:

- **Factual recall** — both scored 5/5 on both tasks. E2B has seen the same training data and retrieves standard ML knowledge with no quality loss at 2.5x the speed.
- **Summarisation** — both scored 5/5. Compression tasks do not require extended reasoning chains; E2B handles them cleanly.

For these task types, E2B is the correct choice: identical quality at 2.5x throughput, 10 GB less memory pressure, and room for other processes on a 24 GB machine.

### Where 26B Has the Edge

- **Reasoning task 2** (context window calculation) — E2B scored 4/5 vs 26B's 5/5. The 26B model tracked the intermediate values more precisely through the multi-step calculation.
- **Reasoning task 1** (warehouse robots) — both scored 4/5. Neither model lost points here, suggesting E2B is competitive on arithmetic-heavy reasoning with explicit numbers.

The reasoning gap is real but narrow — one point on one of two reasoning tasks. This is smaller than the hypothesis predicted.

### The Reasoning Gap Hypothesis — Result

The hypothesis was that E2B would fall significantly behind on multi-step reasoning. The data partially confirms it: 26B is more reliable on reasoning tasks, but the gap (0.2 points average) is smaller than expected.

**The revised routing heuristic based on actual data:**

- Route to E2B when quality requirements are met at 4/5 and throughput matters
- Route to 26B when a task requires precise multi-step reasoning or when a 5/5 answer is required
- For factual recall and summarisation: always E2B — zero quality cost, 2.5x speed gain

### Code Task — Manual Review Required

The code task (Python retry function) was not scored by the judge — code correctness requires execution, not LLM judgment. Both models produced syntactically valid Python. A manual review showed:

- **E2B** — produced a working retry function with correct logic, but generated 197 output tokens (more verbose, included more explanation despite being told not to)
- **26B** — produced a concise 87-token implementation, closely followed the "no explanation" instruction

Instruction-following on format constraints is a real differentiator. If your agent calls tools that return code and must parse it programmatically, 26B is more reliable.

---

## The Local Routing Decision

Based on actual benchmark data, the routing rule for this hardware:

```
If task_type in ["factual", "summarise", "classify"]:
    use gemma4:e2b    # 2.5x faster, quality identical (5/5 vs 5/5)
Elif task_type == "reasoning" and precision_required:
    use gemma4:26b    # more reliable on multi-step derivation
Elif task_type == "code":
    use gemma4:26b    # better instruction-following on format constraints
Else:
    use gemma4:e2b    # default to fast when quality is acceptable
```

This is the foundational pattern for **Phase 5 (Multi-Agent)** — except the routing will be between Gemma local (worker) and Claude cloud (orchestrator), rather than between two local models.

---

## Memory Pressure Observation

- **gemma4:e2b:** 7.2 GB on disk, loads to approximately 8–9 GB in unified memory. Leaves ~15 GB free on a 24 GB machine.
- **gemma4:26b:** 17 GB on disk, loads to approximately 20–22 GB in unified memory. Leaves ~2–4 GB free.

On a 16 GB machine, 26B does not fit. E2B becomes the only local option — the quality benchmark becomes irrelevant and the hardware constraint decides. Complex tasks must go to a cloud API.

**Practical rule:** on 16 GB Apple Silicon, use gemma4:e2b for all local inference. On 24 GB+, route by task type using the heuristic above.

---

## When to Use Each Model

| Dimension | gemma4:e2b | gemma4:26b |
|-----------|-----------|-----------|
| Throughput | 51.9 tok/s | 20.6 tok/s |
| Speedup | 2.5x faster | baseline |
| Memory | ~7 GB loaded | ~20 GB loaded |
| Factual quality | 5/5 | 5/5 |
| Reasoning quality | 4/5 | 4.5/5 |
| Code quality | Functional, verbose | Concise, follows format |
| Summarisation | 5/5 | 5/5 |
| Best for | High-throughput, factual, summarise | Precision reasoning, code, format-sensitive tasks |

---

## Enterprise Implication

In a production edge AI deployment, the model tier decision determines your infrastructure requirements:

- **E2B-only deployment:** runs on any Apple Silicon Mac, most consumer laptops with 8 GB RAM. Low cost, adequate for classification, retrieval, and summarisation at scale.
- **26B deployment:** requires 24 GB+ RAM. Covers the vast majority of enterprise tasks. ~17x larger download, significantly higher hardware spec.
- **Hybrid deployment:** routes by task type. Best quality and cost. Requires a routing layer (classifier or rule-based) and slightly more complex infrastructure.

Most enterprise deployments start with one model and add routing after they have production data showing where quality gaps hurt real outcomes. The benchmark in this note is the tool you run before deployment to make the initial tier decision.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Active parameters | The parameters actually used during a single forward pass (relevant for MoE models) |
| Model routing | Automatically directing requests to different model tiers based on task characteristics |
| Quality gap | The difference in output quality between models — measured here as judge score differential |
| Throughput ratio | The multiplier in tokens/sec between two models — quantifies the latency cost of choosing the larger model |

---

## Next

**Phase 5 — Orchestration and Multi-Agent Systems.** The routing pattern from this benchmark scales up: Gemma (local worker agent) and Claude (cloud orchestrator) work together. The orchestrator breaks down complex tasks, routes sub-tasks to the appropriate model, and aggregates results. This is how production multi-model systems are built.
