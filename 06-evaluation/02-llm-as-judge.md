# LLM-as-Judge

## The Pattern

LLM-as-judge means using a language model to evaluate another language model's output. Instead of a human reading every response and assigning a score, the judge model does it automatically.

```
Question + Response + Rubric
            ↓
      [Judge Model]
            ↓
   Score (1–5) + Reasoning
```

When the judge runs locally (Gemma 26B evaluating Gemma outputs), the cost is zero and the throughput is limited only by your hardware. You can evaluate thousands of responses overnight with no API bill.

---

## Why It Works

The judge model is not checking a lookup table — it is performing genuine quality assessment. Given a question, a response, and a rubric, a capable model can:

- Identify factual errors
- Detect missing key points
- Recognise format violations
- Flag hallucinations (when a reference answer is provided)
- Distinguish a complete answer from a partial one

This is the same reasoning capability that makes LLMs useful for other tasks. The judge is just reasoning about text quality instead of reasoning about a domain question.

---

## The Judge Prompt Design

The judge prompt has four components:

### 1. Role and Task
Tell the model it is an evaluator, not an assistant. This suppresses the tendency to be helpful and agree with the answer being evaluated.

```
You are an expert evaluator. Your task is to score the following response
on a scale from 1 to 5. Be critical and precise.
```

### 2. The Question and Response
The exact question that was asked, and the exact response being evaluated.

### 3. The Rubric
The rubric is the most important part. It defines what each score means for this specific task type. A vague rubric produces noisy scores.

```
Score 5: Fully correct, complete, clear. Covers all key points, no errors.
Score 4: Mostly correct. Minor omission or imprecision, but not misleading.
Score 3: Partially correct. Answers part of the question but misses important points.
Score 2: Mostly wrong or incomplete. Correct fragments but overall misleading.
Score 1: Completely wrong, irrelevant, or harmful.
```

### 4. Output Format Constraint
Force a structured output — JSON with a `score` and `reason` field. This makes scores parseable without post-processing.

```
Respond ONLY with a JSON object: {"score": <1-5>, "reason": "<one sentence>"}
```

---

## Calibration — The Critical Step

An uncalibrated judge is worse than no judge. If Gemma gives every response a 4/5 regardless of quality, the scores are meaningless.

**How to calibrate:**

1. Manually score 20–30 responses from your benchmark (human gold labels)
2. Run the same responses through the judge
3. Compute agreement: what percentage of judge scores match human scores within ±1 point?
4. Identify systematic biases: does the judge inflate scores? Does it penalise certain formats?
5. Adjust the rubric until agreement is above 80%

A calibrated judge does not need to be perfect — it needs to be consistent. Consistency is what makes it useful for regression testing.

---

## Known Biases in LLM Judges

### Self-Enhancement Bias
A model asked to judge outputs from itself tends to rate them higher than outputs from other models. When using Gemma to judge Gemma outputs, test a sample against a human rater to confirm the scores are not inflated.

### Verbosity Bias
As noted in the previous note, judges prefer longer answers. Counter this by explicitly including in the rubric: "A concise, complete answer should score as high as a verbose, complete answer."

### Format Bias
If the judge has seen many well-formatted markdown responses in training, it may penalise plain text responses even when the content is correct. Test the rubric against both formatted and plain text versions of the same answer.

---

## Using a Reference Answer

For questions with known correct answers, include the reference in the judge prompt:

```
Reference answer: {reference}

Evaluate how well the model's response matches the reference answer.
Penalise factual errors, missing key points, and format deviations.
```

With a reference, the judge becomes much more accurate on factual and reasoning tasks. Without a reference, the judge relies on its own knowledge — which means it can only detect errors it knows about.

---

## When Not to Use LLM-as-Judge

- **Safety-critical evaluation** — judge a medical or legal response incorrectly and the error has real consequences. Use human evaluation for these tasks.
- **Very long documents** — judges lose accuracy when the response exceeds ~4,000 tokens. Chunk and evaluate in segments.
- **Creative tasks without rubrics** — if you cannot articulate what a 5/5 response looks like, the judge cannot either. Write the rubric before running the eval.

---

## The Full Evaluation Loop

```
1. Write benchmark questions (domain-specific)
2. Write scoring rubric (what does 1/5 through 5/5 look like?)
3. Run benchmark: send each question to the model under test
4. Run judge: send each (question, response) pair to Gemma 26B
5. Collect scores + reasoning
6. Compute aggregate metrics: average score, score distribution, fail rate
7. Compare to baseline
```

Script: `06-evaluation/code/01_llm_judge.py` implements the judge. `code/02_benchmark_harness.py` implements the full loop.

---

## Experiment — Judge Calibration

> Run on Apple M4 24 GB — 2026-04-21
> Script: `06-evaluation/code/01_llm_judge.py`

Three versions of the same answer — good, partial, and wrong — were submitted to the judge to verify it discriminates correctly before running the full benchmark.

**Question used:** "What is the difference between a pipeline and an agent in AI systems?"

**Good answer** (full explanation of fixed vs dynamic, tool calling, runtime reasoning):

Score: **5/5**
> The response is fully correct, covers all key points from the reference answer, and clearly articulates the distinction between fixed sequences and dynamic reasoning.

**Partial answer** ("A pipeline runs steps in order. An agent is more flexible and can make decisions."):

Score: **3/5**
> Captures the fundamental distinction regarding flexibility and decision-making but fails to mention tool use, observation, or the role of the LLM in the agent's reasoning process.

**Wrong answer** (literal definitions — water pipelines, talent agents):

Score: **1/5**
> The model provides definitions for the literal, non-AI meanings of the words rather than addressing the context of AI systems.

**Calibration result: correct.** The judge assigned 5, 3, 1 exactly matching the expected range. The rubric anchored the scores reliably — no verbosity inflation, no leniency on the wrong answer.

---

## Key Terms

| Term | Definition |
|------|-----------|
| LLM-as-judge | Using a language model to evaluate another model's outputs |
| Rubric | A structured description of what each score level looks like for a specific task type |
| Calibration | The process of validating judge scores against human ratings to detect systematic bias |
| Self-enhancement bias | The tendency of a model to rate its own outputs more favourably than outputs from other models |
| Gold labels | Human-assigned scores used as the ground truth for calibrating the judge |
| Agreement rate | The percentage of judge scores that match human scores within an acceptable tolerance (typically ±1 point) |

---


## Full Code

```python title="01_llm_judge.py"
--8<-- "06-evaluation/code/01_llm_judge.py"
```

## Next

**Domain-Specific Benchmark** — how to write benchmark questions that actually predict real-world performance, and how to build the harness that runs them automatically.
