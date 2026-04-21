# Progress Log — Gemma Local AI

> Updated after each session. Read this at the start of every session to know exactly where to continue.

---

## Session 1 — 2026-04-20

**What was done:**
- Researched Gemma 4 models — confirmed Gemma 4 26B MoE is the right choice for 24 GB M4 Mac
- Mapped all learning concepts across 7 phases
- Created full directory structure at `/Users/amrendra/Om/MyWorkspace/MyProjects/gemma-local-ai/`
- Created `CURRICULUM.md` with detailed phase-by-phase plan

**Files created:**
- `CURRICULUM.md` — full curriculum
- `PROGRESS.md` — this file

**Status:** Phase 1 not yet started. Ollama not yet installed.

**Next:** Start Phase 1 — Installation.
1. Install Ollama via `brew install ollama`
2. Pull `gemma4:26b` (verify exact tag at ollama.com/library)
3. Run first inference and verify Metal GPU is being used
4. Write `notes/01-how-llms-are-packaged.md`
5. Write `code/01_first_inference.py`

---

## Session 2 — 2026-04-20

**What was done:**
- Installed Ollama via Homebrew
- Configured Flash Attention: `OLLAMA_FLASH_ATTENTION="1" OLLAMA_KV_CACHE_TYPE="q8_0" ollama serve`
- Pulled `gemma4:26b` (17 GB, confirmed installed)
- Ran first inference — model responding correctly
- Established hardware baseline: **~25 tokens/sec sustained** on M4 24 GB

**Notes written:**
- `01-installation/notes/01-how-llms-are-packaged.md` — GGUF, safetensors, Ollama as inference server, Apple UMA
- `01-installation/notes/02-quantization-from-first-principles.md` — FP32 to INT4, K-quants, quality vs size tradeoffs
- `01-installation/notes/03-ollama-architecture.md` — full stack, llama.cpp, Metal, KV cache, concurrency model
- `01-installation/notes/04-gemma-model-variants.md` — E2B vs 26B, MoE architecture, use cases, decision framework

**Code written:**
- `01-installation/code/01_first_inference.py` — clean inference wrapper with token stats
- `01-installation/code/02_benchmark_throughput.py` — 3 experiments: short/long throughput, temperature variance, stability

**Benchmark results (M4, 24 GB, gemma4:26b):**
- Cold start throughput: ~4 tok/sec (first request after load)
- Sustained throughput: ~25 tok/sec
- Throughput std dev: 0.51 tok/sec (very stable)
- No thermal throttling observed

**Side topics covered:**
- Gemma 4 E2B vs 26B architecture deep dive (dense vs MoE)
- Production inference architecture (vLLM, continuous batching, horizontal scaling)
- Tutorial publishing strategy — Markdown, GitHub repo, write notes as you go, editorial pass at end

**Status:** Phase 1 COMPLETE. Phase 2 COMPLETE.

---

## Session 3 — 2026-04-20

**What was done — Phase 2: LLM Fundamentals**

**Notes written:**
- `02-llm-fundamentals/notes/01-tokens-from-first-principles.md` — tokenization, BPE, chars/token by content type, real experiment results
- `02-llm-fundamentals/notes/02-context-window-limits-and-tricks.md` — lost-in-the-middle, RAG deep dive, num_ctx gotcha, throughput degradation
- `02-llm-fundamentals/notes/03-temperature-and-sampling.md` — simple + technical explanation, top-p/top-k, thinking mode discovery
- `02-llm-fundamentals/notes/04-statelessness-why-llms-forget.md` — statelessness proof, faked memory, context growth, production strategies
- `02-llm-fundamentals/notes/05-prompt-engineering-as-programming.md` — system prompts, format control, prompt injection, guardrails

**Code written:**
- `02-llm-fundamentals/code/01_tokenization_experiments.py`
- `02-llm-fundamentals/code/02_context_window_limits.py`
- `02-llm-fundamentals/code/03_temperature_experiments.py`
- `02-llm-fundamentals/code/04_stateless_proof.py`
- `02-llm-fundamentals/code/05_system_prompts.py`

