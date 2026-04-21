# Local LLM Agents From Scratch

A hands-on learning series for running Google Gemma 4 locally on Apple Silicon and building LLM agents from first principles — no cloud APIs required.

Every phase has two outputs: a publishable tutorial note explaining the concept, and a runnable Python experiment you can execute against your own local model.

---

## Hardware

| Spec | Value |
|------|-------|
| Chip | Apple M4 |
| RAM | 24 GB Unified Memory |
| Model | Gemma 4 26B MoE + Gemma 4 E2B |
| Inference | Ollama with Metal GPU acceleration |

Benchmarks in this repo are from this hardware. Your numbers will vary — the concepts and code apply to any Apple Silicon Mac with 16 GB+ RAM.

---

## What You Will Build

By the end of all seven phases, you will have built:

- A bare-metal ReAct agent calling a local LLM — no LangChain, no frameworks
- A benchmark harness that compares model quality and throughput across tasks
- A model router that classifies incoming prompts and dispatches to the right model automatically
- A multi-agent system where a local Gemma worker handles sub-tasks routed by a cloud orchestrator
- A domain-specific evaluation harness using LLM-as-judge (free evals, no external service)
- A self-hosted inference server with audit logging, rate limiting, and guardrails

---

## Phases

### Phase 1 — Installation and Infrastructure
**Status: Complete**

Install Ollama, pull Gemma 4 26B, verify Metal GPU acceleration, establish throughput baseline.

Key findings on M4 24 GB:
- Sustained throughput: ~25 tok/s
- Cold start: ~4 tok/s (first request after model load)
- No thermal throttling observed in extended runs

| File | What it covers |
|------|---------------|
| `notes/01-how-llms-are-packaged.md` | GGUF format, safetensors, Ollama as inference server |
| `notes/02-quantization-from-first-principles.md` | FP32 to INT4, K-quants, quality vs size tradeoffs |
| `notes/03-ollama-architecture.md` | Full stack: llama.cpp, Metal, KV cache, concurrency model |
| `notes/04-gemma-model-variants.md` | E2B vs 26B, MoE architecture, use cases |
| `code/01_first_inference.py` | Clean inference wrapper with token stats |
| `code/02_benchmark_throughput.py` | Short/long throughput, temperature variance, stability |

---

### Phase 2 — LLM Fundamentals
**Status: Complete**

Five experiments that build intuition for how LLMs actually work — before writing a single line of agent code.

Key findings:
- Numbers tokenize at ~0.7 chars/token — the most expensive content type
- Lost-in-the-middle: model refused to answer when signal-to-noise ratio was too low
- Throughput drops 5.7x when context grows 14.6x
- Gemma 4 resisted prompt injection ("ignore your previous instructions")

| File | What it covers |
|------|---------------|
| `notes/01-tokens-from-first-principles.md` | Tokenization, BPE, chars/token by content type |
| `notes/02-context-window-limits-and-tricks.md` | Lost-in-the-middle, RAG, throughput degradation |
| `notes/03-temperature-and-sampling.md` | Temperature, top-p, top-k, thinking mode |
| `notes/04-statelessness-why-llms-forget.md` | Statelessness proof, faked memory, production strategies |
| `notes/05-prompt-engineering-as-programming.md` | System prompts, format control, prompt injection, guardrails |
| `code/01_tokenization_experiments.py` | Real token counts across content types |
| `code/02_context_window_limits.py` | Lost-in-the-middle demonstration |
| `code/03_temperature_experiments.py` | Output variance across temperature settings |
| `code/04_stateless_proof.py` | Proving statelessness with and without conversation history |
| `code/05_system_prompts.py` | Behavioral shift from system prompt changes |

---

### Phase 3 — Agent Architecture
**Status: Complete**

Build a ReAct agent from scratch. No frameworks. Every line of the agent loop written by hand so you know exactly what is happening.

