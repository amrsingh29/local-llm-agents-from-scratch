"""
Concurrent Inference Server — Phase 7, Experiment 1

What this builds:
  A FastAPI wrapper around Ollama that adds:
  - Semaphore-based concurrency control (max N simultaneous requests)
  - Bounded request queue (reject when queue is full — explicit 503)
  - Per-user rate limiting (token bucket, X requests per minute)
  - Basic request/response logging to stdout
  - /metrics endpoint showing queue depth and active request count

Why this matters:
  Raw Ollama accepts all requests and serialises them silently.
  Under load, clients time out without knowing why.
  This server makes queuing behaviour explicit and controllable.

Run:
  pip install fastapi uvicorn
  uvicorn 01_concurrent_inference_server:app --host 0.0.0.0 --port 8080

Test concurrent load:
  python 01_concurrent_inference_server.py --load-test

Endpoints:
  POST /infer          — submit an inference request
  GET  /metrics        — current queue depth, active count, rate limit state
  GET  /health         — liveness check
"""

import argparse
import asyncio
import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

OLLAMA_URL       = "http://localhost:11434/api/chat"
MODEL            = "gemma4:26b"
MAX_CONCURRENT   = 2          # simultaneous Ollama calls
MAX_QUEUE_DEPTH  = 8          # requests waiting beyond MAX_CONCURRENT
RATE_LIMIT_RPM   = 10         # requests per user per minute
RATE_LIMIT_BURST = 3          # burst allowance above steady rate


# ------------------------------------------------------------------
# RATE LIMITER — token bucket per user
# ------------------------------------------------------------------

@dataclass
class TokenBucket:
    capacity: int
    refill_rate: float          # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)
    lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self):
        self.tokens = float(self.capacity)
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False


class RateLimiter:
    def __init__(self, rpm: int, burst: int):
        self._buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(capacity=burst, refill_rate=rpm / 60.0)
        )
        self._lock = threading.Lock()

    def allow(self, user_id: str) -> bool:
        with self._lock:
            bucket = self._buckets[user_id]
        return bucket.consume()


# ------------------------------------------------------------------
# QUEUE MANAGER
# ------------------------------------------------------------------

class QueueManager:
    def __init__(self, max_concurrent: int, max_queue: int):
        self._semaphore   = asyncio.Semaphore(max_concurrent)
        self._max_queue   = max_queue
        self._queue_depth = 0
        self._active      = 0
        self._lock        = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            if self._queue_depth >= self._max_queue:
                return False
            self._queue_depth += 1
        await self._semaphore.acquire()
        async with self._lock:
            self._queue_depth -= 1
            self._active += 1
        return True

    async def release(self):
        async with self._lock:
            self._active -= 1
        self._semaphore.release()

    def snapshot(self) -> dict:
        return {
            "active":      self._active,
            "queued":      self._queue_depth,
            "max_concurrent": self._semaphore._value + self._active,
            "max_queue":   self._max_queue,
        }


# ------------------------------------------------------------------
# OLLAMA CALL (blocking — run in thread pool to avoid blocking event loop)
# ------------------------------------------------------------------

def _call_ollama_sync(model: str, prompt: str, max_tokens: int) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": max_tokens, "num_ctx": 4096},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


# ------------------------------------------------------------------
# REQUEST / RESPONSE MODELS
# ------------------------------------------------------------------

class InferRequest(BaseModel):
    prompt: str
    user_id: str = "anonymous"
    max_tokens: int = 400
    model: Optional[str] = None


class InferResponse(BaseModel):
    response: str
    user_id: str
    model: str
    latency_ms: float
    queue_snapshot: dict


# ------------------------------------------------------------------
# APP
# ------------------------------------------------------------------

app          = FastAPI(title="Local Inference Server", version="1.0")
rate_limiter = RateLimiter(rpm=RATE_LIMIT_RPM, burst=RATE_LIMIT_BURST)
queue_mgr    = QueueManager(max_concurrent=MAX_CONCURRENT, max_queue=MAX_QUEUE_DEPTH)

# recent request log (in-memory, last 50)
_request_log: deque = deque(maxlen=50)


