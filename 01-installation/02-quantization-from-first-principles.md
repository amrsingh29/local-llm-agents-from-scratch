# Quantization From First Principles

## The Problem

Gemma 4 26B at full precision would require 104 GB of storage and RAM. You downloaded 17 GB and it runs on a 24 GB MacBook. Something was sacrificed to make that possible.

That something is **numerical precision**. The process of reducing it is called quantization.

Understanding quantization is not optional for anyone deploying AI. It determines model quality, hardware requirements, and ultimately whether your architecture is feasible.

---

## What Precision Means

Every weight in a neural network is a number — specifically a floating-point number. Floating-point numbers trade storage size for precision:

| Format | Bits | Range | Precision | Size per weight |
|--------|------|-------|-----------|----------------|
| FP32 | 32 | ±3.4 × 10³⁸ | ~7 decimal digits | 4 bytes |
| FP16 | 16 | ±65,504 | ~3 decimal digits | 2 bytes |
| INT8 | 8 | -128 to 127 | integer only | 1 byte |
| INT4 | 4 | -8 to 7 | integer only | 0.5 bytes |

Full precision (FP32) is what the model uses during training — every gradient update needs fine-grained precision or training diverges. But at inference time, that level of precision is largely unnecessary.

---

## The Naive Assumption That Fails

"Reducing precision must degrade quality proportionally."

If this were true, a 4-bit model would be roughly 8x worse than a 32-bit model. In practice, the degradation is far smaller — often imperceptible for most tasks. Here is why.

Neural networks are trained to be robust to small perturbations. The weights that matter most for a given prediction are a small fraction of the total. Rounding most weights slightly does not change the output meaningfully. Only the rare, highly sensitive weights cause noticeable degradation when rounded — and modern quantization techniques identify and protect those weights.

---

## How Quantization Works

The core idea: map a range of floating-point values to a smaller set of integers, then store a scaling factor to reverse the mapping at inference time.

**Example with INT8:**

Suppose a layer's weights range from -2.4 to 3.1.

1. Find the range: [-2.4, 3.1], span = 5.5
2. Map to INT8 range [-128, 127]: scale = 5.5 / 255 ≈ 0.0216
3. Store each weight as an integer: -2.4 → -111, 3.1 → 143
4. Store the scale factor once per layer

At inference, multiply integer weight by scale factor to recover the approximate original value. The approximation introduces a tiny error — that is the quality cost.

**INT4 does the same thing with a coarser grid** — 16 possible values instead of 256. More compression, more approximation error.

---

## Quantization Schemes You Will Encounter

### Q4_K_M, Q8_0, Q5_K_S — What These Mean in GGUF

GGUF files use a naming convention that tells you exactly what quantization was applied:

| Code | Bits | Method | Quality vs Size |
|------|------|--------|----------------|
| Q4_0 | 4-bit | Basic INT4 | Smallest, most degradation |
| Q4_K_M | 4-bit | K-quant, medium | Better quality than Q4_0, same size |
| Q5_K_M | 5-bit | K-quant, medium | Good balance |
| Q8_0 | 8-bit | Basic INT8 | Near-lossless, 2x size of Q4 |
| F16 | 16-bit | Half precision | Minimal loss, large |
| F32 | 32-bit | Full precision | Training quality, impractical locally |

**K-quants** (the K_ variants) are smarter: they identify which weights are most sensitive and give them more bits, while compressing less sensitive weights more aggressively. This is why Q4_K_M outperforms Q4_0 at the same file size.

### What Ollama Uses by Default

When you ran `ollama pull gemma4:26b`, Ollama selected a quantization level appropriate for your hardware. You can check the exact variant with:

```bash
ollama show gemma4:26b
```

The `OLLAMA_KV_CACHE_TYPE="q8_0"` flag you set when starting the server applies quantization to the **KV cache** (the memory used during inference for attention) — separate from the model weights themselves.

