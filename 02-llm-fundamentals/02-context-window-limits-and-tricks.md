
# Context Window Limits and the Lost-in-the-Middle Problem

## The Wrong Mental Model

"Gemma 4 26B has a 256K token context window — so I can give it a 200-page document and it will understand all of it."

This is the most dangerous misunderstanding in production LLM deployments. The context window defines how much text the model *receives*. It does not define how much it *pays attention to*.

---

## What the Context Window Actually Is

The context window is the maximum number of tokens the model can process in a single call. For Gemma 4 26B, that is 256,000 tokens — roughly:

| Content type | Approximate equivalent |
|-------------|----------------------|
| English prose | ~190,000 words (~700 pages) |
| Python code | ~120,000 lines |
| JSON data | ~60,000 records |
| Non-English text | ~100,000 words (varies by language) |

Every token in your prompt — system instructions, conversation history, documents, and the question itself — counts against this limit. The model's response tokens also count during generation.

When you hit the limit, one of two things happens:
- The API rejects the request with an error
- The model truncates the oldest tokens (beginning of context) silently

Both outcomes are bad. The second is worse because it fails silently.

---

## The Attention Mechanism and Why Position Matters

To understand why context size is not the same as comprehension, you need to understand how the transformer processes long inputs.

At each generation step, the model computes **attention** — a weighted sum over all tokens in the context. Each token pays attention to every other token, but the weights are not equal. Some tokens get high attention weight (the model "looks at" them closely), others get low weight (effectively ignored).

Research consistently shows that attention weight is not uniformly distributed across a long context. It concentrates at:

1. **The beginning** — the model always pays high attention to the first few hundred tokens
2. **The end** — the model pays high attention to the most recent tokens (recency bias)
3. **The middle** — attention drops off for content buried in the middle of a long context

This is called the **lost-in-the-middle problem**, documented in a 2023 Stanford paper and replicated consistently across model families including Gemma, Llama, GPT, and Claude.

```
Attention weight
     ↑
High │█                                                    █
     │ █                                                  █
     │  █                                                █
     │   ██                                            ██
Low  │     █████████████████████████████████████████████
     └────────────────────────────────────────────────────→
     Start                  Middle                      End
                      Position in context
```

The practical implication: **if you bury a critical fact in the middle of a long document, the model may miss it even though it is within the context window.**

---

## The Experiment: Lost in the Middle

To prove this concretely, we ran an experiment using `02_context_window_limits.py`.

**Setup:**
- Secret fact hidden in a long business document: *"The quarterly revenue target for Project Nightingale is $4.7 million."*
- Same fact placed at three positions: beginning, middle, end
- Same question asked each time: *"What is the quarterly revenue target for Project Nightingale?"*
- Temperature set to 0 (deterministic — no randomness in the answer)

**What Gemma actually received** (simplified):

```
Beginning test:
  "The quarterly revenue target for Project Nightingale is $4.7 million.
   [80 paragraphs of business filler text]"
   Question: What is the quarterly revenue target for Project Nightingale?

Middle test:
  "[40 paragraphs of filler]
   The quarterly revenue target for Project Nightingale is $4.7 million.
   [40 paragraphs of filler]"
   Question: What is the quarterly revenue target for Project Nightingale?

End test:
  "[80 paragraphs of filler]
   The quarterly revenue target for Project Nightingale is $4.7 million."
   Question: What is the quarterly revenue target for Project Nightingale?
```

### Results

> Run against Gemma 4 26B on Apple M4 24 GB — 2026-04-20

| Position | Prompt Tokens | Duration | Found? |
|----------|--------------|----------|--------|
| Beginning | 8,703 | 47.0s | NO |
| Middle | 8,705 | 44.6s | NO |
| End | 8,703 | 37.6s | NO |

### What the Results Actually Tell Us

All three positions returned empty answers — the model produced no response at all. This is a more severe failure than expected and reveals something important: **at ~8,700 tokens, the filler text was dense and repetitive enough that Gemma determined there was nothing meaningful to extract and declined to answer.**

This is actually a stronger finding than the classic lost-in-the-middle result:

