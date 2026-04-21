# Gemma Local AI — Learning Curriculum

> **Model:** Google Gemma 4 26B (MoE, runs on 24 GB Apple M4)
> **Tool:** Ollama (local inference server)
> **Goal:** Master LLM fundamentals, AI Agents, and Edge AI through hands-on local experimentation
> **Audience:** Amrendra — building toward tutorial publication and enterprise thought leadership
> **Philosophy:** First principles always. Show why naive approaches fail before presenting the right solution.

---

## Hardware Context

| Spec | Value |
|------|-------|
| Chip | Apple M4 |
| RAM | 24 GB Unified Memory |
| GPU | Metal 4 |
| Model | Gemma 4 26B MoE (4B active params at inference) |
| Inference | Ollama via Metal GPU acceleration |

---

## The Core Insight This Journey Teaches

> Most enterprise AI projects fail not because models are bad, but because teams don't understand the tradeoffs between **cloud vs local**, **quality vs cost**, and **capability vs privacy**.
> Running a model from scratch — from raw bits to working agent — gives you visceral, first-principles understanding of all three.

---

## Phase 1 — Installation & Infrastructure

> Duration: ~1 day | Status: [ ] Not Started

### What You'll Learn
- How LLMs are packaged and distributed (GGUF, safetensors formats)
- What quantization is: why Q4 is not the same model as Q8, and when that matters
- How Ollama wraps a model and exposes it as a local REST API
- How Apple's unified memory architecture differs from traditional GPU VRAM
- How Metal GPU acceleration works for inference on Apple Silicon

### The Naive Question to Start With
"Can't I just download a model and run it?" — yes, but understanding *what* you're downloading and *how* it runs changes how you architect every system afterward.

### Experiments
1. Install Ollama, pull Gemma 4 26B, run first inference
2. Check memory usage during inference (`Activity Monitor` / `powermetrics`)
3. Run same prompt 3 times with different temperature settings — observe variance
4. Time a 100-token response vs 1000-token response — understand throughput

### Key Files
- `notes/01-how-llms-are-packaged.md`
- `notes/02-quantization-from-first-principles.md`
- `notes/03-ollama-architecture.md`
- `code/01_first_inference.py`
- `code/02_benchmark_throughput.py`

### Enterprise Connection
On-premise AI deployment starts here. Every enterprise that says "we can't send data to the cloud" needs someone who understands exactly this layer.

---

## Phase 2 — LLM Fundamentals

> Duration: ~3 days | Status: [ ] Not Started

### What You'll Learn
- Tokens: what they are, how text is split, why "4 chars per token" is a lie
- Context windows: why 256K tokens ≠ infinite memory
- Temperature, top-p, top-k: the knobs that control output randomness
- The stateless nature of LLMs: why every call is a fresh start
- System prompts: how they shape model behavior
- Few-shot prompting: teaching via examples in-context
- Chain-of-thought: why "think step by step" actually works

### The Naive Approach That Fails
Treating an LLM like a database: "store a fact, retrieve it later." Show why this breaks without understanding statelessness.

### Experiments
1. Tokenize the same sentence 5 ways — watch token counts change
2. Fill context window to 90% — observe degraded recall (the "lost in the middle" problem)
3. Run identical prompt at temp=0, temp=0.5, temp=1.5 — build intuition
4. Send a 10-message conversation without history vs with history — prove statelessness
5. System prompt A vs System prompt B on the same question — measure behavioral shift

### Key Files
- `notes/01-tokens-from-first-principles.md`
- `notes/02-context-window-limits-and-tricks.md`
- `notes/03-temperature-and-sampling.md`
- `notes/04-statelessness-why-llms-forget.md`
- `notes/05-prompt-engineering-as-programming.md`
- `code/01_tokenization_experiments.py`
- `code/02_context_window_limits.py`
- `code/03_temperature_experiments.py`
- `code/04_stateless_proof.py`

### Enterprise Connection
Every failed LLM deployment traces back to someone not understanding one of these fundamentals. This is the knowledge that separates engineers from power users.

---

## Phase 3 — Agent Architecture

> Duration: ~4 days | Status: [ ] Not Started

### What You'll Learn
- What makes something an "agent" vs a chatbot vs a pipeline
- The agent loop: Perceive → Think → Act → Observe (repeat)
- ReAct pattern: the bedrock of modern agents (Reasoning + Acting interleaved)
- Tool/function calling: how the model signals "I need to use a tool"
- Tool schema design: why a poorly designed tool schema breaks agents
- Error handling in tool use: what happens when tools fail

### The Naive Approach That Fails
Chaining prompts sequentially (a "pipeline") and calling it an agent. Show why it breaks on anything non-linear.

