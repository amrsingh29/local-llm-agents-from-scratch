# Self-Hosted AI Architecture for the Enterprise

## The Gap Between a Demo and a Production System

Running `ollama run gemma4:26b` on your laptop is a demo. It works for one user, has no logging, no access control, no rate limiting, and crashes if two requests arrive simultaneously. Every enterprise objection to local AI is actually an objection to this demo configuration — not to local AI itself.

The path from demo to production is five layers:

```
┌─────────────────────────────────────┐
│           Client Layer              │  ITSM tools, web apps, APIs
├─────────────────────────────────────┤
│         Guardrails Layer            │  Input filter, output filter, injection detection
├─────────────────────────────────────┤
│      Request Management Layer       │  Rate limiter, request queue, concurrency control
├─────────────────────────────────────┤
│        Audit Logging Layer          │  Every prompt, response, latency, user ID logged
├─────────────────────────────────────┤
│         Inference Layer             │  Ollama + Gemma (or any local model)
└─────────────────────────────────────┘
```

Each layer solves a different enterprise objection. This note covers what each layer does and why it exists. The code experiments build them one at a time.

---

## The Five Enterprise Objections — and the Answers

Before architecting anything, understand the objections you will face. Every large organisation asks the same five questions when evaluating a self-hosted AI system.

### Objection 1: "How do we know what the AI is doing?"

**The requirement:** complete auditability. Every input sent to the model and every output received must be logged, attributed to a user or system, timestamped, and retained for compliance review.

**Why this matters in practice:** in a regulated industry (banking, healthcare, legal), an AI-generated response that influenced a business decision must be reproducible. "The AI said so" is not an audit trail. "At 14:23 UTC on 12 March, user ID 4421 submitted prompt X, model Y returned response Z, latency 1.4 seconds" is.

**The solution:** an audit logging layer that sits between the client and the inference engine. Every request passes through it. The model never receives a request that is not logged.

### Objection 2: "What happens when 50 people use it at once?"

**The requirement:** predictable performance under concurrent load with graceful degradation.

**Why this matters in practice:** Ollama serves one request at a time by default. When a second request arrives, it queues. Under high load without a managed queue, requests time out, users get errors, and confidence in the system collapses.

**The solution:** a request management layer with a bounded queue, configurable concurrency limits, and a rate limiter per user or team. The system rejects or queues requests explicitly rather than failing silently.

### Objection 3: "How do we stop people from misusing it?"

**The requirement:** guardrails on both input and output.

**Why this matters in practice:** without guardrails, a user can submit a prompt that extracts confidential information from the system prompt, generates harmful content, or bypasses intended behaviour via prompt injection. In an enterprise context, the blast radius of a successful prompt injection is not just one bad response — it is a compliance incident.

**The solution:** a guardrails layer that filters inputs before they reach the model (block known injection patterns, reject out-of-scope requests) and filters outputs before they reach the user (strip accidental PII, flag low-confidence or unsafe responses).

### Objection 4: "Can different teams use it without seeing each other's data?"

**The requirement:** multi-tenant isolation. User A's conversation history, injected context, and system prompts must be invisible to User B — even though both are using the same model instance.

**Why this matters in practice:** LLMs are stateless, but the applications built on top of them maintain state (conversation history, user context, RAG retrievals). Without explicit isolation, a conversation context built for one user can leak into another user's session through a shared cache or context store.

**The solution:** session management with tenant-scoped context stores. Each user or team gets an isolated context namespace. The inference layer is shared; the context layer is not.

### Objection 5: "What if the internet goes down — or we're not allowed to use it?"

**The requirement:** air-gapped or offline-capable deployment.

**Why this matters in practice:** defence, intelligence, and some financial institutions operate networks with no external connectivity. A system that requires calling home to an API provider, pulling model updates, or validating a licence key against a remote server cannot be deployed in these environments.

**The solution:** the local inference stack (Ollama + model weights) is already air-gap capable. The architecture must also avoid any external dependency in the guardrails, logging, and queue layers. All dependencies must be installable from a local package mirror.

---

## The Architecture We Will Build

Over four experiments, we build each layer from scratch:

