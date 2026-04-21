# Temperature and Sampling — Controlling Output Randomness

## The Wrong Mental Model

"Temperature controls quality. Lower is better."

This is wrong. Temperature controls **randomness**, not quality. The right temperature depends entirely on the task. A temperature that produces perfect creative writing will produce wrong answers for factual queries — and vice versa.

---

## The Simple Explanation First

### The Model is a Predictive Autocomplete

You know how your phone keyboard suggests the next word as you type? The model does the exact same thing — but for every single word in its response.

When you ask Gemma "Write the opening sentence of a mystery novel set in Tokyo", the model does not think up the whole sentence at once. It works **one word at a time**:

```
"The" → what comes next?
"The neon" → what comes next?
"The neon glow" → what comes next?
```

At each step, the model ranks every word by how likely it is to come next. Think of it as a leaderboard:

```
Position 1:  "glow"      — 45% chance
Position 2:  "lights"    — 22% chance
Position 3:  "blur"      — 11% chance
Position 4:  "haze"      —  8% chance
Position 5:  "shimmer"   —  5% chance
...
Position 500: "elephant"  —  0.001% chance
```

**Temperature controls which position the model picks from.**

```
temp=0.0 → always pick position 1 (safest, always "glow")
temp=0.7 → usually top 3, occasionally lower (natural, varied)
temp=1.5 → the whole leaderboard is fair game (surprising, unpredictable)
```

### The Talent Show Analogy

Think of temperature like a talent show scoring rule:

- **temp=0:** The judge always picks the contestant with the highest score. Safe, predictable — but you always get the same winner.
- **temp=0.7:** The judge mostly picks from the top 3, but occasionally a wildcard from position 5 wins. Results feel fresh without being chaotic.
- **temp=1.5:** Even contestants ranked 50th have a real shot. Occasionally a hidden gem, occasionally a disaster.

### Top-p and Top-k — Just Guardrails

Before the pick happens, these two settings cut off the bottom of the leaderboard so that truly absurd words never win.

**Top-k:** "Only consider the top K candidates"
```
top_k=1:   only position 1 → same as temp=0
top_k=10:  only top 10 positions eligible
top_k=100: top 100 positions eligible
```

**Top-p:** "Only consider candidates until their probabilities add up to p%"
```
top_p=0.9: keep adding candidates until their probabilities sum to 90%
```
If "glow" alone is 95% likely, it covers 90% by itself — nothing else competes. If the top 10 words each have ~9% probability, all 10 get in. Top-p is smarter than top-k because it adapts to how confident the model is.

### The One-Sentence Rule

**Use low temperature when you need the right answer. Use high temperature when you want surprising ideas.**

| Task | Temperature | Why |
|------|------------|-----|
| "What's 2+2?" | 0.0 | One correct answer |
| "Fix this bug" | 0.1 | Logic must be right |
| "Summarize this" | 0.3 | Faithful but natural |
| "Write me an email" | 0.7 | Human-sounding |
| "Write a poem" | 0.9 | Surprise is the point |
| "Brainstorm 10 ideas" | 1.1 | Maximum diversity |

---

## How the Model Picks the Next Token — The Technical Detail

For those who want to understand what is happening under the hood:

At each step, the model computes a **probability distribution** over all tokens in its vocabulary (~250,000 tokens for Gemma). Every token gets a probability score. The model then **samples** from this distribution to pick the next token.

Example — the model has just processed "The capital of France is":

```
Token         Raw score (logit)    Probability
"Paris"           8.4               94.2%
"a"               3.1                2.1%
"the"             2.8                1.5%
"located"         2.1                0.8%
"known"           1.9                0.6%
... (249,995 more tokens, all near 0%)
```

With no temperature adjustment, the model samples from these probabilities. "Paris" wins almost every time — but not always.

---

## What Temperature Does Mathematically

Temperature scales the raw scores (logits) before converting to probabilities:

```
adjusted_logit = raw_logit / temperature
```