**Key discoveries:**
- Gemma 4 uses `/api/chat` not `/api/generate` for text responses
- Gemma 4 is a thinking model — set `think: false` for direct responses
- Ollama default `num_ctx` is 4,096 — must set explicitly for larger prompts
- Numbers tokenize at 0.7 chars/token — most expensive content type
- Lost-in-the-middle: model refused to answer when signal-to-noise too low
- Throughput drops 5.7x when context grows 14.6x
- Prompt injection ("ignore your previous instructions") — Gemma 4 resisted
- Hallucination risk when model is constrained to a domain it has no data for

**Status:** Phase 2 COMPLETE.

**Next:** Start Phase 3 — Agent Architecture.
1. Write `notes/01-what-is-an-agent-vs-pipeline.md`
2. Write `notes/02-the-agent-loop.md`
3. Write `notes/03-react-pattern-from-first-principles.md`
4. Build bare-metal ReAct agent: `code/01_bare_metal_react_agent.py`
5. Wire up real tools: calculator, file reader

---

## Session 4 — 2026-04-20

**What was done — Phase 3: Agent Architecture**

**Notes written:**
- `03-agent-architecture/notes/01-what-is-an-agent-vs-pipeline.md` — chatbot vs pipeline vs agent, stock price example showing both approaches
- `03-agent-architecture/notes/02-the-agent-loop.md` — Perceive→Think→Act→Observe loop, Python skeleton, termination problem, failure modes, audit trail
- `03-agent-architecture/notes/03-react-pattern-from-first-principles.md` — ReAct format, full example, code walkthrough, stop sequence rationale, all 4 task results
- `03-agent-architecture/notes/04-tool-calling-internals.md` — four failure modes, exception handling, hallucination discovery, before/after stop sequence comparison, native tool calling
- `03-agent-architecture/notes/05-tool-schema-design.md` — four schema elements, three design mistakes, native tool calling schema format, enterprise implications

**Code written:**
- `03-agent-architecture/code/01_bare_metal_react_agent.py` — full ReAct agent with calculator, date, file_read, word_count tools
- `03-agent-architecture/code/02_agent_error_handling.py` — four error scenarios with deliberately broken tools

**Key discoveries:**
- Stop sequence `"\nObservation:"` is mandatory — without it the model hallucinated tool results (invented "Shipped" order status and "$226.55" AAPL price)
- After stop sequence fix: model correctly reads real errors and gives honest answers
- Task 3 (days until year end) fails due to format deviation — model produces prose instead of Thought/Action format
- Gemma 4 correctly identifies non-existent tools from system prompt alone without trying to call them
- Fallback recovery works correctly with stop sequence: tries primary tool, reads real error, tries fallback, reads real error, reports failure honestly
- Schema quality governs agent quality — a bad description breaks tool selection even with perfect code

**Known issues:**
- Task 3 ("days until year end") still fails with format deviation — fix requires stricter system prompt or more robust parser

**Additional experiment added (session 5):**
- `03-agent-architecture/code/03_pipeline_vs_agent.py` — runs same task through pipeline and agent across 3 scenarios (happy path, primary fails, all fail)
- `03-agent-architecture/notes/06-pipeline-vs-agent.md` — results + when to use each architecture

**Key finding from pipeline vs agent:** Both architectures produced identical results on all 3 scenarios. The difference is not in outcomes on known paths — it is in maintainability as requirements grow. Pipeline hardcodes every branch; agent discovers paths from tool descriptions at runtime.

**Status:** Phase 3 COMPLETE.

---

## Session 5 — 2026-04-21

**What was done — Phase 4: Edge AI and On-Device Intelligence**

