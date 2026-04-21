# Ollama Architecture — How the Local Inference Server Works

## The Naive Assumption

"Ollama is just a wrapper that runs the model."

That is partially true but misses what makes it useful in practice. Ollama is a production-grade inference server — it manages model lifecycle, GPU scheduling, concurrent requests, and API compatibility. Understanding its architecture tells you what you can and cannot build on top of it.

---

## The Full Stack

When you run `ollama serve` and call `http://localhost:11434/api/generate`, this is what happens:

```
Your Application (Python, curl, any HTTP client)
        ↓  HTTP POST /api/generate
Ollama Server (Go process, port 11434)
        ↓  model management + request routing
llama.cpp (C++ inference engine)
        ↓  tensor operations
Metal GPU / CPU (Apple Silicon)
        ↓  computation
Unified Memory (model weights + KV cache)
```

Each layer has a distinct responsibility. Let's go through them.

---

## Layer 1 — The Ollama Server (Go)

Ollama's server is written in Go. It handles:

**Model lifecycle management**
- Downloads and stores GGUF files at `~/.ollama/models/`
- Loads models into memory on first request
- Keeps models loaded for a configurable idle timeout (default: 5 minutes)
- Unloads models from memory when idle to free RAM

**Request routing**
- Accepts HTTP requests on port 11434
- Queues concurrent requests when a model is busy
- Routes to the correct model if multiple are loaded

**API surface**
- `/api/generate` — single-turn completion
- `/api/chat` — multi-turn conversation with message history
- `/api/embeddings` — generate vector embeddings
- `/api/pull`, `/api/push`, `/api/delete` — model management
- OpenAI-compatible endpoints at `/v1/chat/completions` — drop-in replacement for OpenAI SDK calls

The OpenAI-compatible endpoint is significant: any application built for OpenAI can point at Ollama with a URL change. No code rewrite required.

---

## Layer 2 — llama.cpp (C++ Inference Engine)

Ollama uses **llama.cpp** as its inference backend. llama.cpp is an open-source C++ library that:

- Loads GGUF files and maps weights into memory
- Implements the transformer forward pass in optimized C++
- Handles quantized arithmetic (INT4, INT8, FP16 operations)
- Dispatches compute to the available hardware backend

llama.cpp is the reason local LLM inference became practical on consumer hardware. Before it, running a transformer model required Python, PyTorch, CUDA, and a dedicated GPU. llama.cpp runs on CPU, Apple Silicon, NVIDIA, AMD — with a single binary.

Ollama ships llama.cpp compiled for your platform. You never interact with it directly — Ollama manages it as a subprocess.

---

## Layer 3 — Metal GPU Backend (Apple Silicon)

On your M4 Mac, llama.cpp dispatches tensor operations to Apple's **Metal** GPU framework.

The key operations offloaded to Metal:
- Matrix multiplications (the dominant operation in transformer inference)
- Attention score computation
- Softmax and normalization

The CPU handles:
- Tokenization (converting text to token IDs)
- Sampling (selecting the next token from the probability distribution)
- Memory management and KV cache coordination

Because Apple Silicon uses **unified memory**, the GPU reads model weights directly from the same RAM pool the CPU uses — no data transfer across a PCIe bus. This is a meaningful latency advantage over discrete GPU setups.

The `OLLAMA_FLASH_ATTENTION="1"` flag you set enables an optimized attention algorithm that reduces memory bandwidth usage — important when the model and KV cache are competing for the same unified memory pool.

---

## The KV Cache — What It Is and Why It Matters

Every time the model generates a token, it computes **attention** over all previous tokens. Recomputing this from scratch for every new token would be prohibitively slow.

The **KV cache** (Key-Value cache) stores the attention computation for all previous tokens so it only needs to be computed once. As generation continues, the cache grows:

```
Token 1:   compute attention → cache [K1, V1]
Token 2:   compute attention → cache [K1, V1, K2, V2]
Token 3:   compute attention → cache [K1, V1, K2, V2, K3, V3]
...
Token N:   only compute KN, VN — reuse everything else from cache
```

The KV cache is stored in RAM alongside the model weights. For a 26B model with a long context window (256K tokens), the KV cache can grow to several GB. This is why the `OLLAMA_KV_CACHE_TYPE="q8_0"` flag matters — it quantizes the cache to 8-bit integers, reducing its memory footprint without significantly affecting output quality.

