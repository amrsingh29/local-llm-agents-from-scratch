# Concurrency and Throughput

## The Problem with Naive Concurrency

Start Ollama and send two requests at the same time. The second request does not fail — it queues silently inside Ollama and waits for the first to complete. From the client's perspective, the request takes twice as long with no explanation.

At three concurrent users, it takes three times as long. At ten, ten times. There is no timeout, no feedback, no way to tell a client "you are number 7 in the queue." Requests pile up until clients time out, and the system appears to have crashed.

This is the naive concurrency model. It works for a single developer running experiments. It fails the moment two people use the system at the same time.

---

## What Production Concurrency Requires

A production inference server needs four things that Ollama does not provide out of the box:

**1. Explicit queue management** — clients should know immediately whether their request will be served or rejected. A bounded queue with a clear rejection message is more honest than an unbounded implicit queue that causes silent timeouts.

**2. Concurrency control** — the server should control how many inference requests hit the model simultaneously. On a single machine, increasing beyond one simultaneous request rarely increases total throughput — it only increases latency variance and KV cache memory pressure.

**3. Per-user rate limiting** — without rate limiting, a single user running a script can consume all available inference capacity, starving other users. The rate limiter ensures that no single user can monopolise the server.

**4. Observability** — operators need to see queue depth and active request count in real time to know when the system is under pressure.

---

## The Architecture

```
Client request
      ↓
  Rate limiter            ← rejects immediately if user exceeds RPM
      ↓
  Queue manager           ← rejects immediately if queue is full (503)
      ↓                   ← queues if below MAX_CONCURRENT (waits)
  Semaphore (N=2)         ← only N requests reach Ollama simultaneously
      ↓
  Ollama (gemma4:26b)
      ↓
  Response → Client
```

The semaphore is the key mechanism. It allows at most `MAX_CONCURRENT` requests to reach Ollama at the same time. Additional requests wait in the asyncio queue. Requests beyond `MAX_QUEUE_DEPTH` are rejected immediately with a 503 before they consume any resources.

---

## What the Code Does

`01_concurrent_inference_server.py` wraps Ollama in a FastAPI server and adds three components:

### Token Bucket Rate Limiter

```
User sends request → rate limiter checks the user's token bucket
   → bucket has tokens → consume one, allow request
   → bucket is empty   → return 429 Too Many Requests immediately
```

Each user gets a `TokenBucket` with:
- `capacity` = burst allowance (default 3) — how many requests can be sent in a short burst
- `refill_rate` = `rpm / 60` — tokens refill at this rate per second

A user configured at 10 RPM gets 0.167 tokens/second. They can burst up to 3 requests immediately, then are throttled to one request every 6 seconds.

### Semaphore + Queue Manager

`asyncio.Semaphore(MAX_CONCURRENT)` ensures at most `MAX_CONCURRENT` coroutines are blocked on the Ollama call at once. The `QueueManager` wraps the semaphore with:
- A count of how many requests are waiting (queue depth)
- A rejection gate when `queue_depth >= MAX_QUEUE_DEPTH`
- An active count for the `/metrics` endpoint

### Ollama Call in Thread Pool

