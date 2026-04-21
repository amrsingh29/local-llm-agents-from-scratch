# Tokens From First Principles

## The Wrong Mental Model

Most developers who start working with LLMs think in words. They ask: "how many words can the model handle?" or "how many words did that cost me?" This mental model is wrong, and it causes real problems.

The model does not see words. It sees **tokens**.

---

## What a Token Is

A token is a chunk of text — but not necessarily a word, a character, or a syllable. It is a unit defined by the model's **vocabulary**, which was built during training using an algorithm called **Byte Pair Encoding (BPE)** or a variant of it.

The training algorithm analyzed a massive corpus of text and repeatedly merged the most frequently occurring pairs of characters or character sequences. The result is a vocabulary of 250,000+ tokens — some are single characters, some are common words, some are word fragments, some are multi-word phrases.

**Examples from Gemma's vocabulary:**

| Token | What it represents |
|-------|-------------------|
| `▁the` | The word "the" with a leading space |
| `▁running` | The word "running" with a leading space |
| `ing` | The suffix "ing" (used for rare words: "run" + "ning") |
| `▁Kubernetes` | The full word, common enough to be one token |
| `micro` | A prefix fragment |
| `▁services` | The word "services" |
| `▁micro` + `services` | "microservices" split into two tokens |

The leading `▁` (underscore) marks the beginning of a word — it indicates a space came before this token in the original text.

---

## Why Words ≠ Tokens

Three examples that break the word = token assumption:

**1. Common words are often single tokens**
"cat" → 1 token
"the" → 1 token
"running" → 1 token

**2. Rare or long words split into multiple tokens**
"Supercalifragilisticexpialidocious" → ~10 tokens
"microservices" → 2 tokens (micro + services)
"Kubernetes" → 1 token (common enough in training data)

**3. Punctuation and capitalization add tokens**
"cat" → 1 token
"cat." → 2 tokens (cat + period)
"Cat" → might be a different token than "cat"
"CAT" → possibly 2–3 tokens

The practical rule: **English prose averages 3–4 characters per token. But this varies enormously by content type.**

---

## The Chars-Per-Token Reality by Content Type

Based on experiments run against Gemma 4 26B:

| Content type | Chars/token | Why |
|-------------|------------|-----|
| Plain English | ~4.5 | Common words, efficient encoding |
| Technical jargon | ~4.0 | Mixed — some terms are single tokens |
| Python code | ~3.5 | Operators, indentation, brackets are costly |
| JSON | ~3.0 | Quotes, colons, brackets add overhead |
| Non-English (Hindi, Arabic, CJK) | ~1.5–2.5 | Rare in training data, encodes character by character |
| Numbers | ~3.0 | Each digit group is often a separate token |

**The non-English finding is critical for enterprise applications.** If your system processes Arabic contracts, Hindi support tickets, or Japanese documentation, your token costs and context window usage will be 2–3x higher than an equivalent English workload.

---

## The Tokenization Pipeline

When you send a prompt to Gemma via Ollama, this happens before any neural network computation:

```
Raw text (string)
      ↓
Tokenizer splits text into tokens
      ↓
Each token looked up in vocabulary → integer ID
      ↓
Sequence of integer IDs sent to the model
      ↓
Model processes IDs, outputs probability over next ID
      ↓
Sampled ID converted back to text via vocabulary
      ↓
Detokenization: IDs → text → returned to your application
```

The model never sees letters. It sees numbers. "Hello" might be token ID 4906. The model learns that token 4906 appears near token 3421 ("world") often enough to predict it. Language understanding is pattern matching over integer sequences.

---

## Why This Matters: Context Windows

The model has a maximum sequence length — the **context window**. For Gemma 4 26B, that is 256,000 tokens. Every token in your prompt and every token the model generates counts against this limit.

When the context window fills up, the model either:
- Stops (hard limit)
- Truncates the beginning of the conversation (sliding window)
- Loses coherence as earlier tokens fall out of attention range

This is why "256K context" does not mean "unlimited memory." It means 256,000 tokens — roughly 190,000 words of English prose, but far less for code or non-English text.

---

## The Cost Dimension

For cloud API providers (OpenAI, Anthropic, Google), you pay per token — both input and output. Tokens are the billing unit.

For local inference (Ollama + Gemma), you pay in **time and compute** rather than money. More tokens = longer inference time = more GPU cycles.

**What this means for prompt design:**

Verbose prompt (enterprise-style, lots of context-setting):
```
You are an expert technical writer with 20 years of experience...
Please provide a comprehensive, well-structured summary...
Focus on key points, main arguments, and actionable conclusions...
Write in a professional tone suitable for a business audience.
```
→ ~60 tokens of instruction overhead per call

Concise prompt:
```
Summarize this document. Be concise and professional.
```
→ ~10 tokens of instruction overhead per call

The difference is 41 tokens per call (measured: 21 vs 62 tokens). At 10,000 calls/day on a cloud API at $1/million tokens:
- Extra cost per day: $0.41
- Extra cost per year: $150

Trivial at this scale. Not trivial at 10 million calls/day — where it becomes $150,000/year in prompt verbosity alone.

**Local inference implication:** those 41 extra tokens per call add ~1.6 seconds of processing time at 25 tok/sec. At 1,000 concurrent users, that is 1,600 seconds of wasted GPU time per request cycle.

Prompt engineering is not just craft. It is cost engineering.

---

## The Tokenization Experiments

> Run against Gemma 4 26B on Apple M4 24 GB — 2026-04-20
> Script: `01_tokenization_experiments.py`

### How We Counted Tokens — The `num_predict: 0` Trick

Ollama does not expose a dedicated tokenization endpoint. But every response it returns includes `prompt_eval_count` — the exact number of tokens it processed from your prompt.