**Temperature = 1.0 (default):** no change. Sample from the natural distribution.

**Temperature < 1.0 (e.g., 0.1):** divide by a small number → logits get larger → probabilities become more extreme → the highest-probability token dominates.

```
temp=0.1:
  "Paris"  → 99.99%
  everything else → near 0%
```

**Temperature > 1.0 (e.g., 1.5):** divide by a large number → logits shrink → probabilities flatten → lower-ranked tokens become more competitive.

```
temp=1.5:
  "Paris"   → 61%
  "a"       → 12%
  "the"     → 10%
  "Lyon"    →  6%
  "famous"  →  4%
  ...
```

**Temperature = 0:** mathematically, dividing by zero → the model always picks the single highest-probability token. Fully deterministic (also called greedy decoding).

---

## Top-p: Nucleus Sampling

Temperature adjusts probabilities but still allows the entire vocabulary to compete. **Top-p** (nucleus sampling) adds a hard filter: only consider tokens whose cumulative probability reaches the threshold p.

Example with top_p = 0.9:

```
Token         Probability    Cumulative
"Paris"          94.2%          94.2%  ← stop here, cumulative > 90%
"a"               2.1%          96.3%  ← excluded
"the"             1.5%          97.8%  ← excluded
...
```

At top_p=0.9, only "Paris" is eligible. The model always picks "Paris."

With a more uncertain distribution (creative prompt):

```
Token           Probability    Cumulative
"crimson"          18%           18%
"an"               14%           32%
"blue"             12%           44%
"the"              10%           54%
"like"              9%           63%
"not"               8%           71%
"simply"            7%           78%
"just"              6%           84%
"perhaps"           5%           89%  ← stop here, cumulative ≥ 90%
"purely"            4%           93%  ← excluded
...
```

At top_p=0.9, nine tokens compete. The model samples from those nine. Low-quality tokens with probability <1% are excluded regardless of temperature.

**Top-p is a quality floor.** Temperature controls how much randomness within the eligible set. Top-p controls which tokens are eligible at all.

---

## Top-k: Hard Candidate Limit

**Top-k** is simpler: only the top K tokens by probability are eligible, regardless of their actual probability values.

```
top_k=1:  only the single most likely token → identical to temperature=0 (greedy)
top_k=10: only the 10 most likely tokens compete
top_k=40: the 40 most likely tokens compete (common default)
top_k=0:  disabled — no hard limit (rely on top_p alone)
```

Top-k is cruder than top-p but computationally cheaper. Most production systems use both together: top-k filters first, then top-p refines within the remaining candidates.

---

## The Sampling Pipeline

The full sequence for each generated token:

```
Raw logits (250,000 scores)
      ↓  divide by temperature
Scaled logits
      ↓  softmax → probabilities
Probability distribution
      ↓  apply top-k (keep top K)
Filtered distribution
      ↓  apply top-p (keep cumulative p%)
Nucleus
      ↓  sample one token
Next token ID
      ↓  detokenize
Next piece of text
```

Every token you see in a model's response was produced by running this pipeline once.

---

## The Experiments

> Run against Gemma 4 26B on Apple M4 24 GB — 2026-04-20
> Script: `03_temperature_experiments.py`

### Experiment 1 — Temperature Controls Variance

Prompt: *"Write the opening sentence of a mystery novel set in Tokyo."*

**temp=0.0 — Deterministic (3/3 identical):**
```
Run 1: The neon glow of Shinjuku bled into the rain-slicked pavement, masking the single, crimson drop that had escaped the vic...
Run 2: [identical]
Run 3: [identical]
```

**temp=0.7 — Maximum variance (3/3 unique):**
```
Run 1: ...masking the single, crimson smear that lay cooling beneat...
Run 2: ...masking the single drop of blood that had escaped the vic...
Run 3: ...casting long, distorted shadows that seemed to swallow th...
```