Key findings:
- Stop sequence `"\nObservation:"` is mandatory — without it the model hallucinated tool results
- After stop sequence fix: model correctly reads real errors and gives honest failure reports
- Schema quality governs agent quality — a bad description breaks tool selection even with perfect code
- Pipeline and agent architectures produce identical results on known scenarios; the difference is maintainability as requirements grow

| File | What it covers |
|------|---------------|
| `notes/01-what-is-an-agent-vs-pipeline.md` | Chatbot vs pipeline vs agent, with stock price example |
| `notes/02-the-agent-loop.md` | Perceive → Think → Act → Observe, termination problem, failure modes |
| `notes/03-react-pattern-from-first-principles.md` | ReAct format, stop sequences, full worked example |
| `notes/04-tool-calling-internals.md` | Four failure modes, hallucination discovery, stop sequence fix |
| `notes/05-tool-schema-design.md` | Schema design rules, three common mistakes, native tool calling |
| `code/01_bare_metal_react_agent.py` | Full ReAct agent: calculator, date, file_read, word_count tools |
| `code/02_agent_error_handling.py` | Four error scenarios with deliberately broken tools |
| `code/03_pipeline_vs_agent.py` | Same task through both architectures across three failure scenarios |

---

### Phase 4 — Edge AI and On-Device Intelligence
**Status: Complete**

When does running a model locally beat calling a cloud API? Benchmark two local models, build a router that dispatches to the right one automatically.

Key findings (M4 24 GB, Gemma 4 E2B vs 26B):

| | gemma4:e2b | gemma4:26b |
|-|-----------|-----------|
| Avg throughput | 51.9 tok/s | 20.6 tok/s |
| Speedup | 2.5x faster | baseline |
| Factual quality | 5/5 | 5/5 |
| Reasoning quality | 4/5 | 4.5/5 |
| Code (format-following) | Verbose, ignores format | Concise, follows instructions |
| Memory loaded | ~7 GB | ~20 GB |

Router result: 4/4 correct classifications on first run. Classifier overhead ~400ms warm.

| File | What it covers |
|------|---------------|
| `notes/01-edge-ai-vs-cloud-ai.md` | Five-axis decision framework: latency, cost, privacy, reliability, capability |
| `notes/02-gemma-e2b-vs-26b-benchmark.md` | Full benchmark with per-task prompts, responses, and analysis |
| `notes/03-model-routing.md` | Three routing strategies, classifier prompt, experiment results |
| `code/01_model_benchmark.py` | Automated benchmark harness with LLM-as-judge scoring |
| `code/02_model_router.py` | Classifier router dispatching to E2B or 26B based on task type |

---

### Phase 5 — Orchestration and Multi-Agent Systems
**Status: Complete**

Fully local multi-agent system — Gemma 26B orchestrates and synthesises, E2B/26B workers execute sub-tasks routed by task type.

Key findings:
- 4-part transformer explainer decomposed into 4 correctly typed sub-tasks on first run
- Routing was automatic: orchestrator assigned `type`, routing table selected the model
- E2B handled summarise tasks at 51 tok/s; 26B handled reasoning and code
- 1,949 total worker tokens — zero API cost, everything local

| File | What it covers |
|------|---------------|
| `notes/01-multi-agent-architecture.md` | Four single-agent failure modes, orchestrator/worker pattern, task decomposition, dependency graph, experiment results |
| `notes/02-gemma-as-worker.md` | Worker contract, what Gemma handles well, output format spec, context-passing patterns, per-worker experiment results |
| `code/01_orchestrated_agent.py` | Full local multi-agent system: decompose → route → execute → synthesise |

---

### Phase 6 — Evaluation and Benchmarking
**Status: Complete**

Domain-specific benchmark harness using Gemma as the judge — free evaluations, fully local.