---

## Model Loading Lifecycle

Understanding when Ollama loads and unloads models matters for production use:

```
First request arrives
        ↓
Model not in memory → load from disk (~10–30 seconds for 26B)
        ↓
Model loaded → inference runs → response returned
        ↓
Subsequent requests → model already in memory → fast (~1–2 seconds to first token)
        ↓
No requests for 5 minutes → model unloaded from memory
        ↓
Next request → cold load again
```

**Enterprise implication:** the first request after a cold start is slow. In production, you either keep the model warm with periodic pings, or pre-load it at server startup. Ollama supports pre-loading via:

```bash
ollama run gemma4:26b --keepalive -1
```

The `-1` value keeps the model loaded indefinitely.

---

## Concurrency Model

Ollama processes one inference request at a time per model. Concurrent requests are queued.

This is different from cloud APIs, which handle thousands of parallel requests. On a single 24 GB Mac:

- Request 1 starts → uses ~20 GB RAM for model + KV cache
- Request 2 arrives → queued until Request 1 completes
- Request 2 starts → reuses already-loaded model weights

The model weights are loaded once and shared across requests. Only the KV cache is per-request.

In Phase 7 (Production), you will build a request queue and rate limiter on top of Ollama to manage this constraint properly — simulating a realistic multi-user deployment.

---

## The REST API in Detail

Your Python script from `01_first_inference.py` called `/api/generate`. Here is the full request structure:

```json
{
  "model": "gemma4:26b",
  "prompt": "Your prompt here",
  "stream": false,
  "options": {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
    "num_predict": 512
  }
}
```

And the response:

```json
{
  "model": "gemma4:26b",
  "response": "The generated text...",
  "done": true,
  "prompt_eval_count": 12,
  "eval_count": 47,
  "eval_duration": 2193000000,
  "total_duration": 22847000000
}
```

Key response fields:

| Field | Meaning |
|-------|---------|
| `prompt_eval_count` | Tokens in your prompt (input tokens) |
| `eval_count` | Tokens generated (output tokens) |
| `eval_duration` | Time spent on generation (nanoseconds) |
| `total_duration` | Total time including model load (nanoseconds) |

Tokens per second = `eval_count / (eval_duration / 1e9)`

This is exactly what `01_first_inference.py` computes.

---

## Streaming vs Non-Streaming

With `"stream": false`, Ollama waits for full generation then returns the complete response. This is simple but means your application blocks until the model finishes.

With `"stream": true`, Ollama returns tokens as they are generated — one JSON object per line, each with a partial `response` field. This is how chat interfaces show text appearing word by word.

For the experiments in this project, non-streaming is fine. For any user-facing application, streaming is essential — users perceive a streaming response as faster even if total generation time is identical.

---

## Enterprise Architecture Implications

Ollama's architecture maps directly to enterprise deployment decisions:

**"How do we serve multiple teams from one model?"**
One Ollama instance, one model loaded. Requests queue. For higher concurrency, run multiple Ollama instances behind a load balancer — each on its own server.

**"How do we integrate with our existing OpenAI-based tooling?"**
Point the OpenAI SDK at `http://your-server:11434/v1`. Change the base URL. Done.

**"How do we monitor inference performance?"**
Parse the `eval_duration` and `eval_count` fields from every response. You have tokens/second, latency, and input/output token counts — everything you need for a performance dashboard.

**"How do we ensure the model is always ready?"**
Use `--keepalive -1` to prevent unloading. Add a health check endpoint (`GET /api/tags`) to your monitoring. Alert if response time exceeds threshold.

---

## Key Terms

| Term | Definition |
|------|-----------|
| llama.cpp | C++ inference engine that runs the transformer forward pass |
| Metal | Apple's GPU compute framework used for tensor operations |
| KV cache | Stores attention computations for previous tokens to avoid recomputation |
| Flash Attention | Memory-efficient attention algorithm that reduces bandwidth usage |
| Streaming | Returning tokens as generated rather than waiting for full completion |
| Keepalive | Configuration that prevents Ollama from unloading idle models |

---

## Next

**Gemma 4 Model Variants** — E2B, E4B, 26B, 31B explained: what the naming means, why E2B runs on a phone, and the decision framework for choosing between them.

> Note: If you followed this series in order, you may have already read the model variants note. It was written out of sequence because the question came up naturally during installation. That is how real learning works.