Ollama calls are blocking HTTP requests. Running them directly in the FastAPI event loop would block the entire server. The server runs each Ollama call in `asyncio.get_event_loop().run_in_executor(None, ...)` — this dispatches the blocking call to the default thread pool, keeping the event loop responsive for health checks and metrics queries while inference is running.

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/infer` | POST | Submit an inference request |
| `/metrics` | GET | Current queue depth, active requests, rate limit config |
| `/health` | GET | Liveness check |

---

## Configuration

```python
MAX_CONCURRENT  = 2    # simultaneous Ollama calls
MAX_QUEUE_DEPTH = 8    # requests waiting beyond MAX_CONCURRENT
RATE_LIMIT_RPM  = 10   # requests per user per minute
RATE_LIMIT_BURST = 3   # burst allowance
```

On M4 24 GB with `gemma4:26b`, `MAX_CONCURRENT = 2` is the right setting. Running two simultaneous requests does not double throughput — it roughly halves latency variance for the waiting request while keeping memory pressure manageable. Setting `MAX_CONCURRENT > 2` on this hardware increases KV cache pressure and typically reduces total throughput.

---

## Throughput Under Load — Expected Behaviour

Under concurrent load with `MAX_CONCURRENT=2`:

| Concurrent users | What happens |
|-----------------|--------------|
| 1 | Full throughput — no queue wait. |
| 2 | Both run simultaneously — P50 latency approximately 1.5–2× single-request. |
| 3 | Third queues — waits for one of the first two to complete. |
| 5 | All 5 admitted. Three queue. P95 latency approximately 5× single-request. |
| 9+ | Beyond `MAX_QUEUE_DEPTH=8`, requests 9+ receive 503 immediately. |

**Measured results (M4 24 GB, gemma4:26b, 5 concurrent users):**

Prompt: "In one sentence, what is a connection pool?"

| User | Client latency | Ollama inference time | Queue wait |
|------|---------------|-----------------------|------------|
| user_4 | 21,357ms | 21,253ms | ~0ms (slot 1) |
| user_3 | 27,478ms | 27,390ms | ~0ms (slot 2) |
| user_5 | 29,739ms | 8,414ms | ~21s queued |
| user_2 | 32,048ms | 4,557ms | ~27s queued |
| user_1 | 33,487ms | 3,746ms | ~30s queued |
| **Avg** | **28,822ms** | | |

user_4 and user_3 entered immediately (no wait — they claimed the two `MAX_CONCURRENT` slots). user_5, user_2, and user_1 queued. Their Ollama inference was fast (3–8s each) but they waited 20–30 seconds for a slot to open. All five received the same correct response.

This is the queuing effect measured directly: response quality is identical regardless of queue position. Wait time is entirely determined by position in the queue and the inference time of the requests ahead.

This is the honest concurrency story for a single-node local inference server. It is not comparable to a cloud API running hundreds of instances in parallel. The value is privacy, cost, and control.

---

## How to Run

```bash
# Create venv and install dependencies (from project root)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Or if venv already exists:

# Terminal 1 — start the server
python 07-production-enterprise/code/01_concurrent_inference_server.py

# Terminal 2 — single request test
curl -s -X POST http://localhost:8080/infer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is a connection pool? One sentence.", "user_id": "alice"}' | python3 -m json.tool

# Terminal 2 — check metrics
curl -s http://localhost:8080/metrics | python3 -m json.tool

# Terminal 2 — load test (5 concurrent users)
python 07-production-enterprise/code/01_concurrent_inference_server.py --load-test
```

---

## Key Concepts Demonstrated

| Concept | Implementation |
|---------|---------------|
| Semaphore | Caps concurrent Ollama calls. Standard concurrency primitive — one Semaphore.acquire() per active inference, release() on completion. |
| Bounded queue | `MAX_QUEUE_DEPTH` hard limit. Requests beyond the limit receive 503 immediately, not a timeout. |
| Token bucket | Per-user rate limiter. Tokens refill at a steady rate; burst capacity is consumed first. This allows short bursts without permanently denying the user. |
| Thread pool offload | Blocking Ollama HTTP calls run in `run_in_executor`. The FastAPI event loop stays responsive for health checks while inference runs. |
| Explicit rejection | 429 (rate limit) and 503 (capacity) are returned immediately. The client knows why it was rejected and when to retry. |

---


## Full Code

```python title="01_concurrent_inference_server.py"
--8<-- "07-production-enterprise/code/01_concurrent_inference_server.py"
```

## Next

`02_audit_logger.py` — adds the compliance layer: every request and response stored to SQLite with full attribution. This is what makes an AI system auditable in a regulated environment.