### Experiments
1. Build a bare-metal ReAct agent calling Gemma locally — no LangChain, no frameworks
2. Wire up 3 real tools: web search, calculator, file reader
3. Deliberately break a tool — watch how the agent handles failure
4. Compare pipeline (fixed steps) vs agent (dynamic steps) on the same task

### Key Files
- `notes/01-what-is-an-agent-vs-pipeline.md`
- `notes/02-the-agent-loop.md`
- `notes/03-react-pattern-from-first-principles.md`
- `notes/04-tool-calling-internals.md`
- `notes/05-tool-schema-design.md`
- `code/01_bare_metal_react_agent.py`
- `code/02_tool_calling_deep_dive.py`
- `code/03_agent_error_handling.py`

### Enterprise Connection
The ReAct pattern is how every production agent works today — Copilot, Claude, Gemini agents. Understanding it from scratch means you can debug, extend, and audit any agent system.

---

## Phase 4 — Edge AI & On-Device Intelligence

> Duration: ~3 days | Status: [ ] Not Started

### What You'll Learn
- What "Edge AI" means: inference at the source, not in the cloud
- The spectrum: cloud → on-premise server → edge device → mobile → microcontroller
- Privacy-first AI: how local inference eliminates data exfiltration risk
- Quantization deep dive: INT4, INT8, FP16, FP32 — quality vs speed tradeoffs
- Hardware-aware inference: Neural Engine, GPU, CPU — which runs what and why
- Latency vs throughput: optimizing for real-time response vs batch processing
- When local beats cloud: the decision framework

### The Naive Question That Exposes Gaps
"Why not just use ChatGPT?" — show the 5 enterprise scenarios where that answer is wrong.

### Experiments
1. Benchmark Gemma 26B local vs Claude API: latency, throughput, quality on same tasks
2. Run Q4 vs Q8 quantization — measure quality degradation on reasoning tasks
3. Profile inference: which chip (CPU/GPU/Neural Engine) handles which operations
4. Build latency dashboard: tokens/second under load
5. Simulate air-gapped environment: no internet, full agent still runs

### Key Files
- `notes/01-what-is-edge-ai.md`
- `notes/02-the-cloud-vs-local-decision-framework.md`
- `notes/03-quantization-quality-tradeoffs.md`
- `notes/04-hardware-aware-inference-apple-silicon.md`
- `notes/05-privacy-first-ai-enterprise-patterns.md`
- `code/01_latency_benchmark.py`
- `code/02_quantization_comparison.py`
- `code/03_throughput_under_load.py`

### Enterprise Connection
Regulated industries — banking, defense, healthcare, legal — cannot send data to cloud APIs. This phase makes you the person who can architect the alternative.

---

## Phase 5 — Orchestration & Multi-Agent Systems

> Duration: ~4 days | Status: [ ] Not Started

### What You'll Learn
- Why single agents fail at complex, long-horizon tasks
- Orchestrator + worker agent pattern
- Using Gemma as a worker, Claude as orchestrator — heterogeneous multi-agent systems
- Model routing: right model for the right task (cost vs quality)
- Shared vs isolated memory across agents
- Human-in-the-loop design: when to pause and ask

### The Naive Approach That Fails
One giant agent trying to do everything. Show how context blows up and reasoning degrades.

### Experiments
1. Build orchestrator (Claude) + worker (Gemma) — assign tasks by complexity
2. Implement model routing: if task is simple → Gemma, if complex → Claude
3. Shared memory experiment: multiple agents reading/writing a shared context store
4. Measure cost: all-Claude vs routed (Gemma for 80% of calls) — compute savings

### Key Files
- `notes/01-why-single-agents-fail.md`
- `notes/02-orchestrator-worker-pattern.md`
- `notes/03-model-routing-cost-quality-tradeoff.md`
- `notes/04-heterogeneous-multi-agent-systems.md`
- `code/01_orchestrator_worker.py`
- `code/02_model_router.py`
- `code/03_shared_memory_agents.py`

### Enterprise Connection
Cost optimization is the #1 enterprise ask after initial LLM deployment. This phase directly answers "how do we cut our AI API bill by 70% without sacrificing quality?"

---

## Phase 6 — Evaluation & Benchmarking

> Duration: ~3 days | Status: [ ] Not Started

### What You'll Learn
- Why LLM evaluation is fundamentally hard (non-determinism, subjectivity)
- LLM-as-judge pattern: using Gemma to evaluate other models (free evaluation!)
- Building your own benchmark: domain-specific, not generic
- Quality vs cost matrix: when is "good enough" actually good enough?
- Comparing Gemma 26B vs Claude on your specific use cases
- Automated regression testing for agents

