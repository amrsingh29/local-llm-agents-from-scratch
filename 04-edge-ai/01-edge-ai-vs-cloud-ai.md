
# Edge AI vs Cloud AI — The Decision Framework

## The Core Question

When you build a system that needs an LLM, you have two options:

```
Option A — Cloud API:
  Your app → HTTP → OpenAI / Anthropic / Google → Response

Option B — Edge (Local) Inference:
  Your app → localhost → Ollama → Gemma → Response
```

Most engineers default to the cloud because it is simpler to start. That is often the right call. But treating it as the *only* call means leaving significant value on the table — or shipping systems that cannot legally or practically use a cloud API.

This note builds the decision framework from first principles.

---

## What "Edge" Actually Means

"Edge" in AI means inference happens on the device — not on a remote server. The model lives on the same machine (or local network) as the application.

The edge is not only phones and embedded devices. A developer's M4 MacBook running Ollama is an edge inference setup. So is a hospital's on-premise server running a quantized model for medical record processing. The unifying characteristic: **compute is local, data does not leave the device**.

---

## The Five Axes of the Decision

### 1. Latency

**Cloud API:**
- Round-trip over HTTPS: typically 300ms–2000ms depending on model size, load, and geography
- Time-to-first-token for streaming: usually 500ms–1500ms
- Not deterministic — shared infrastructure, traffic spikes, rate limits

**Local:**
- Round-trip over localhost: sub-millisecond network overhead
- Time-to-first-token: depends on model and hardware — on M4 24 GB, Gemma 4 26B delivers ~25 tok/sec sustained
- Deterministic — you own the hardware

**When latency decides the choice:**
- Real-time applications (voice, gaming, robotics): local wins unconditionally
- Batch processing with no user-facing latency: cloud latency is irrelevant
- Interactive user-facing apps: cloud latency is acceptable unless you need sub-300ms responses

### 2. Cost

**Cloud API pricing model:** per token, per request.

Example rates (approximate, vary by provider and model):
- GPT-4o: ~$2.50 / 1M input tokens, ~$10.00 / 1M output tokens
- Claude Sonnet 4: ~$3.00 / 1M input tokens, ~$15.00 / 1M output tokens
- Gemini 2.0 Flash: ~$0.10 / 1M input tokens

At scale, per-token pricing becomes the dominant cost. A system generating 10M output tokens/day on GPT-4o costs ~$100K/month just in API fees.

**Local inference pricing model:** hardware + electricity.

A Mac M4 24 GB costs roughly $1,600. At $0.12/kWh and ~30W active draw during inference, running Gemma 4 26B full-time costs ~$26/month in electricity. The hardware amortizes over 3-5 years.

**The crossover point:** if your system generates enough tokens per month, local is cheaper. The exact crossover depends on which cloud model you're comparing against. For high-volume workloads comparing against frontier models (GPT-4, Claude Sonnet), local inference typically wins within 6–12 months of hardware cost.

**When cost decides the choice:**
- High-volume, repetitive tasks (document processing, code review pipelines): local wins
- Low-volume, irregular tasks: cloud wins (no idle hardware cost)
- Development and experimentation: local wins (no per-token cost during iteration)

### 3. Privacy and Data Sovereignty

This is often the deciding factor in enterprise settings — not cost or latency.

**Cloud API:** data leaves your infrastructure. The provider's terms govern what happens to it. Even with enterprise contracts and data processing agreements, the data is physically on someone else's hardware.

**Regulatory environments where local is mandatory:**
- Healthcare (HIPAA in US, GDPR in EU): patient data cannot leave compliant infrastructure
- Finance (SOX, PCI-DSS): transaction data subject to sovereignty requirements
- Legal: attorney-client privilege considerations with third-party AI processing
- Government and defense: classified or sensitive information cannot go to external APIs

**When privacy decides the choice:**
- Any regulated industry: local is often not optional, it is the only legal path
- Internal tools processing employee or customer PII: consult legal before using cloud APIs
- Enterprise code review: source code is often contractually protected from third-party exposure

### 4. Reliability and Offline Operation

**Cloud API dependencies:**
- Internet connectivity required
- Provider availability (OpenAI has experienced multi-hour outages)
- Rate limits that can block your application under load
- Breaking changes in model behavior when provider updates the model

**Local inference:**
- Works offline (critical for edge devices in the field)
- No rate limits (your hardware is the limit)
- Model behavior is frozen to the version you pulled
- You control when to upgrade the model

**When reliability decides the choice:**
- Field applications (devices that operate without reliable internet)
- Mission-critical pipelines where a provider outage would halt operations
- Compliance requirements for availability SLAs you cannot enforce on a third party