We exploit this by sending text with `num_predict: 0`, which tells the model: tokenize my input, run one forward pass, then stop — generate nothing.

```python
payload = {
    "model": "gemma4:26b",
    "prompt": "some text to count",
    "stream": False,
    "options": {"num_predict": 0},
}
response = requests.post(OLLAMA_URL, json=payload)
token_count = response.json()["prompt_eval_count"]
```

What Gemma does on each call:

```
We send:  { prompt: "some text", num_predict: 0 }

Gemma:
  1. Tokenize text → sequence of integer IDs
  2. Load IDs into the transformer
  3. Run one forward pass to prepare for generation
  4. Stop — generate 0 tokens
  5. Return: { prompt_eval_count: N }

We read: N
```

**Gemma never generated any text in this entire script.** It was used purely as a tokenizer and token counter — not as a language model. This is a useful pattern any time you need to measure token cost without paying the inference cost of full generation.

### Experiment 1 — Words Are Not Tokens

| Text | Words | Tokens | Ratio |
|------|-------|--------|-------|
| Simple words | 4 | 20 | 5.0x |
| Same words with punctuation | 4 | 24 | 6.0x |
| Supercalifragilisticexpialidocious | 1 | 26 | 26.0x |
| Common phrase | 4 | 20 | 5.0x |
| Repeated word (x5) | 5 | 21 | 4.2x |
| Capitalization change (hello/Hello/HELLO) | 3 | 20 | 6.67x |

Finding: one rare word (26 tokens) costs as much as an entire 5-word sentence. The word-to-token ratio is meaningless as a planning unit.

### Experiment 2 — Chars Per Token by Content Type

| Content type | Chars | Tokens | Chars/Token |
|-------------|-------|--------|------------|
| Plain English prose | 114 | 36 | **3.2** |
| Technical jargon | 112 | 33 | **3.4** |
| Python code | 89 | 45 | **2.0** |
| JSON data | 101 | 70 | **1.4** |
| Non-English (Hindi) | 33 | 26 | **1.3** |
| Numbers | 39 | 55 | **0.7** |
| Whitespace heavy | 46 | 23 | **2.0** |

Finding: numbers are the most expensive content type — nearly one token per digit. JSON and non-English text are 2–3x more expensive than plain English. Code is 60% more expensive than prose. The "4 chars per token" rule only approximately holds for plain English prose.

### Experiment 3 — Prompt Token Cost

| Prompt | Tokens |
|--------|--------|
| "Summarize this document." | 21 |
| Verbose expert-framing prompt | 62 |
| **Overhead** | **+41 tokens** |

At 10,000 API calls/day ($1/million tokens):
- Extra tokens/day: 410,000
- Extra cost/day: $0.41
- Extra cost/year: **$150**

Finding: verbose prompts are a modest cost at small scale but compound significantly at enterprise volume. Local inference implication: 41 extra tokens = ~1.6 seconds of extra GPU time per call at 25 tok/sec.

### Experiment 4 — Phrasing Impact

| Short | Tokens | Verbose | Tokens | Overhead |
|-------|--------|---------|--------|----------|
| "Use AI." | 19 | "Please utilize artificial intelligence technologies." | 22 | +3 |
| "List 3 bugs." | 21 | "Please enumerate exactly three software defects..." | 27 | +6 |
| "Why?" | 18 | "Could you please explain the underlying reasoning..." | 27 | +9 |
| "Fix the error." | 20 | "Please correct the mistake and ensure it does not..." | 30 | +10 |

Finding: polite, verbose phrasing adds 3–10 tokens per prompt with no improvement in model output quality. In high-volume systems, this is a measurable engineering cost.

---

## What the Model Does Not Know About Tokens

The model has no concept of "word boundaries" or "sentences." It processes a flat sequence of integers. Punctuation, newlines, and spaces only matter insofar as they affect which tokens appear in sequence.

This has a subtle implication: **the model's reasoning is token-level, not word-level.** When it generates text, it is predicting the next token ID, not the next word. The output happens to look like words because the tokenizer reconstructs readable text from the IDs — but the underlying computation is over integers.

This is why models sometimes produce odd spacing, strange hyphenation, or mid-word line breaks when generating long outputs. These are artifacts of the token-to-text reconstruction, not the model misunderstanding language.

---

## Enterprise Takeaways

**For cost estimation:**
- Do not estimate token costs from word counts — measure them
- Non-English content costs 2–3x more tokens than English
- Code and JSON cost more than prose

**For context window planning:**
- Always measure prompt token count before scaling
- Leave headroom — filling to 95% of context degrades quality (covered in the next experiment)
- System prompts + conversation history grow with each turn in a chat application

**For prompt design:**
- Concise prompts are not just clean code — they are cost optimization
- Every token of instruction overhead is subtracted from the content the model can process

---

## Key Terms

| Term | Definition |
|------|-----------|
| Token | A chunk of text as defined by the model's vocabulary |
| Vocabulary | The fixed set of all tokens the model knows (250K+ for Gemma) |
| BPE (Byte Pair Encoding) | Algorithm that builds the token vocabulary by merging frequent character pairs |
| Tokenization | Converting raw text to a sequence of token IDs |
| Detokenization | Converting token IDs back to readable text |
| Context window | Maximum number of tokens the model can process in one call |
| prompt_eval_count | Ollama's field reporting how many tokens were in your prompt |

---


## Full Code

```python title="01_tokenization_experiments.py"
--8<-- "02-llm-fundamentals/code/01_tokenization_experiments.py"
```

## Next

**Context Window Limits and the Lost-in-the-Middle Problem** — why 256K tokens does not mean the model pays equal attention to all of it, and what happens when you push toward the limit.
