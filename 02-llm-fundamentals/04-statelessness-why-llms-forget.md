# Statelessness — Why LLMs Forget Everything

## The Wrong Mental Model

"I told the AI my name last time. Why doesn't it remember?"

Every developer building their first LLM application hits this wall. They assume the model is like a person — accumulating knowledge about you over time, building a relationship, remembering what was said.

It is not. Every API call is the model waking up for the first time with complete amnesia. There is no persistence, no memory, no continuity between calls. The model does not know you exist until you tell it — in every single call.

---

## What Statelessness Means

A **stateless** system processes each request independently, with no knowledge of previous requests. HTTP is stateless. REST APIs are stateless. And LLMs are stateless.

When you call Ollama's `/api/chat`:

```
Call 1: { messages: [{ role: "user", content: "My name is Amrendra" }] }
         → Model processes, responds, forgets everything

Call 2: { messages: [{ role: "user", content: "What is my name?" }] }
         → Model starts fresh. Has no idea. Says "I don't know your name."
```

The model that answered Call 1 and the model that answered Call 2 are functionally identical — same weights, same starting state. Nothing from Call 1 carries over.

This is not a bug. It is a deliberate architectural property. Statelessness makes LLMs:
- **Scalable** — any server can handle any request, no session affinity needed
- **Predictable** — same input always produces same output (at temp=0)
- **Safe** — no information leaks between users in a multi-tenant system

---

## The Experiment: Proving Statelessness

Script: `04_stateless_proof.py`

**Setup:** Three separate API calls. Each is completely independent.

```
Call 1 prompt: "My name is Amrendra. Please remember that."
Call 2 prompt: "What is my name?"           ← new call, no history
Call 3 prompt: "What did I just ask you to remember?"  ← new call, no history
```

### Results

> Run against Gemma 4 26B on Apple M4 24 GB — 2026-04-20

**Call 1 response:**
> Understood, Amrendra. I will remember your name. How can I help you today?

**Call 2 response:**
> I do not know your name. As a large language model, I don't have access to your personal identity or private information unless you have shared it with me in our current conversation.

**Call 3 response:**
> You haven't asked me to remember anything yet in this conversation. This is the start of our chat! If you have something specific you'd like me to keep in mind for our future interactions, feel free...

Finding: the model correctly acknowledged the name in Call 1 — "I will remember your name." Then immediately had zero knowledge of it in Call 2 and 3. "I will remember" is a meaningless statement from a stateless system. The model cannot fulfil that promise — it has no mechanism to do so. It does not even know Call 1 happened.

---

## How Chat Applications Fake Memory

If LLMs are stateless, how does ChatGPT appear to remember what you said five messages ago?

**It doesn't remember. It re-reads.**

Every time you send a message in a chat interface, the application sends the **entire conversation history** as part of the current API call:

```
Turn 1:
  API call: [{ user: "My name is Amrendra" }]
  Response: "Nice to meet you, Amrendra!"

Turn 2:
  API call: [
    { user: "My name is Amrendra" },        ← sent again
    { assistant: "Nice to meet you..." },    ← sent again
    { user: "What is my name?" },            ← new message
  ]
  Response: "Your name is Amrendra."

Turn 3:
  API call: [
    { user: "My name is Amrendra" },        ← sent again
    { assistant: "Nice to meet you..." },    ← sent again
    { user: "What is my name?" },            ← sent again
    { assistant: "Your name is Amrendra." },← sent again
    { user: "What do I do for work?" },     ← new message
  ]
  Response: "You haven't told me what you do for work."
```

The model is not remembering — it is reading the transcript fresh on every call. "Memory" in a chat application is just history management in the application layer.

### Results from the Faked Memory Experiment

In `experiment_faked_memory()`, we told Gemma:
1. "My name is Amrendra and I work as a Solutions Engineer."
2. "I am currently learning about AI agents and LLMs."
3. "What do you know about me so far?"
4. "Based on what I told you, what kind of AI projects might be most useful for my role?"

By turn 4, the API call contained 7 messages (4 user + 3 assistant). Gemma correctly answered based on the earlier context — not because it remembered, but because it was reading the full transcript every time.

---

## The Context Growth Problem

This architecture has a fatal flaw: **the prompt grows with every turn.**

```
Turn 1:  ~50 tokens sent
Turn 5:  ~500 tokens sent
Turn 20: ~2,000 tokens sent
Turn 100: ~10,000 tokens sent
```

Eventually you hit the context window limit. For Gemma 4 26B with a 256K context window, that sounds generous — but in a real conversation with long answers:

### Results from the Context Growth Experiment