Key findings (gemma4:26b, 10-question domain benchmark):
- Overall: 4.5/5 — quality gate (4.0/5) passed
- Evaluation category scored 5.0/5 — strong meta-knowledge
- Common failure: token limit truncation, not factual errors — answers were correct but cut off
- Judge calibrated correctly: 5/3/1 on good/partial/wrong answers
- 360 seconds for 10 questions + 10 judge calls — zero API cost

| File | What it covers |
|------|---------------|
| `notes/01-why-llm-evaluation-is-hard.md` | Non-determinism, benchmark gaming, verbosity bias, three evaluation approaches |
| `notes/02-llm-as-judge.md` | Judge prompt design, calibration, known biases, experiment results |
| `notes/03-domain-specific-benchmark.md` | Benchmark design principles, 10-question domain test, full results |
| `code/01_llm_judge.py` | Standalone judge: scores any response 1–5 with reasoning |
| `code/02_benchmark_harness.py` | Full benchmark runner with category report and quality gate |

---

### Phase 7 — Production and Enterprise Patterns
**Status: Complete**

Self-hosted inference server with concurrency control, audit logging, and guardrails — the production layer above the model.

Key findings (M4 24 GB, gemma4:26b):
- Audit logger correctly records two-phase request/response with latency data
- Guardrail injection detection: 2/2 injection attempts blocked; scope filter caught the third via defence-in-depth
- Critical bug found: substring keyword matching produces false negatives — `"api" in "capital"` is True; word-boundary regex required for production scope filters
- All components run fully offline (no external network calls)

| File | What it covers |
|------|---------------|
| `notes/01-self-hosted-ai-architecture.md` | 5-layer production architecture, enterprise objections, air-gap checklist |
| `notes/02-concurrency-and-throughput.md` | Token bucket rate limiter, semaphore queue, thread pool offload, load behaviour |
| `notes/03-audit-logging-compliance.md` | Two-phase write, per-user reporting, compliance export, real latency data |
| `notes/04-guardrails-for-local-models.md` | 6 test cases with real results, substring matching bug, defence-in-depth finding |
| `notes/05-air-gapped-deployment.md` | Pre-staging checklist, telemetry disable, cross-model eval alternatives |
| `code/01_concurrent_inference_server.py` | FastAPI + semaphore + bounded queue + token bucket rate limiter |
| `code/02_audit_logger.py` | SQLite audit logger with compliance export |
| `code/03_guardrails.py` | Input/output filter: injection detection, scope enforcement, PII detection |

---

## Getting Started

```bash
# Install Ollama
brew install ollama

# Start with Flash Attention enabled
OLLAMA_FLASH_ATTENTION="1" OLLAMA_KV_CACHE_TYPE="q8_0" ollama serve

# Pull models
ollama pull gemma4:26b   # 17 GB — main model
ollama pull gemma4:e2b   # 7.2 GB — fast model for routing

# Run any experiment
python 01-installation/code/01_first_inference.py
python 03-agent-architecture/code/01_bare_metal_react_agent.py
python 04-edge-ai/code/02_model_router.py
python 05-orchestration-multi-agent/code/01_orchestrated_agent.py
```

**Requirements:** Python 3.11+, `requests` library, Ollama 0.20+

```bash
pip install requests
```

---

## Structure

```
├── 01-installation/
│   ├── notes/          # Concept explanations (publishable tutorial format)
│   └── code/           # Runnable Python experiments
├── 02-llm-fundamentals/
├── 03-agent-architecture/
├── 04-edge-ai/
├── 05-orchestration-multi-agent/
├── 06-evaluation/                  # Upcoming
├── 07-production-enterprise/       # Upcoming
├── CURRICULUM.md       # Full 7-phase learning plan with details
└── PROGRESS.md         # Session log — what was built and when
```

---

## Why Local Models

- **Privacy:** data never leaves your machine — required for regulated industries
- **Cost:** no per-token charges during development and high-volume workloads
- **Latency:** localhost inference with no round-trip to a remote API
- **Reliability:** no rate limits, no provider outages, no breaking model updates
- **Learning:** when you own the stack end to end, you understand it end to end