### The Naive Approach That Fails
Using MMLU/benchmark scores as a proxy for your actual use case. Show why a model that scores 90% on MMLU can fail your domain tasks.

### Experiments
1. Build a 50-question benchmark for a specific domain (e.g., IT change management)
2. Run Gemma 26B and Claude on same benchmark — score with LLM-as-judge
3. Build automated eval harness: push code → run benchmark → get quality report
4. Cost analysis: if Gemma scores 85% and Claude scores 92%, what is the 7% worth?

### Key Files
- `notes/01-why-llm-evaluation-is-hard.md`
- `notes/02-llm-as-judge-pattern.md`
- `notes/03-building-domain-specific-benchmarks.md`
- `notes/04-quality-vs-cost-decision-matrix.md`
- `code/01_llm_judge.py`
- `code/02_benchmark_harness.py`
- `code/03_cost_quality_analysis.py`

### Enterprise Connection
Every enterprise AI investment needs an ROI story. This phase gives you the framework to measure and communicate value — critical for your presales role.

---

## Phase 7 — Production & Enterprise Patterns

> Duration: ~4 days | Status: [ ] Not Started

### What You'll Learn
- Self-hosted AI architecture: what it takes to run your own model in an enterprise
- Air-gapped deployments: no internet, fully local, fully auditable
- Throughput and concurrency: multiple simultaneous users on one model
- Guardrails and content safety for local models
- Audit logging: every inference logged, traceable, compliant
- Multi-tenancy: one model, many isolated customers
- Security: prompt injection, data leakage prevention, RBAC

### Experiments
1. Run Ollama with 5 concurrent users — measure degradation
2. Build a request queue + rate limiter around local Gemma
3. Add audit logging: every prompt and response stored with timestamp + user ID
4. Implement guardrails: input/output filtering before/after Gemma
5. Multi-tenant isolation: user A cannot see user B's conversation history

### Key Files
- `notes/01-self-hosted-ai-architecture.md`
- `notes/02-air-gapped-deployment-patterns.md`
- `notes/03-concurrency-and-throughput.md`
- `notes/04-guardrails-for-local-models.md`
- `notes/05-audit-logging-compliance.md`
- `code/01_concurrent_inference_server.py`
- `code/02_audit_logger.py`
- `code/03_guardrails.py`
- `code/04_multi_tenant_isolation.py`

### Enterprise Connection
This is the phase that makes you dangerous in a presales conversation. You can speak to every objection: "how do we keep data on-premise?", "how do we audit AI usage?", "how do we scale this?"

---

## Cross-Cutting Themes (All Phases)

| Theme | What You'll Build |
|-------|-------------------|
| Cost awareness | Token/compute cost tracker for every experiment |
| Security | Prompt injection tests in every agent built |
| Observability | Latency + quality metrics logged from day one |
| Enterprise narrative | "How would I sell this?" after every phase |

---

## Suggested Weekly Sequence

| Week | Focus | Milestone |
|------|-------|-----------|
| 1 | Phases 1-2: Install + LLM Fundamentals | Gemma running, 5 experiments done |
| 2 | Phase 3: Agent Architecture | Bare-metal ReAct agent with real tools |
| 3 | Phase 4: Edge AI | Benchmark report: Gemma vs Claude |
| 4 | Phase 5: Orchestration | Heterogeneous multi-agent system running |
| 5 | Phase 6: Evaluation | Domain benchmark harness complete |
| 6 | Phase 7: Production | Self-hosted AI with audit logs + multi-tenancy |

---

## Publishing Plan

Each phase produces one tutorial for Amrendra's website:

| Phase | Tutorial Title |
|-------|---------------|
| 1-2 | "Running a 26B AI Model Locally on a MacBook — What I Learned" |
| 3 | "Building an AI Agent From Scratch Using a Local Model" |
| 4 | "Edge AI vs Cloud AI: A Practical Decision Framework" |
| 5 | "Cutting Your AI API Bill by 70% With Model Routing" |
| 6 | "How to Evaluate LLMs for Your Specific Use Case" |
| 7 | "Self-Hosted AI for the Enterprise: Architecture, Security, and Compliance" |

---

## Quick Reference

```bash
# Start Ollama
ollama serve

# Pull Gemma 4 (check latest tag at ollama.com/library/gemma4)
ollama pull gemma4:26b

# Run interactive chat
ollama run gemma4:26b

# API call (Python)
import requests
response = requests.post("http://localhost:11434/api/generate", json={
    "model": "gemma4:26b",
    "prompt": "Your prompt here",
    "stream": False
})
print(response.json()["response"])
```