### 5. Capability

Here is where cloud often wins.

**Frontier models (GPT-4o, Claude Sonnet, Gemini 2.0 Pro) vs local models (Gemma 4 26B):**

| Capability | Frontier Cloud | Gemma 4 26B Local |
|---|---|---|
| Complex reasoning | Industry best | Strong, not best |
| Code generation | Industry best | Competitive for most tasks |
| Long context (>100K tokens) | Native | Requires careful management |
| Vision | Native (multimodal) | Native (Gemma 4 is multimodal) |
| Structured output | Reliable | Good with prompting |
| Multilingual | Broad | Strong, narrower than frontier |

Gemma 4 26B is not a toy — it is competitive with models that were frontier-tier two years ago. For most tasks in a well-defined domain, it is sufficient. But for the hardest reasoning tasks, frontier models have a real capability advantage.

**When capability decides the choice:**
- Tasks requiring frontier-level reasoning: cloud wins
- Well-defined, domain-specific tasks: local is often sufficient
- Fine-tuning for a specific domain: local is the only practical option (fine-tuning frontier models is extremely expensive)

---

## The Hybrid Architecture

Most production AI systems are not purely local or purely cloud. They are hybrid.

```
Incoming request
       ↓
  [Router / Classifier]
  ↙                    ↘
Local model           Cloud API
(fast, cheap,         (frontier capability,
 private)              external)
```

The router classifies each request and sends it to the appropriate model:
- Sensitive data? → local
- Simple/repetitive task? → local
- Needs frontier reasoning? → cloud
- Cost limit exceeded? → local

This is the architecture that gives you the best of both worlds — capability where you need it, cost and privacy protection where you don't.

**Phase 5 of this series** builds this router using Gemma (local worker) and Claude (cloud orchestrator).

---

## The Decision Matrix

| Factor | Choose Local | Choose Cloud |
|--------|-------------|--------------|
| Latency | <300ms required | >300ms acceptable |
| Cost | High volume (>1M tokens/day) | Low volume |
| Privacy | Regulated data / PII | Public or non-sensitive data |
| Reliability | Offline operation, SLA control | Cloud SLA sufficient |
| Capability | Domain-specific, well-defined | Frontier reasoning required |
| Iteration speed | Rapid local dev, no API costs | Quick start, no hardware |

No single factor determines the answer. Score each axis for your specific use case. If 3+ axes favor local, start with local and add cloud API for the cases that need it.

---

## The Practical Starting Point

For a new project:

**Start local if:**
- You are in a regulated industry
- You need to iterate quickly without per-token costs
- Your task is well-defined and can be tested against a capable but not frontier model

**Start cloud if:**
- You do not know the task scope yet and need maximum capability to explore it
- Your volume is low enough that per-token costs are negligible
- You need capabilities not available in open models (very long context, specialized APIs)

**Plan for hybrid from day one:**
- Abstract your LLM client so swapping providers requires changing one class, not the whole codebase
- Log every call with model, token count, and latency so you have data to make routing decisions later
- Build your evaluation suite before committing to a model choice — the model that scores best on your eval is the model you should use

---

## Enterprise Implication

The largest enterprise AI deployments are not monolithic cloud setups. They are hybrid architectures with multiple model tiers:

- **Tier 1 — Local edge models:** fast, cheap, private, sufficient for 80% of requests
- **Tier 2 — Self-hosted mid-tier models:** on-premise servers running open models for sensitive workloads
- **Tier 3 — Cloud frontier models:** reserved for the hardest tasks that justify the cost and data transfer

This tiered approach emerged because enterprises learned the hard way that:
1. Cloud-only breaks when you need offline operation or hit rate limits
2. Local-only hits capability ceilings on complex tasks
3. The right answer is routing, not selection

The skills to build this architecture — local inference, benchmarking, routing logic — are what this phase teaches.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Edge inference | Running model inference on local hardware, not a remote API |
| Data sovereignty | The legal principle that data is subject to the laws of the jurisdiction where it is stored/processed |
| Hybrid architecture | A system that routes requests to local or cloud models based on request characteristics |
| Token cost crossover | The volume at which local hardware amortization becomes cheaper than per-token cloud pricing |
| Model routing | Automatically selecting the appropriate model for a given request based on cost, capability, or privacy requirements |

---

## Next

**Gemma E2B vs 26B Benchmark** — pulling both models and running the same task suite against each. Real numbers: latency, throughput, accuracy, memory pressure. The benchmark produces the data you need to make the local-vs-local routing decision (when to use the small model vs the large one).
