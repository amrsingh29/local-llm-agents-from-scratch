# CLAUDE.md — Gemma Local AI

## What This Project Is

A structured, hands-on learning project where Amrendra runs Google Gemma 4 26B locally on his Apple M4 Mac (24 GB RAM) using Ollama, and uses it as the primary vehicle to learn LLM fundamentals, AI Agent architecture, Edge AI, and enterprise deployment patterns.

Everything built here is written toward publication as a tutorial series on his website.

---

## Hardware

| Spec | Value |
|------|-------|
| Chip | Apple M4 |
| RAM | 24 GB Unified Memory |
| GPU | Metal 4 |
| Model | Gemma 4 26B MoE |
| Inference tool | Ollama |

---

## Project Structure

```
gemma-local-ai/
├── CLAUDE.md                   ← You are here
├── CURRICULUM.md               ← Full 7-phase learning plan
├── PROGRESS.md                 ← Session log — READ THIS EACH SESSION
├── 01-installation/
│   ├── notes/                  ← Publishable concept notes (.md)
│   └── code/                   ← Runnable Python experiments
├── 02-llm-fundamentals/
├── 03-agent-architecture/
├── 04-edge-ai/
├── 05-orchestration-multi-agent/
├── 06-evaluation/
├── 07-production-enterprise/
└── resources/
```

---

## The 7 Phases

| Phase | Topic | Key Deliverable |
|-------|-------|-----------------|
| 1 | Installation & Infrastructure | Gemma running, Metal GPU verified |
| 2 | LLM Fundamentals | 5 hands-on experiments (tokens, context, temperature, statelessness, prompting) |
| 3 | Agent Architecture | Bare-metal ReAct agent calling Gemma locally |
| 4 | Edge AI & On-Device Intelligence | Gemma vs Claude benchmark + decision framework |
| 5 | Orchestration & Multi-Agent | Model routing: Gemma (worker) + Claude (orchestrator) |
| 6 | Evaluation & Benchmarking | Domain-specific benchmark harness with LLM-as-judge |
| 7 | Production & Enterprise | Self-hosted AI with audit logs, concurrency, guardrails |

Full details in `CURRICULUM.md`.

---

## Your Role Each Session

1. **Read `PROGRESS.md` first** — know exactly where we left off
2. **Teach from first principles** — why the problem exists before how to solve it
3. **Show the naive approach that fails** — before presenting the right solution
4. **Build working code** — save to the phase's `code/` folder
5. **Write publishable notes** — save to the phase's `notes/` folder
6. **Apply enterprise lens** — connect every concept to real-world business impact
7. **Update `PROGRESS.md`** — after each concept or experiment completed

---

## File Naming Convention

| Type | Pattern | Example |
|------|---------|---------|
| Notes | `NN-topic-name.md` | `01-how-llms-are-packaged.md` |
| Code | `NN_topic_name.py` | `01_first_inference.py` |

---

## Teaching Style

- No emojis
- First principles before frameworks
- Enterprise lens on every concept
- Always show why the naive approach fails before the right solution
- Notes written in publishable tutorial format (clear headings, examples, takeaways)

---

## Ollama Quick Reference

```bash
# Start server
ollama serve

# Pull model (verify tag at ollama.com/library)
ollama pull gemma4:26b

# Chat
ollama run gemma4:26b

# API call from Python
import requests
response = requests.post("http://localhost:11434/api/generate", json={
    "model": "gemma4:26b",
    "prompt": "Your prompt here",
    "stream": False
})
print(response.json()["response"])
```

---

## Connection to Main Roadmap

This project is a parallel track alongside `ai-agents-mastery/`. Concepts learned here feed directly into:
- Phase 1 (Foundations) — agent loop experiments using Gemma
- Phase 2 (Memory) — RAG with local model
- Phase 5 (Multi-Agent) — Gemma as worker agent
- Phase 6 (Evaluation) — LLM-as-judge using Gemma (free evals)
- Phase 7 (Production) — self-hosted deployment patterns