**Notes written:**
- `04-edge-ai/notes/01-edge-ai-vs-cloud-ai.md` — five-axis decision framework (latency, cost, privacy, reliability, capability), decision matrix, hybrid architecture, enterprise tier model
- `04-edge-ai/notes/02-gemma-e2b-vs-26b-benchmark.md` — benchmark structure, task suite, results template (fill in after running)

**Code written:**
- `04-edge-ai/code/01_model_benchmark.py` — automated benchmark harness with LLM-as-judge scoring. Runs 6 tasks across 4 types (factual, reasoning, code, summarise) against both models.

**Benchmark results (M4, 24 GB, gemma4:e2b vs gemma4:26b):**
- E2B throughput: 51.9 tok/s avg | 26B throughput: 20.6 tok/s avg
- Speedup: 2.5x in E2B's favour
- Quality (judged by 26B): E2B 4.6/5 avg, 26B 4.8/5 avg
- Factual + summarise: identical quality (5/5 both) — always use E2B
- Reasoning: E2B 4/5 vs 26B 4.5/5 — 26B more reliable on multi-step
- Code: both functional; 26B better at following format constraints
- Memory: E2B ~7 GB loaded, 26B ~20 GB loaded

**Notes written:**
- `04-edge-ai/notes/03-model-routing.md` — three routing strategies (rule-based, classifier, confidence-based), routing table, failure modes, enterprise pattern

**Code written:**
- `04-edge-ai/code/02_model_router.py` — classifier router using E2B to classify, dispatches to E2B or 26B. 4/4 correct classifications on demo prompts.

**Router results:**
- Classifier overhead: ~200–400ms warm, ~5s cold (E2B not loaded)
- All four task types correctly classified and routed on first run
- 26B's `chunk_list` response: one-liner list comprehension, 13.6 tok/s
- E2B's summarise response: accurate, 54.7 tok/s

**Status:** Phase 4 COMPLETE.

---

## Session 6 — 2026-04-21

**What was done — Phase 5: Orchestration and Multi-Agent Systems**

**Notes written:**
- `05-orchestration-multi-agent/notes/01-multi-agent-architecture.md` — four single-agent failure modes, orchestrator/worker pattern, task decomposition, dependency graph, routing decision
- `05-orchestration-multi-agent/notes/02-gemma-as-worker.md` — worker contract, what Gemma handles well, output format spec, three context-passing patterns, error handling

**Code written:**
- `05-orchestration-multi-agent/code/01_orchestrated_agent.py` — fully local multi-agent system: Gemma 26B orchestrates and synthesises, E2B/26B workers execute sub-tasks by type

**Experiment results (M4 24 GB — fully local):**
- Request: 4-part transformer model explainer
- Decomposition: 4 sub-tasks (summarise x2, reasoning x1, code x1) — correct types assigned
- Sub-task 1 (summarise → E2B): 50.9 tok/s | 570 tokens | attention mechanism explanation
- Sub-task 2 (reasoning → 26B): 9.4 tok/s | 642 tokens | self-attention vs cross-attention comparison
- Sub-task 3 (code → 26B): 16.2 tok/s | 287 tokens | scaled dot-product attention in NumPy
- Sub-task 4 (summarise → E2B): 51.2 tok/s | 450 tokens | encoder/decoder architecture guide
- Final synthesis: structured multi-section response with table, code block, explanations
- Total worker tokens: 1,949 | All local — zero API cost

**Key finding:** Gemma 26B decomposed the 4-part request correctly on the first try, assigned correct task types, and the routing matched Phase 4 predictions. E2B handled summarise tasks at 5x the speed of 26B. The synthesised output was well-structured and publication-quality.

**Status:** Phase 5 COMPLETE.

---

## Session 7 — 2026-04-21

**What was done — Phase 6: Evaluation and Benchmarking**