```
Experiment 1: Concurrent inference server
    — FastAPI wrapper around Ollama with a request queue and rate limiter
    — Shows throughput degradation under load and controlled queuing

Experiment 2: Audit logger
    — SQLite-backed logger capturing every request and response
    — Structured log format suitable for compliance export

Experiment 3: Guardrails layer
    — Input filter: prompt injection detection, scope enforcement
    — Output filter: PII pattern detection, safety flag passthrough from Phase 6

Experiment 4 (bonus): Quality gate integration
    — Wire the ITSM multi-dimensional scorer from Phase 6 into the server
    — Responses below the quality gate are flagged before reaching the user
```

Each experiment adds a layer to the same server. By the end, a single request goes through: rate limiter → audit log (request) → guardrails (input) → Ollama → guardrails (output) → quality gate → audit log (response) → client.

---

## Design Decisions Made Up Front

### Why SQLite for audit logs?

SQLite is file-based, requires no server process, and is readable by standard tooling. For a single-node deployment (one machine running the inference server), it is the right choice. At scale (multiple inference nodes), replace SQLite with a centralised log store — but the schema and query patterns stay the same.

### Why FastAPI?

FastAPI generates OpenAPI documentation automatically, handles async request handling natively, and is the standard Python web framework for ML serving. The alternative is a raw `http.server` or Flask, which require more boilerplate for the same result.

### Why not use an existing model serving framework (vLLM, TGI)?

vLLM and Text Generation Inference are production-grade serving frameworks that handle batching, KV cache management, and GPU allocation at a level far beyond what Ollama does. For a single-user or small-team deployment on Apple Silicon, they are overkill and do not support Metal. Ollama is the right tool for this hardware. The point of this phase is not to rebuild vLLM — it is to understand what the production layers above the inference engine look like.

### Why not LangChain or LlamaIndex?

These frameworks abstract away the layers we are building. Understanding what a guardrails layer, a rate limiter, and an audit log look like from first principles means you can evaluate, debug, and customise any framework that provides these features. That is worth the extra code.

---

## Throughput Expectations Under Load (M4, 24 GB)

From Phase 1 benchmarks: `gemma4:26b` sustains ~25 tokens/second on a single request. Under concurrent load, total throughput does not scale linearly because the model processes one request at a time (Ollama default configuration).

Expected behaviour with the queue-based server:

| Concurrent users | Behaviour |
|-----------------|-----------|
| 1 | ~25 tok/s, ~1.4s for a 35-token response |
| 2 | Serialised — second request waits for first to complete. P50 latency doubles. |
| 5 | Queue depth grows. P95 latency is approximately 5× single-request latency. |
| 10+ | Without a queue limit, memory pressure grows as KV caches stack. With a queue limit, excess requests receive a 429 response immediately. |

This is the honest throughput story for a single-node local inference server. It is not comparable to a cloud API that runs hundreds of instances in parallel — nor should it be. The value proposition is privacy, cost, and control, not raw throughput.

---

## Air-Gapped Deployment Checklist

For readers who need to deploy in a fully disconnected environment:

- [ ] Ollama binary installed from local copy (no `brew install`)
- [ ] Model weights pulled and cached before network disconnect (`~/.ollama/models/`)
- [ ] Python dependencies installed from local mirror (pip with `--no-index --find-links`)
- [ ] FastAPI, SQLite, and all guardrails dependencies are standard library or installable offline
- [ ] No telemetry calls — Ollama sends anonymous usage data by default; disable with `OLLAMA_NO_ANALYTICS=true`
- [ ] Audit log storage is local (SQLite file) with no remote export configured
- [ ] The system prompt and any RAG knowledge base are stored locally

Once these conditions are met, the entire stack — from HTTP request to model response — runs with zero external network calls.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Guardrails | Input/output filters that enforce safety, scope, and content policy for a model deployment |
| Rate limiter | A mechanism that caps the number of requests a user or system can make per unit time |
| Request queue | A buffer that holds incoming requests when the inference engine is busy, preventing timeouts |
| Audit log | An immutable record of every inference request and response, attributed to a user and timestamped |
| Multi-tenancy | Running one model instance that serves multiple isolated users or teams simultaneously |
| Air-gapped | A deployment with no external network connectivity — all dependencies are local |
| Tenant isolation | Ensuring that one tenant's context, history, and data are invisible to other tenants |

---

## Next

`code/01_concurrent_inference_server.py` — builds the request management layer: a FastAPI server wrapping Ollama with a semaphore-based concurrency limiter, a bounded request queue, and per-user rate limiting. Run it and send concurrent requests to see exactly how load affects latency.