**temp=1.5 — Maximum variance (3/3 unique):**
```
Run 1: ...masking the single, crimson smear left behind on the stat...
Run 2: ...masking the fact that the body under the dumpster...
Run 3: The neon lights of Shinjuku bled into the puddles of a midnight downpour...
```

Finding: temp=0 is perfectly deterministic. Both 0.7 and 1.5 produce unique outputs every run. Notably, temp=1.5 diverges more strongly — "The neon lights" vs "The neon glow", different sentence structures entirely. The model's most likely token ("The neon glow of Shinjuku") still dominates at 0.7 but gets displaced at 1.5.

### Experiment 2 — Temperature vs Factual Accuracy

Prompt: *"What is the capital of France, and in what year did the Eiffel Tower open?"*
Correct answer: Paris, 1889

| Temperature | Result | Answer |
|------------|--------|--------|
| 0.0 | CORRECT | The capital of France is Paris, and the Eiffel Tower opened in 1889. |
| 0.7 | CORRECT | The capital of France is Paris, and the Eiffel Tower opened in 1889. |
| 1.2 | CORRECT | The capital of France is Paris, and the Eiffel Tower opened in 1889. |
| 1.8 | CORRECT | The capital of France is Paris, and the Eiffel Tower opened in 1889. |

Finding: Gemma 4 26B is robust enough that even at temp=1.8, well-known facts stay correct. This reflects strong training — "Paris" and "1889" are so dominant in the probability distribution that even a flattened distribution still picks them. The accuracy degradation from temperature is more visible on obscure facts, complex reasoning chains, and arithmetic — not trivia that appeared millions of times in training data.

### Experiment 3 — Top-p Effect

Prompt: *"Describe the colour blue in an unusual way."* Temperature fixed at 0.7.

**top_p=0.1:**
> Blue is the sound of a cello played in an empty cathedral — a low, resonant vibration that settles in the marrow of your bones. It is not a color so much as it is a temperature; it is the precise moment...

**top_p=0.5:**
> Blue is the sound of a cello played in an empty cathedral — a low, resonant vibration that settles in the marrow of your bones. It is not a color so much as it is a temperature; it is the precise moment...

**top_p=0.95:**
> Blue is the sound of a cello played in an empty cathedral — a low, resonant vibration that doesn't sit on the surface of things, but sinks into the marrow. It is not a color so much as it is a distance...

Finding: top_p=0.1 and top_p=0.5 produced identical output — the cello/cathedral metaphor is so dominant in the probability distribution that even widening the nucleus to 50% doesn't change which tokens win. At top_p=0.95, the response diverges slightly ("doesn't sit on the surface" vs "settles in the marrow", "a distance" vs "a temperature"). The effect of top_p is subtle when temperature is moderate.

### Experiment 4 — Top-k Effect

Prompt: *"What should I name my new coffee shop? Give one creative name."* Temperature fixed at 0.8.

| top_k | Response |
|-------|----------|
| 1 | **Velvet Brew** |
| 10 | **Velvet Brew** |
| 100 | **Velvet Brew** |

Finding: all three produced the same answer. "Velvet Brew" is so strongly favored by the model that restricting to top_k=1 (greedy) or expanding to top_k=100 makes no difference — the winner is clear regardless. top_k matters most when the distribution is flat (many tokens competing equally). For a naming task with a creative prompt, the model converges on one answer confidently.

### Experiment 5 — Right Temperature for the Task

**Factual Q&A (temp=0.0):**
> The boiling point of water at sea level is 100 degrees Celsius.

**Code generation (temp=0.1):**
> There are several ways to implement this in Python. Here are the three most common methods: recursion, iteration, math.factorial...

**Creative writing (temp=0.9):**
> Screen glows in the dark, / Searching for a missing dot, / Coffee's running low.

**Brainstorming (temp=1.1):**
> To create truly "unusual" business ideas, we have to move beyond the standard "AI-powered coffee recommendation app." Instead, we should look at the intersection of sensory science, predictive logistics, and hyper-personalization...