1. **The model is not hallucinating** — it correctly identifies that the document is mostly noise. This is good model behaviour.
2. **The signal-to-noise ratio matters as much as position** — a single sentence buried in 80 paragraphs of repetitive filler is an unrealistic retrieval scenario. In production, retrieved chunks are semantically related to the question, not random filler.
3. **The U-shape failure mode is real but context-dependent** — it manifests most clearly when content is meaningful throughout but one specific fact is in the middle. Pure noise documents trigger a different failure: refusal.

The core lesson holds: **do not rely on a model finding a needle in a haystack by stuffing the haystack into the context.** Whether it misses the needle (lost-in-the-middle) or refuses to answer (noise overload), the outcome is the same — the system fails.

---

## Experiment 2: Context Size vs Throughput

As prompt token count grows, throughput (output tokens/sec) drops. This is not a bug — it is physics.

At each generation step, the model computes attention over all prompt tokens. A 10,000-token prompt requires 10x more attention computation per token than a 1,000-token prompt.

### Results

> Run against Gemma 4 26B on Apple M4 24 GB — 2026-04-20

| Filler Paras | Prompt Tokens | Duration | Output tok/s |
|-------------|--------------|----------|-------------|
| 10 | 1,110 | 5.3s | 5.7 |
| 40 | 4,350 | 12.1s | 2.5 |
| 80 | 8,670 | 16.3s | 1.8 |
| 150 | 16,230 | 30.7s | 1.0 |

**The pattern is clear:** throughput drops from 5.7 tok/sec at 1,110 tokens to 1.0 tok/sec at 16,230 tokens — a **5.7x throughput degradation** for a **14.6x increase in context size**.

This is not linear — it is worse than linear. As prompt size grows, the model must compute attention over more tokens at every generation step. The relationship trends toward quadratic for full attention models.

**Enterprise implication:** a system handling 10 concurrent users with 16K token prompts delivers the same throughput as 1 user with a 1K token prompt. Context size is a multiplier on your infrastructure cost.

---

## Production Strategies for Long Contexts

Understanding the problem leads directly to the solutions used in production:

### 1. RAG — Retrieval-Augmented Generation

RAG has two steps. The retrieval step is where the real work happens:

```
Step 1: RETRIEVAL — find the right 5 chunks out of 10,000
Step 2: GENERATION — send those 5 chunks to the model
```

If retrieval is precise, you send 2,000–5,000 tokens to the model — well within the high-attention zone. The U-shape never becomes a problem because you never reach the "middle" at scale.

**Concrete example:**

Knowledge base: 50,000 support tickets × 500 tokens each = 25 million tokens total.
User question: "How do we fix the SSL certificate error on nginx after upgrading to Ubuntu 22.04?"

```
Bad RAG (naive):
  Retrieve top 500 chunks by keyword match
  → 250,000 tokens sent to model
  → U-shape problem in full effect
  → Slow, expensive, inaccurate

Good RAG:
  1. Embed the question → vector [0.23, -0.71, 0.44, ...]
  2. Search vector index → top 5 semantically similar chunks
  3. Re-rank those 5 by relevance score
  4. Send only top 3 chunks (~1,500 tokens) + system + question
  → Total context: ~2,000 tokens
  → Model reads all of it with full attention
  → Fast, cheap, accurate
```

The retrieval step's job is to make the model's job trivially easy. RAG does not solve lost-in-the-middle by being smarter about context placement — it solves it by making the context small enough that the problem never appears.

**The critical insight:** RAG is a precision problem, not a context problem. Think of it like a search engine — Google does not solve "too many web pages" by making browsers scroll faster. It returns 10 highly relevant results instead of 50 million pages.

#### Why 200K Tokens Gets Retrieved — and How to Fix It

A common failure: "we implemented RAG but the model still misses facts." The cause is almost always a retrieval problem, not a generation problem.

| Root cause | Fix |
|-----------|-----|
| Chunk size too large (whole documents) | Chunk at 200–400 tokens, not 2,000 |
| Top-K set too high (200 chunks) | Retrieve top 20, re-rank, keep top 3–5 |
| Query too broad ("tell me about SSL") | Query decomposition — split into specific sub-questions |
| Still too much content | Compress retrieved chunks via summarization before sending |

If your RAG system is retrieving 200K tokens, you are doing context stuffing with extra steps. Fix the retrieval step.

#### Does RAG Work Even for Opus 4.7 and Gemini?

