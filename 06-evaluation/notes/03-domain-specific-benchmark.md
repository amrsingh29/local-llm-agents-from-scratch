# Domain-Specific Benchmarks — Evaluating What Actually Matters

## Why Generic Benchmarks Fail

MMLU, HellaSwag, HumanEval — these are the standard benchmarks used to rank models on leaderboards. They measure general reasoning, world knowledge, and coding ability across a broad distribution of topics.

The problem: your system does not operate on a broad distribution. It operates on a narrow one — your domain, your users, your data.

A model that scores 90% on MMLU may answer your domain questions at 60%. A model that scores 78% on MMLU may answer your domain questions at 85%. Leaderboard rankings do not predict this. Your own benchmark does.

**The rule:** evaluate on the distribution you care about, not the distribution someone else built a dataset for.

---

## What Makes a Good Benchmark Question

A benchmark question is not just a question — it is a test case with four components:

### 1. The Question
Drawn from real user requests or realistic synthetic variants of them. Not from textbooks or general knowledge sources.

```
Bad:  "What is the OSI model?"
Good: "A developer reports that their service can ping the database
       host but cannot establish a TCP connection on port 5432.
       Which OSI layer is the likely failure point, and what are
       the two most probable causes?"
```

The good question is what a real user in your domain would ask. It requires applied reasoning, not recall.

### 2. The Reference Answer (for scoreable tasks)
A correct, complete answer written by a domain expert. Used by the judge as the gold standard.

### 3. The Scoring Rubric
Specific to the question type — not a generic 1–5 scale but a description of what each score means for this question.

```
5: Identifies layer 4 (Transport), names both TCP handshake failure
   and firewall/ACL block as causes. Optionally mentions pg_hba.conf.
4: Correct layer, one of the two causes identified correctly.
3: Correct layer but wrong or vague causes.
2: Wrong layer but plausible reasoning.
1: Wrong layer, wrong causes, or no answer.
```

### 4. Metadata
Tags that tell you what capability the question tests. Used to break down scores by category after the run.

```json
{
  "id": "net_001",
  "category": "networking",
  "difficulty": "medium",
  "type": "reasoning"
}
```

---

## The Domain for This Benchmark

For this phase, the benchmark covers **LLM and AI agent concepts** — the same domain this tutorial series teaches. This serves two purposes:

1. It tests whether Gemma can answer questions about the material covered in phases 1–5
2. It demonstrates the evaluation pattern on a domain where you can judge answer quality yourself

The benchmark has 10 questions across four categories:

| Category | Questions | What it tests |
|----------|----------|---------------|
| Fundamentals | 3 | Tokenization, context windows, temperature |
| Agent architecture | 3 | ReAct pattern, tool calling, pipeline vs agent |
| Edge AI | 2 | Local vs cloud decision, quantization tradeoffs |
| Evaluation | 2 | LLM-as-judge design, benchmark construction |

---

## Benchmark Design Principles

### Write Questions Before Running the Model
If you write questions after seeing model outputs, you unconsciously select questions the model answered well. The benchmark must be written independently of the model being tested.

### Include Hard Questions Deliberately
A benchmark where every question scores 5/5 tells you nothing. Include questions that probe the edges — questions where partial credit (3/5) is a realistic outcome.

### Balance Task Types
Not every question should be the same type. Mix factual, reasoning, and applied questions. A model that scores 5/5 on factual but 2/5 on applied questions has a specific gap — the breakdown by category reveals it.

### Version Your Benchmark
Save the benchmark as a JSON file with a version field. When you add questions, create a new version. Never modify existing questions — changes invalidate historical comparisons.

---

## Reading the Results

After running the benchmark, you have a score distribution. The aggregate average is one number — the breakdown by category is more useful.

Example output:

```
Category         Avg Score    Min    Max    Questions
fundamentals       4.7        4      5          3
agent_arch         3.8        3      5          3
edge_ai            4.5        4      5          2
evaluation         4.0        3      5          2
─────────────────────────────────────────────────
OVERALL            4.2        3      5         10
```

This tells you: the model is strong on fundamentals and edge AI, weaker on agent architecture. If you are building an agent system with this model, the 3.8 average on agent architecture questions is a risk worth investigating before deployment.

---

## Experiment — Benchmark Results

> Run on Apple M4 24 GB — 2026-04-21
> Script: `06-evaluation/code/02_benchmark_harness.py`
> Model under test: `gemma4:26b` | Judge: `gemma4:26b` | Quality gate: 4.0/5

### Category Breakdown

