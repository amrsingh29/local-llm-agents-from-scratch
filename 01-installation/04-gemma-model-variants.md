# Gemma 4 Model Variants — E2B, E4B, 26B, 31B Explained

## The Question That Exposes a Gap

Most developers look at a model list and pick by size: "bigger is better." But Gemma 4 has variants that are not simply scaled-up versions of each other. They have different architectures, different deployment targets, and different cost profiles. Picking the wrong one does not just waste compute — it means your architecture is wrong from the start.

---

## The Gemma 4 Family

| Model | Parameters | Active at Inference | File Size | RAM Needed | Context |
|-------|-----------|-------------------|-----------|-----------|---------|
| E2B | 2.3B (dense) | 2.3B (all) | ~2.54 GB | ~1.5 GB | 128K |
| E4B | 4B (dense) | 4B (all) | ~4.5 GB | ~3 GB | 128K |
| 26B (A4B) | 26B (MoE) | 4B (subset) | ~17 GB | ~20 GB | 256K |
| 31B | 31B (MoE) | subset | ~20 GB | ~24 GB | 256K |

---

## What "E" Means — Effective Parameters

The "E" in E2B and E4B stands for **Effective**. These are dense models — every parameter participates in every inference. There is no routing, no expert selection. What you see is what runs.

Google uses "effective" to signal that these models punch above their raw parameter count through architectural tricks like **Per-Layer Embeddings (PLE)** — a technique that maximizes what each parameter contributes without adding more of them.

Think of it like a small, highly trained specialist team versus a large generalist workforce. Fewer people, more output per person.

---

## What "A" Means — Active Parameters (Mixture of Experts)

The 26B model's full name is **26B-A4B**: 26 billion total parameters, 4 billion active per token.

This is a **Mixture of Experts (MoE)** architecture. Instead of one monolithic network, the model contains many specialized sub-networks called "experts." For each token, a routing mechanism selects which 4B worth of experts to activate. The other 22B sit idle.

The implication:
- **Inference cost** is similar to a 4B dense model (only 4B active)
- **Knowledge capacity** is closer to a 26B model (all experts trained, all knowledge encoded)
- **Memory requirement** is the full 26B (all experts must be loaded, even if not all fire)

This is why 26B runs on a 24 GB Mac — but still needs all 17 GB loaded into memory.

---

## Why E2B Is 2.54 GB and Runs on a Phone

Three compounding factors make E2B phone-friendly:

**1. Fewer parameters**
2.3B vs 26B — roughly 11x fewer numbers to store.

**2. Quantization**
The distributed GGUF file uses 4-bit or 8-bit quantization instead of full 32-bit precision. At 4-bit, the model fits in ~1.5 GB of RAM. We cover quantization in detail in the next note.

**3. Dense architecture**
No MoE routing overhead. The model is a single, compact network optimized for low-latency execution on mobile hardware.

Google designed E2B specifically to run via **Google AICore** on Android devices — completely offline, no network call, no API key, no cost per inference.

---

## Architecture Comparison

Both families share Gemma 4's core design — hybrid attention that interleaves local sliding window attention with global attention. But they diverge in scale and deployment target:

| Property | E2B / E4B | 26B / 31B |
|----------|-----------|-----------|
| Architecture | Dense | Mixture of Experts |
| Deployment target | Device / edge | Server / workstation |
| Context window | 128K tokens | 256K tokens |
| Multimodal (vision, audio) | Yes | Yes |
| Function calling | Yes | Yes |
| Offline capable | Yes | Yes (on right hardware) |
| API cost | Zero (on-device) | Zero (self-hosted) |

---

## Use Cases by Model

### Gemma 4 E2B — On-Device Intelligence

Best for situations where the data cannot or should not leave the device:

- **Mobile apps** — AI features that work without internet (autocomplete, summarization, translation)
- **IoT and edge devices** — smart cameras, industrial sensors, local inference at the source
- **Medical and legal tools** — patient intake, document review where data must stay on-device
- **Air-gapped environments** — factory floors, military, remote field operations
- **Zero-cost inference** — no server, no API bill, runs on the user's own hardware

The tradeoff: simpler reasoning, shorter context, will struggle with complex multi-step tasks.

### Gemma 4 26B — On-Premise Server Intelligence

Best for situations where the data cannot leave the organization but quality cannot be compromised:

- **Team AI assistant** — one Mac Mini or workstation serving 5–10 users via a local REST API
- **Enterprise document analysis** — contracts, RFPs, compliance documents processed on-premise
- **Code generation** — complex, multi-file reasoning that small models cannot handle
- **RAG pipelines** — retrieval-augmented generation where answer quality matters
- **Agent systems** — worker agent in a multi-agent architecture, orchestrated by a more capable model
- **Regulated industries** — banking, healthcare, defense where cloud APIs are prohibited

The tradeoff: needs significant hardware, not deployable to a phone or low-power device.

---

## The Decision Framework

```
Can the data leave the device?
├── No → Use E2B (on-device, offline, zero cost)
└── Yes, but can it leave the building?
    ├── No → Use 26B (on-premise server, high quality)
    └── Yes → Use cloud API (OpenAI, Anthropic, Google)
```

This framework is the foundation of every enterprise Edge AI conversation. The question is never "which model is best?" — it's "where does the data need to stay?"

---

## What This Means for This Project

This tutorial uses **Gemma 4 26B** as the primary model — it runs on a 24 GB M4 Mac and provides production-grade quality for learning agent architecture, orchestration, and enterprise patterns.

In Phase 4 (Edge AI), we will run the same tasks on **E2B** and compare:
- Quality of responses side by side
- Latency difference
- Memory footprint
- Which tasks E2B handles adequately vs where 26B is necessary

That comparison produces the decision framework you can bring into any enterprise architecture conversation.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Dense model | Every parameter activates on every inference |
| MoE (Mixture of Experts) | Only a subset of parameters activate per token |
| Active parameters | The parameters that actually compute during inference |
| PLE (Per-Layer Embeddings) | Technique to maximize small model efficiency |
| AICore | Google's on-device AI runtime for Android |
| Edge AI | Running inference at the data source, not in the cloud |
