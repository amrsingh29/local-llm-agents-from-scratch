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
**Status: Upcoming**

Gemma as a local worker agent. Claude as a cloud orchestrator. A routing layer that decides which model handles each sub-task.

---

### Phase 6 — Evaluation and Benchmarking
**Status: Upcoming**

Build a domain-specific benchmark harness. Use Gemma as the judge — free evaluations, no external service required.

---

### Phase 7 — Production and Enterprise Patterns
**Status: Upcoming**

Self-hosted inference with audit logging, rate limiting, guardrails, and multi-tenant isolation.

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
├── 05-orchestration-multi-agent/   # Upcoming
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