Finding: the task-to-temperature mapping works exactly as expected. Factual and code tasks give precise, direct answers. Creative writing at temp=0.9 produced a genuinely good haiku. Brainstorming at temp=1.1 produced a thoughtful meta-framing before diving into ideas — the model's creativity extended to how it approached the problem, not just the content.

### The Gemma 4 Thinking Mode Discovery

During debugging, we discovered that Gemma 4 is a **thinking model** — it uses extended reasoning by default, similar to Claude's extended thinking. Each response has two fields:

- `thinking` — internal reasoning (chain of thought, planning)
- `content` — the final answer shown to the user

With `num_predict` set too low, the model exhausts its token budget on thinking and produces empty content. Solution: either set `think: false` to disable thinking, or increase `num_predict` to give the model budget for both.

```python
payload = {
    "model": "gemma4:26b",
    "messages": [{"role": "user", "content": prompt}],
    "think": False,       # disable thinking for fast, direct responses
    "options": {"num_predict": 150},
}
```

This is a critical production consideration: thinking mode produces better reasoning but costs more tokens and time. Disable it for simple tasks (classification, extraction, factual Q&A). Keep it enabled for complex reasoning tasks.

---

## The Right Temperature by Task Type

This is the practical output of the experiments:

| Task | Temperature | top_p | Reasoning |
|------|------------|-------|-----------|
| Factual Q&A | 0.0 | 0.9 | Need the most likely correct answer |
| Code generation | 0.1 | 0.9 | Logic must be correct, minor variation acceptable |
| Summarization | 0.3 | 0.9 | Faithful to source, slightly varied phrasing |
| Chat / conversation | 0.7 | 0.9 | Natural, varied but coherent |
| Creative writing | 0.9–1.0 | 0.95 | Variety and surprise are desirable |
| Brainstorming | 1.1–1.3 | 0.95 | Maximum idea diversity |
| Data extraction | 0.0 | — | Deterministic, no variation acceptable |

These are starting points, not fixed rules. Always benchmark against your specific task.

---

## Why temp=0 Is Not Always "Best"

A common mistake: set temperature=0 for everything to get "reliable" outputs.

The problem: at temperature=0, the model always picks the single highest-probability token. For creative or open-ended tasks, that means the model produces the most statistically average response — safe, expected, boring, and often unhelpful.

For brainstorming, you want token 7 on the probability list to win sometimes. That is where the surprising, useful ideas live.

For code generation, you want token 1 almost always — but occasionally token 2 or 3 gives you a cleaner implementation. A small temperature (0.1) allows this without risking wrong logic.

Temperature is not a quality dial. It is a creativity-vs-precision dial.

---

## The Enterprise Implication

Different parts of the same system need different temperatures:

```
User submits a support ticket
      ↓
Classification agent (temp=0.0)  ← deterministic, must be consistent
      ↓
Retrieval query generation (temp=0.2)  ← slight variation improves recall
      ↓
Answer generation (temp=0.4)  ← natural phrasing, faithful to source
      ↓
Response quality check (temp=0.0)  ← binary pass/fail, no randomness
```

Treating temperature as a single system-wide setting is a design mistake. Each agent or step in your pipeline should set temperature independently based on its task.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Temperature | Scales logits before sampling — lower = more deterministic, higher = more random |
| Logits | Raw unnormalized scores the model assigns to each token |
| Softmax | Converts logits to probabilities that sum to 1 |
| Greedy decoding | Always pick the highest-probability token (temperature=0) |
| Top-p (nucleus sampling) | Only sample from tokens whose cumulative probability reaches p |
| Top-k | Only sample from the top K tokens by probability |
| Nucleus | The set of tokens that pass the top-p filter |

---


## Full Code

```python title="03_temperature_experiments.py"
--8<-- "02-llm-fundamentals/code/03_temperature_experiments.py"
```

## Next

**Statelessness — Why LLMs Forget** — every API call starts fresh, and what that means for building systems that appear to have memory.
