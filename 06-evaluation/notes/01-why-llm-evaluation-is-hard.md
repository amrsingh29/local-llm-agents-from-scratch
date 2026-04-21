# Why LLM Evaluation Is Hard

## The Problem with "It Seems Good"

The most common way teams evaluate an LLM in practice is by running a few prompts, reading the outputs, and deciding it "seems good." This works during initial exploration. It fails as soon as the system is under any production load.

The failure modes:

- The prompts you tested are the prompts you wrote — they reflect your assumptions, not the full range of user requests
- "Seems good" is not reproducible — a different engineer running the same test may reach a different conclusion
- There is no baseline — you cannot tell if the model is getting better or worse across versions
- Edge cases are invisible — the cases that matter most in production (ambiguous questions, adversarial inputs, domain-specific queries) are precisely the ones you did not think to test

Evaluation is not optional. It is the difference between a system you can deploy with confidence and one that surprises you in production.

---

## Why LLMs Are Uniquely Hard to Evaluate

Traditional software has deterministic outputs — a function that adds two numbers either returns the right answer or it does not. LLMs do not.

### Problem 1 — Non-Determinism

Run the same prompt twice at temperature > 0 and you get different outputs. Both may be "correct" but different. A naive eval that checks for exact string match will report failures that are not failures.

**Example:**
```
Prompt: "Explain attention in one sentence."

Run 1: "Attention allows a model to weight the importance of each token
        relative to every other token in the sequence."

Run 2: "The attention mechanism enables a model to focus on the most
        relevant parts of the input when generating each output token."
```

Both are correct. Neither matches the other. Exact match evaluation would score both runs as failures against any fixed reference answer.

### Problem 2 — Subjectivity

Many LLM tasks do not have a single correct answer. Summarisation, explanation, tone, format — these are quality judgements, not binary outcomes. Two evaluators reading the same output may give it different scores for legitimate reasons.

### Problem 3 — Benchmark Gaming

Models trained on internet data have likely seen standard benchmark questions (MMLU, HellaSwag, HumanEval). High scores on these benchmarks tell you the model is good at those specific questions — not that it is good at your specific domain.

**The gap:** a model can score 90% on MMLU (general knowledge multiple choice) and score 50% on your domain-specific evaluation (IT change management, medical triage, legal clause extraction). The benchmark score is not a proxy for domain performance.

### Problem 4 — Length Bias

LLM judges — including humans — tend to rate longer, more detailed responses higher, even when a shorter, more precise answer is better. This is known as verbosity bias. If your judge (human or model) has verbosity bias, you will inadvertently train and select for verbose models.

### Problem 5 — Position Bias

When evaluating two answers side-by-side (A vs B), both human and model judges tend to prefer whichever answer was presented first. This is position bias. A rigorous evaluation randomises the order and checks for consistency.

---

## What Good Evaluation Looks Like

A production-grade evaluation system has five properties:

### 1. Domain-Specific Questions
Not "what is photosynthesis?" but "given this IT change request, what is the risk level and why?" The questions must reflect the actual distribution of requests your system will receive.

### 2. Reference Answers (Where Possible)
For questions with objectively correct answers (calculations, factual lookups, code correctness), use reference answers. For subjective tasks, use scoring rubrics instead of exact answers.

### 3. A Reproducible Scoring Mechanism
Human evaluation is the gold standard but does not scale. LLM-as-judge (covered in the next note) gives reproducible, scalable scoring at near-zero cost when using a local model.

### 4. A Fixed Test Set
The benchmark is frozen once written. Adding questions mid-evaluation inflates scores because you are now selecting questions the model can answer. Write the benchmark before you run it.

### 5. A Baseline
Run the benchmark on day one. Every subsequent run is compared to the baseline. A model that scores 78% today and 75% next week after a prompt change has regressed — you need numbers to see this.

---

## The Three Evaluation Approaches

| Approach | When to Use | Limitation |
|----------|------------|-----------|
| Human evaluation | Final sign-off on high-stakes tasks | Slow, expensive, does not scale |
| LLM-as-judge | Development, regression testing, automated CI | Judge has its own biases — calibrate against human scores |
| Automated metrics (BLEU, ROUGE) | Translation, summarisation with reference answers | Poor correlation with human judgment on open-ended tasks |

Most practical evaluation systems use all three: automated metrics and LLM-as-judge for continuous feedback, human evaluation as a periodic audit.

---

## The Evaluation Mindset

Evaluation is not a one-time activity. It is a continuous process:

```
Write benchmark → Run against model A → Establish baseline
                                ↓
                    Change prompt / swap model
                                ↓
                    Run benchmark again → Compare to baseline
                                ↓
                    Did quality improve, regress, or hold?
```

Every time you change the model, the prompt, the context strategy, or the tool set, you run the benchmark. The benchmark is the contract between your changes and your system's quality.

---

## Enterprise Implication

In enterprise AI deployments, evaluation serves two distinct audiences:

**The engineering team** needs a signal for every code change — did this prompt refactor hurt quality on the payment processing questions? Did the context window increase help on long-document queries?

**The business stakeholders** need a periodic report — the system answered 94% of customer questions correctly this quarter, up from 89% last quarter, with a 12% reduction in escalation rate.

These are the same evaluation data viewed at different frequencies and granularities. The investment in building a rigorous benchmark pays back in both directions: faster iteration for engineers, clearer ROI evidence for the business.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Non-determinism | The property of LLMs that identical prompts produce different outputs across runs |
| Benchmark gaming | When a model scores well on a benchmark because it was trained on similar questions, not because it generalises |
| Verbosity bias | The tendency of evaluators (human and model) to prefer longer responses regardless of actual quality |
| Position bias | The tendency to prefer whichever answer appears first in a side-by-side comparison |
| Reference answer | A known-correct answer used as the gold standard for scoring a response |
| Scoring rubric | A structured description of what a 1/5, 3/5, and 5/5 answer looks like, used when no single correct answer exists |
| Baseline | The first evaluation score, against which all future scores are compared |

---

## Next

**LLM-as-Judge** — using Gemma to score Gemma outputs. The pattern that makes evaluation scalable and free.