---

## The Quality vs Size Tradeoff in Practice

Here is what degradation actually looks like across quantization levels, using a reasoning benchmark as reference:

| Quantization | Relative Quality | RAM (26B model) | Notes |
|-------------|-----------------|-----------------|-------|
| FP32 | 100% (baseline) | ~104 GB | Impractical locally |
| FP16 | ~99.5% | ~52 GB | Still large |
| Q8_0 | ~99% | ~27 GB | Near-lossless |
| Q5_K_M | ~98% | ~18 GB | Recommended for quality |
| Q4_K_M | ~96–97% | ~14 GB | Default sweet spot |
| Q4_0 | ~94–95% | ~14 GB | Avoid if Q4_K_M available |

For most production tasks — summarization, Q&A, code generation, classification — the difference between Q8 and Q4_K_M is invisible to end users. The difference becomes noticeable on tasks that require precise arithmetic, complex multi-step reasoning, or rare factual recall.

---

## Where Quality Actually Degrades

Quantization hurts most in these scenarios:

**1. Precise arithmetic**
"What is 847 × 293?" — small weights that encode numerical reasoning get rounded, introducing errors.

**2. Rare knowledge**
Facts that appear infrequently in training data are encoded in small weight activations — more susceptible to rounding.

**3. Long chain-of-thought reasoning**
Errors compound across many reasoning steps. A 1% degradation per step becomes significant over 50 steps.

**4. Code with subtle bugs**
Off-by-one errors, edge cases, type handling — small precision differences in the weights that encode syntax rules can flip a correct solution to a wrong one.

For these tasks, Q8 or F16 is worth the extra RAM cost. For everything else, Q4_K_M is the right default.

---

## Quantization vs the E2B Model

This is where the Gemma 4 E2B story connects back.

E2B at 2.54 GB achieves its size through **two compounding factors**:
1. Fewer parameters (2.3B vs 26B) — roughly 11x reduction
2. 4-bit quantization applied on top — roughly 8x reduction from FP32

Combined: a model that would be ~9 GB at FP32 becomes 2.54 GB. That is how a capable multimodal model fits in 1.5 GB of RAM on a phone.

The 26B model applies the same quantization but starts from a much larger base — hence 17 GB rather than 2.54 GB.

---

## Enterprise Implications

When a client asks "can we run this model on our hardware?", quantization is half the answer.

**Questions you can now answer:**

- **"We only have 16 GB RAM on the target server."**
  A Q4_K_M of Gemma 4 26B needs ~14 GB — feasible, but tight. Q8 is not an option. Consider E4B instead.

- **"How much quality are we giving up by running locally?"**
  With Q4_K_M: 3–4% on benchmarks. For your use case (document summarization, Q&A): likely imperceptible.

- **"Can we run a model that's better than GPT-4?"**
  Quality is not just a function of quantization — it is model capability × quantization level. A poorly quantized large model can still outperform a well-quantized small model.

- **"How do we choose between Q4 and Q8?"**
  Run your specific task as a benchmark. If outputs are indistinguishable to your domain experts, ship Q4. If not, pay the RAM cost for Q8.

---

## Key Terms

| Term | Definition |
|------|-----------|
| FP32 | 32-bit floating point — full training precision |
| FP16 | 16-bit floating point — half precision |
| INT8 / Q8 | 8-bit integer quantization |
| INT4 / Q4 | 4-bit integer quantization |
| K-quants | Adaptive quantization that protects sensitive weights |
| Scale factor | The multiplier stored alongside quantized weights to recover approximate original values |
| KV cache | Memory used during inference to store attention context — separate from model weights |

---


## Full Code

```python title="02_benchmark_throughput.py"
--8<-- "01-installation/code/02_benchmark_throughput.py"
```

## Next

**Ollama Architecture** — how the inference server manages model loading, GPU scheduling, and the REST API that your application talks to.