| Category | Avg | Min | Max | Questions |
|----------|-----|-----|-----|-----------|
| agent_architecture | 4.7 | 4 | 5 | 3 |
| edge_ai | 4.0 | 3 | 5 | 2 |
| evaluation | 5.0 | 5 | 5 | 2 |
| fundamentals | 4.3 | 4 | 5 | 3 |
| **OVERALL** | **4.5** | **3** | **5** | **10** |

**Quality gate (4.0/5): PASS**

### Per-Question Results

| ID | Score | Judge reasoning (excerpt) |
|----|-------|--------------------------|
| fund_01 | 4/5 | Accurate and covers all key points, but cuts off mid-sentence at the end |
| fund_02 | 4/5 | Excellent depth, cuts off mid-sentence at the end |
| fund_03 | 5/5 | Mathematically accurate explanation of logits and Softmax |
| agent_01 | 4/5 | Excellent explanation but cuts off before naming the fourth component |
| agent_02 | 5/5 | Accurately explains hallucination risk and stop sequence purpose |
| agent_03 | 5/5 | Excellent concrete example distinguishing hardcoded vs dynamic fallback |
| edge_01 | 5/5 | Three distinct, accurate scenarios with technical depth |
| edge_02 | 3/5 | Correct general categories but misses specific metrics (2.5x, factual recall) |
| eval_01 | 5/5 | Comprehensive, multi-faceted impact analysis |
| eval_02 | 5/5 | Accurately identifies selection and confirmation bias |

### Key Findings

**Recurrent failure mode — token limit truncation.** Three of the four 4/5 scores (fund_01, fund_02, agent_01) were caused by responses cutting off mid-sentence, not by factual errors. The answers were correct but incomplete because the 600-token `num_predict` cap was hit. Increasing the limit to 800–1,000 would likely raise these to 5/5.

**One genuine gap — edge_02.** The model correctly identified general patterns from the E2B vs 26B benchmark but did not recall specific numbers (2.5x speedup, which task types scored identically). This is expected — specific benchmark results from this tutorial series are not in Gemma's training data. The model needs retrieval (RAG) to answer questions about its own performance data accurately.

**Evaluation category scored highest (5.0/5).** The model has strong meta-knowledge about evaluation methodology — it correctly explained verbosity bias, benchmark independence, and the risks of post-hoc question writing.

**Total benchmark time: 360 seconds (6 minutes)** for 10 questions + 10 judge calls, all local. Zero API cost.

---

## The Quality-vs-Cost Decision Matrix

Once you have benchmark scores across multiple models, you can make the routing decision quantitatively:

| Model | Avg score | Avg latency | Cost/1K tokens | Use when |
|-------|----------|------------|----------------|---------|
| gemma4:e2b | [from benchmark] | ~400ms | $0 | Acceptable quality, speed required |
| gemma4:26b | [from benchmark] | ~1,200ms | $0 | Quality required, local |
| claude-sonnet | [from benchmark] | ~800ms | $3.00 | Frontier quality required |

If E2B scores 4.2/5 and 26B scores 4.7/5 for your domain, the question is: is 0.5 points worth 3x the latency? For most tasks, no. For high-stakes tasks (medical, legal, financial), potentially yes.

The benchmark gives you the data to make this decision. Without it, you are guessing.

---

## Enterprise Implication

In production, a domain benchmark is a regression suite. Every deployment goes through it:

1. Model version changes → run benchmark → compare to previous
2. Prompt engineering changes → run benchmark → did quality improve?
3. New data or retrieval strategy → run benchmark → did context quality improve?

The benchmark is the quality gate. If a change scores below the acceptance threshold, it does not ship.

This is the same discipline that software teams apply to unit tests. The difference is that LLM regression testing catches quality degradation that unit tests cannot — a prompt change that makes the code correct but the output less useful will pass all unit tests and fail the benchmark.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Domain benchmark | A test set of questions drawn from the actual distribution of requests your system handles |
| Reference answer | The correct answer written by a domain expert, used as the gold standard |
| Score distribution | The spread of scores across benchmark questions — more informative than the average alone |
| Quality gate | A minimum benchmark score that a model or prompt must achieve before deployment |
| Regression testing | Running the benchmark after every change to detect quality degradation |
| Category breakdown | Aggregate scores grouped by question category — reveals specific capability gaps |

---

## Next

Build the benchmark — `code/02_benchmark_harness.py` runs 10 domain-specific questions through Gemma, scores each with the LLM judge, and produces a report with category breakdown and pass/fail against a quality gate.