| Turn | Messages in History | Approx Tokens |
|------|--------------------|--------------:|
| 1 | 2 | 187 |
| 2 | 4 | 364 |
| 3 | 6 | 552 |
| 4 | 8 | 742 |
| 5 | 10 | 924 |

Growth rate: ~185 tokens per turn (user message + assistant response combined).
At this rate, a 256K context window fills in approximately **~1,385 conversation turns**.

That sounds comfortable — but these were short answers. In a real technical conversation with detailed responses, each turn easily costs 500–1,000 tokens. At 750 tokens/turn, 256K context fills in ~340 turns — roughly a 3-hour session with one message per minute.

For a customer support bot handling hour-long sessions, that math works. For a long-running AI agent operating for days, it does not.

---

## Production Memory Strategies

Understanding statelessness leads directly to the strategies real systems use:

### 1. Full History (Naive — works for short sessions)

Send everything. Simple, accurate, but hits context limits eventually.

```python
history.append({"role": "user", "content": new_message})
response = call_model(history)
history.append({"role": "assistant", "content": response})
```

Works for: chat sessions under ~100 turns, customer support, short-lived agents.

### 2. Sliding Window (Fixed context budget)

Keep only the last N turns. Old context is discarded.

```python
MAX_TURNS = 20
recent_history = history[-MAX_TURNS:]
response = call_model(recent_history)
```

Risk: the model loses early context. If the user's name was mentioned in turn 1 and the window is 20 turns, by turn 21 the model forgets the name.

### 3. Summarization (Compress old history)

Periodically summarize old turns into a compact paragraph, replace them with the summary.

```
[Turn 1-20 raw history]
         ↓  summarize
"User is Amrendra, a Solutions Engineer learning AI. Discussed neural networks,
transformers, and agent architecture. User prefers concise technical explanations."

[Summary] + [Turn 21-40 raw history]
```

The model retains the gist of earlier turns without paying the full token cost. This is how Claude's memory features work under the hood.

### 4. External Memory (RAG-based)

Store facts from the conversation in a vector database. Retrieve relevant facts per turn.

```
Turn 1: User says "I'm allergic to peanuts"
         → store: { fact: "user allergic to peanuts", embedding: [...] }

Turn 50: User asks "What snacks would you recommend?"
         → retrieve: "user allergic to peanuts" (high similarity)
         → inject into prompt: "Note: user is allergic to peanuts"
```

This is how enterprise AI assistants handle long-term user profiles. The "memory" is a database, not the model itself.

### 5. Structured State (Agent systems)

For AI agents that run for hours or days, maintain explicit state in a structured format (JSON) that gets updated and injected into every prompt.

```json
{
  "user": { "name": "Amrendra", "role": "Solutions Engineer" },
  "task": { "current": "Phase 2 experiments", "completed": ["Phase 1"] },
  "decisions": ["Use Ollama for local inference", "Python for all code"]
}
```

The agent reads its own state at the start of every call. State is the memory.

---

## The Enterprise Implication

Every enterprise AI deployment must answer: **where does memory live?**

| Memory type | Where stored | Lifetime | Cost |
|------------|-------------|---------|------|
| In-context history | Prompt (tokens) | One session | Token cost per call |
| Summarized history | Prompt (compressed) | One session | Cheaper per call |
| Vector database | External DB | Persistent | Query cost |
| Structured state | Application layer | Persistent | Negligible |
| Model weights | None — stateless | Zero | Not applicable |

The last row is the key insight: **you cannot store memory in the model.** The model has no persistent storage. Everything the model "knows" about your user must be supplied to it anew on every call — either directly in the prompt or retrieved from an external system.

This is why "just fine-tune the model on our data" is usually the wrong answer to "how do we give the AI memory?" Fine-tuning bakes knowledge into the weights — but that knowledge is static, expensive to update, and shared across all users. User-specific memory must live outside the model.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Stateless | Each request is processed independently with no knowledge of prior requests |
| Conversation history | The list of all previous messages sent to the model in one session |
| Context window | The maximum tokens the model can receive — sets the ceiling for history length |
| Sliding window | Keeping only the last N turns to stay within context limits |
| Summarization | Compressing old turns into a short paragraph to save tokens |
| External memory | Storing facts in a database and retrieving them per turn via RAG |
| Structured state | An explicit JSON object tracking agent state, injected into every prompt |

---


## Full Code

```python title="04_stateless_proof.py"
--8<-- "02-llm-fundamentals/code/04_stateless_proof.py"
```

## Next

**Prompt Engineering as Programming** — system prompts, few-shot examples, and chain-of-thought: how you shape model behaviour through careful instruction design.