**Notes written:**
- `06-evaluation/notes/01-why-llm-evaluation-is-hard.md` — 5 evaluation failure modes, non-determinism, benchmark gaming, verbosity/position bias, three evaluation approaches
- `06-evaluation/notes/02-llm-as-judge.md` — judge prompt design (4 components), calibration, known biases, experiment results
- `06-evaluation/notes/03-domain-specific-benchmark.md` — benchmark design principles, 10-question domain benchmark, experiment results with category breakdown

**Code written:**
- `06-evaluation/code/01_llm_judge.py` — standalone LLM judge: scores any response 1–5 with reasoning
- `06-evaluation/code/02_benchmark_harness.py` — full benchmark runner: 10 questions, model + judge calls, category report, quality gate

**Benchmark results (gemma4:26b, M4 24 GB):**
- Overall: 4.5/5 — quality gate (4.0) PASSED
- Best category: evaluation (5.0/5) — strong meta-knowledge
- Weakest category: edge_ai (4.0/5) — missed specific benchmark metrics
- Common failure mode: token limit truncation (3/4 scoring at 4/5 were truncated, not wrong)
- Judge calibration: 5, 3, 1 on good/partial/wrong answers — correct discrimination

**Status:** Phase 6 COMPLETE.

---

## Session 8 — 2026-04-21

**What was done — Phase 7: Production and Enterprise Patterns**

**Notes written:**
- `07-production-enterprise/notes/01-self-hosted-ai-architecture.md` — 5-layer architecture, 5 enterprise objections with answers, design decisions, throughput expectations, air-gap checklist
- `07-production-enterprise/notes/02-concurrency-and-throughput.md` — token bucket rate limiter, semaphore + bounded queue, thread pool offload, load behaviour table
- `07-production-enterprise/notes/03-audit-logging-compliance.md` — schema design, two-phase write pattern, experiment results with latency data, compliance export
- `07-production-enterprise/notes/04-guardrails-for-local-models.md` — 6 test cases run with real results, substring matching bug discovery (false negative on "capital"/"api"), defence-in-depth finding
- `07-production-enterprise/notes/05-air-gapped-deployment.md` — pre-staging checklist, Ollama telemetry disable, what changes vs connected, cross-model eval alternatives

**Code written:**
- `07-production-enterprise/code/01_concurrent_inference_server.py` — FastAPI wrapper with semaphore concurrency, bounded queue, token bucket rate limiter, /metrics endpoint, load test mode
- `07-production-enterprise/code/02_audit_logger.py` — SQLite-backed audit logger with two-phase write, per-user activity report, compliance JSON export
- `07-production-enterprise/code/03_guardrails.py` — input filter (injection, scope, PII), output filter (refusal, short response, PII), 6-case demo

**Experiment results:**

Audit logger (M4 24 GB, gemma4:26b):
- Request 1 (root cause question): 19,195ms — cold KV cache
- Request 2 (index creation question): 12,830ms — warm cache
- Request 3 (escalation question): 3,249ms — short answer, fast
- All 3 responses technically correct, logged to /tmp/audit.db

Guardrails (6 test cases):
- Case 1 — safe triage: OK (13,290ms)
- Case 2 — safe diagnosis: OK (13,550ms)
- Case 3 — injection "ignore instructions": BLOCKED (scope filter, not injection regex)
- Case 4 — injection "act as if": BLOCKED (injection pattern matched correctly)
- Case 5 — out of scope "capital of France": FALSE NEGATIVE — "capital" contains substring "api", passed scope check
- Case 6 — PII email in prompt: WARN (email regex matched correctly)

**Key finding:** substring keyword matching is fragile. `"api" in "capital"` is True. Production scope filters need word-boundary regex (`\bapi\b`) or a semantic classifier. Case 3 demonstrates defence-in-depth: injection regex missed but scope filter still blocked.

**Status:** Phase 7 IN PROGRESS — core patterns complete, bonus ITSM quality gate integration pending.

**Next:** 
1. (Optional) Wire ITSM quality gate from Phase 6 into the inference server
2. Update README.md with Phase 7 status and findings
3. Commit and push

---