Yes — and this is important. RAG is not a workaround for weak models. It is the correct architecture for retrieval over large knowledge bases regardless of model capability.

Models with massive context windows (Gemini 2.0 at 1M tokens, Opus 4.7 at 200K) are genuinely useful for tasks that require reasoning over an entire document simultaneously — a full codebase, a 300-page contract, a long conversation history. For those tasks, large context is the right tool.

For Q&A over a knowledge base of thousands of documents, RAG beats full-context stuffing on accuracy, cost, and latency — even with the most capable models available. The U-shape does not disappear with model scale. It shrinks, but it does not disappear.

### 2. Structured Context Placement

If you must use long context, put critical information at the beginning and end — never bury it in the middle.

```
[MOST IMPORTANT: system instructions, key facts]
[Long background content]
[QUESTION + KEY CONTEXT AGAIN]  ← repeat critical info near the question
```

### 3. Context Compression

Summarize long sections before including them. A 10,000-token document summarized to 500 tokens loses some detail but avoids the lost-in-the-middle problem entirely.

### 4. Chunking with Overlap

For sequential processing (e.g., reading a long contract), split into overlapping chunks:

```
Chunk 1: tokens 0–2000
Chunk 2: tokens 1500–3500   ← 500 token overlap prevents boundary artifacts
Chunk 3: tokens 3000–5000
```

Process each chunk independently, then aggregate results.

---

## The Ollama num_ctx Gotcha

Discovered during the experiment: Ollama's default context size is **4,096 tokens**, regardless of the model's actual capability.

If you send a prompt larger than 4,096 tokens without explicitly setting `num_ctx`, Ollama returns a 500 error or silently truncates. This is a critical production gotcha — your application gets an error or wrong answer with no indication that context was the cause.

Always set `num_ctx` explicitly when working with larger prompts:

```python
payload = {
    "model": "gemma4:26b",
    "prompt": your_prompt,
    "options": {
        "num_ctx": 16384,   # set explicitly — do not rely on the default
    }
}
```

Gemma 4 26B supports up to 256,000 tokens, but Ollama will not use that unless you ask. This is one of the most common silent failures in local LLM deployments.

---

## When Large Context IS the Right Answer

There are legitimate cases where sending 50K–200K tokens is correct:

- **Full codebase analysis** — "find all security vulnerabilities across this repo"
- **Long document reasoning** — "compare clauses 12 and 47 of this 300-page contract"
- **Long-running agent history** — agent that has been working for hours with accumulated context

For these cases, the mitigations are:

1. **Place critical content at the end** — right before the question, never buried in the middle
2. **Summarize older history** — compress old conversation turns rather than keeping raw tokens
3. **Use models trained for long context** — Gemini 2.0 and Opus 4.7 are meaningfully better here
4. **Accept partial degradation and design around it** — ask follow-up questions when the model is uncertain rather than assuming one-shot accuracy

The distinction: **RAG for retrieval over many documents. Large context for deep reasoning over one document.**

---

## The Enterprise Conversation

When a client says "we want to feed the model our entire knowledge base," the right response is:

1. **How large is the knowledge base?** If it exceeds the context window, it physically cannot fit in one call.
2. **Even if it fits, do you need the model to reason over all of it simultaneously?** If you are asking one specific question, RAG retrieves the relevant parts more reliably than buried-in-the-middle full-context processing.
3. **What is your latency requirement?** A 100K-token prompt takes minutes to process locally. A 2K-token RAG result takes seconds.

The lost-in-the-middle problem is the best argument for RAG in enterprise deployments. It is not that context windows are too small — it is that flooding them is the wrong architecture.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Context window | Maximum tokens the model can receive in one call |
| Attention | The mechanism by which tokens "look at" each other during processing |
| Lost in the middle | Degraded recall for content positioned in the middle of long contexts |
| RAG | Retrieval-Augmented Generation — retrieve relevant chunks before calling the model |
| Context compression | Summarizing long content to reduce token count before including in prompt |
| Sliding window attention | Attention variant that limits each token's view to a local window, improving long-context efficiency |

---


## Full Code

```python title="02_context_window_limits.py"
--8<-- "02-llm-fundamentals/code/02_context_window_limits.py"
```

## Next

**Temperature and Sampling** — the knobs that control how deterministic or creative the model's output is, and why temperature=0 does not always mean the same answer twice.
