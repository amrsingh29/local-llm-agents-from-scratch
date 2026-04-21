# How LLMs Are Packaged and Distributed

## The Naive Question

"Can't I just download a model and run it?"

Yes — but most developers treat a model like an executable: download it, run it, done. That mental model breaks the moment you try to deploy it, optimize it, or explain to a client why it costs what it costs. Understanding what you actually downloaded changes how you architect every system that uses it.

---

## What a Model Actually Is

A trained neural network is, at its core, a very large collection of numbers called **weights** (or parameters). These numbers encode everything the model learned during training — grammar, facts, reasoning patterns, code syntax.

Gemma 4 26B has approximately **26 billion** of these numbers.

The "26B" is not marketing. It is a direct count of parameters. More parameters generally means more capacity to represent complex patterns — but also more memory required to hold them.

---

## The Storage Problem

26 billion floating-point numbers at full 32-bit precision would require:

```
26,000,000,000 × 4 bytes = 104 GB
```

That does not fit on a 24 GB MacBook. It does not fit on most consumer hardware at all.

This is why **quantization** exists — but we will cover that in the next note. First, the file format.

---

## GGUF: The File Format That Made Local LLMs Possible

When you ran `ollama pull gemma4:26b`, you downloaded a file in **GGUF format** (GPT-Generated Unified Format).

GGUF was created by the llama.cpp project and has become the standard for distributing models that run on consumer hardware. Before GGUF, running models locally required complex Python environments, fragile dependencies, and GPU-specific builds. GGUF consolidates everything into a single portable file.

A GGUF file contains:

| Section | What it holds |
|---------|--------------|
| Header | Model architecture, vocabulary size, context length, quantization type |
| Tokenizer | The vocabulary — every token the model knows |
| Tensor data | The actual weights, stored in the quantized format |
| Metadata | Author, license, training details |

One file. Self-describing. No separate config files needed.

---

## Safetensors: The Other Format

You will encounter **safetensors** format when working with Hugging Face models. This is the format used for training and fine-tuning — it preserves full precision and is safe to load (no arbitrary code execution, unlike the older pickle-based `.pt` format).

The typical workflow:
1. Model is trained and saved as safetensors (full precision, large)
2. Converted to GGUF with quantization applied (smaller, consumer-friendly)
3. Distributed via Ollama, Hugging Face, or direct download

When Ollama pulls `gemma4:26b`, it is fetching a GGUF file that Google (or the community) already converted and quantized.

---

## How Ollama Wraps the Model

Ollama is not a model. It is an **inference server** that:

1. Downloads and manages GGUF files on disk
2. Loads the model into memory when first called
3. Runs inference using llama.cpp under the hood
4. Exposes a local REST API at `http://localhost:11434`
5. Handles GPU acceleration automatically (Metal on Apple Silicon)

This is why your Python script used `requests.post()` to a local URL — you were talking to the Ollama server, which in turn ran inference on the model.

```
Your Python script
      ↓  HTTP POST
Ollama server (port 11434)
      ↓  llama.cpp
GGUF model weights (in memory)
      ↓  Metal GPU
Apple M4 unified memory
```

The REST API approach has an important enterprise implication: **the model is decoupled from your application code**. You can swap models, update versions, or run multiple models without touching your application. This is the same pattern used by OpenAI, Anthropic, and every major AI provider — Ollama just runs it locally.

---

## Apple Unified Memory: Why This Matters

Traditional computers have two separate memory pools:
- **RAM**: used by the CPU
- **VRAM**: used by the GPU (typically 8–24 GB on consumer cards)

Running a large model on a traditional GPU means fitting it entirely within VRAM. A 26B parameter model at even moderate quantization does not fit in 24 GB of traditional VRAM.

Apple Silicon uses **unified memory architecture (UMA)**: a single pool of memory shared between CPU, GPU, and Neural Engine. On your M4 Mac with 24 GB:

- The model weights load into the shared 24 GB pool
- The GPU (Metal) accesses those weights directly — no data copy between CPU RAM and GPU VRAM
- The Neural Engine can assist with specific operations

This is why Gemma 4 26B runs on a 24 GB MacBook but would struggle on a PC with a 24 GB GPU — on the PC, the OS, applications, and model would compete for that 24 GB of VRAM.

---

## What You Actually Downloaded

When you ran `ollama pull gemma4:26b`, you got:

- A GGUF file stored at `~/.ollama/models/`
- Quantized to reduce size from ~104 GB to ~17 GB
- Pre-configured to use Metal GPU on Apple Silicon
- Wrapped by Ollama's server process when you call `ollama serve`

The 17 GB on disk becomes approximately 17–20 GB in memory during inference, leaving a few GB for the OS and your application.

---

## Enterprise Takeaway

Every enterprise conversation about "running AI on-premise" starts here. The questions you can now answer:

- **"How much storage do we need?"** — The GGUF file size, plus overhead. For 26B: ~17 GB.
- **"How much RAM does the server need?"** — Model size plus inference overhead. For 26B: 20–24 GB minimum.
- **"Can we run this on our existing GPU servers?"** — Depends on VRAM. UMA architecture (Apple Silicon) has an advantage here.
- **"How do we update the model?"** — `ollama pull` fetches the new version. Your application code does not change.
- **"What format is the model in?"** — GGUF. Self-contained, portable, no Python environment required at runtime.

Understanding the packaging layer is what separates someone who *uses* AI from someone who can *deploy and own* it.

---

## Key Terms

| Term | Definition |
|------|-----------|
| Parameters / Weights | The numbers that encode what a model learned |
| GGUF | Portable file format for distributing quantized LLMs |
| Safetensors | Full-precision format used for training and fine-tuning |
| Quantization | Reducing weight precision to shrink model size (covered next) |
| Unified Memory (UMA) | Apple Silicon's shared CPU/GPU memory pool |
| Ollama | Local inference server that wraps GGUF models behind a REST API |

---

## Next

**Quantization from First Principles** — why the 17 GB file is not the same model as the 104 GB original, and when that difference matters.