@app.post("/infer", response_model=InferResponse)
async def infer(body: InferRequest):
    user_id = body.user_id
    model   = body.model or MODEL

    # rate limit check
    if not rate_limiter.allow(user_id):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded for user '{user_id}'. Max {RATE_LIMIT_RPM} req/min.",
        )

    # queue check
    admitted = await queue_mgr.acquire()
    if not admitted:
        raise HTTPException(
            status_code=503,
            detail=f"Server at capacity. Queue depth {MAX_QUEUE_DEPTH} reached. Retry shortly.",
        )

    start_ms = time.perf_counter() * 1000
    try:
        response_text = await asyncio.get_event_loop().run_in_executor(
            None, _call_ollama_sync, model, body.prompt, body.max_tokens
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ollama error: {exc}") from exc
    finally:
        await queue_mgr.release()

    latency_ms = round(time.perf_counter() * 1000 - start_ms, 1)
    snapshot   = queue_mgr.snapshot()

    log_entry = {
        "ts":         time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "user_id":    user_id,
        "model":      model,
        "prompt_len": len(body.prompt),
        "resp_len":   len(response_text),
        "latency_ms": latency_ms,
    }
    _request_log.appendleft(log_entry)
    print(f"[{log_entry['ts']}] user={user_id} latency={latency_ms}ms active={snapshot['active']}")

    return InferResponse(
        response=response_text,
        user_id=user_id,
        model=model,
        latency_ms=latency_ms,
        queue_snapshot=snapshot,
    )


@app.get("/metrics")
async def metrics():
    return JSONResponse({
        "queue":        queue_mgr.snapshot(),
        "rate_limit":   {"rpm": RATE_LIMIT_RPM, "burst": RATE_LIMIT_BURST},
        "recent_reqs":  list(_request_log)[:10],
    })


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL}


# ------------------------------------------------------------------
# LOAD TEST — runs without the server, directly calls Ollama
# ------------------------------------------------------------------

def _load_test():
    """
    Simulate 5 concurrent users hitting the server.
    Shows how latency scales with concurrency.
    Run after starting the server: python script.py --load-test
    """
    import concurrent.futures

    SERVER_URL = "http://localhost:8080/infer"
    PROMPT     = "In one sentence, what is a connection pool?"
    USERS      = 5

    def send_request(user_id: str) -> dict:
        t0 = time.perf_counter()
        try:
            r = requests.post(SERVER_URL, json={
                "prompt":     PROMPT,
                "user_id":    user_id,
                "max_tokens": 60,
            }, timeout=180)
            latency = round((time.perf_counter() - t0) * 1000)
            if r.status_code == 200:
                data = r.json()
                return {"user": user_id, "status": 200, "latency_ms": latency,
                        "response": data["response"][:80]}
            return {"user": user_id, "status": r.status_code,
                    "latency_ms": latency, "error": r.json().get("detail", "")}
        except Exception as exc:
            return {"user": user_id, "status": -1,
                    "latency_ms": round((time.perf_counter() - t0) * 1000),
                    "error": str(exc)}

    print(f"\nLoad test — {USERS} concurrent users, same prompt\n")
    print(f"Prompt: \"{PROMPT}\"\n")

    with concurrent.futures.ThreadPoolExecutor(max_workers=USERS) as pool:
        futures = [pool.submit(send_request, f"user_{i+1}") for i in range(USERS)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    results.sort(key=lambda x: x["user"])
    print(f"{'User':<10} {'Status':>6}  {'Latency':>9}  Response / Error")
    print("─" * 70)
    for r in results:
        status = r["status"]
        lat    = f"{r['latency_ms']}ms"
        detail = r.get("response", r.get("error", ""))
        print(f"{r['user']:<10} {status:>6}  {lat:>9}  {detail}")

    successful = [r for r in results if r["status"] == 200]
    if successful:
        avg_lat = round(sum(r["latency_ms"] for r in successful) / len(successful))
        max_lat = max(r["latency_ms"] for r in successful)
        print(f"\nSuccessful: {len(successful)}/{USERS}")
        print(f"Avg latency: {avg_lat}ms  |  Max latency: {max_lat}ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--load-test", action="store_true",
                        help="Run load test against the running server")
    args = parser.parse_args()

    if args.load_test:
        _load_test()
    else:
        print(f"Starting inference server")
        print(f"  Model          : {MODEL}")
        print(f"  Max concurrent : {MAX_CONCURRENT}")
        print(f"  Queue depth    : {MAX_QUEUE_DEPTH}")
        print(f"  Rate limit     : {RATE_LIMIT_RPM} req/min per user (burst {RATE_LIMIT_BURST})")
        print(f"  Endpoints      : POST /infer  GET /metrics  GET /health\n")
        uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
