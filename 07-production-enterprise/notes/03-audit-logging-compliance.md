# Audit Logging for AI Compliance

## Why AI Systems Need Audit Logs

A conventional software system that gives a wrong answer can be debugged: you find the code path, trace the inputs, reproduce the bug. An AI system that gives a wrong answer is harder to audit because the "code path" is 26 billion parameters evaluated stochastically.

This creates a compliance problem. If an engineer acts on an AI-generated recommendation that turns out to be wrong, and the incident review board asks "what exactly did the AI say?" — you need to be able to answer with precision. "The AI said something about the database" is not an audit trail. "At 09:21 UTC on 21 April 2026, user engineer_alice submitted prompt X, gemma4:26b returned response Y, latency 12,830ms" is.

Regulated industries (banking, healthcare, insurance, defence) require this level of attribution as a minimum for any AI-assisted decision.

---

## What Must Be Logged

Every inference event must capture six things to be auditable:

| Field | Why it matters |
|-------|---------------|
| `request_id` | Links the request record to the response record — essential if they are stored separately or in different systems |
| `timestamp` | UTC, not local time. Enables correlation with incident timelines, which are always recorded in UTC |
| `user_id` | Who submitted the request. Without this, you cannot do per-user activity reporting or identify misuse |
| `session_id` | Groups requests within a conversation. An engineer may send 10 requests to diagnose an incident — the session ID lets you reconstruct the reasoning chain |
| `model` | Which model version was used. Models are updated. A response from `gemma4:26b` in April 2026 may differ from the same prompt in June 2026 if the model changes |
| `prompt` + `response` | The exact text sent and received. Summaries are not sufficient for compliance — the full text must be stored |

Additional useful fields: `latency_ms` (performance baseline), `prompt_chars` / `resp_chars` (token cost proxy), `status` (success or error), `error_msg`.

---

## Schema Design

The audit log uses a single SQLite table. SQLite is the right choice for a single-node deployment: it is file-based, requires no server process, is readable by standard tooling (`sqlite3`, DBeaver, any SQL client), and its WAL mode supports concurrent reads during writes.

```sql
CREATE TABLE inference_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id   TEXT    NOT NULL,   -- UUID linking request → response
    timestamp    TEXT    NOT NULL,   -- UTC ISO-8601
    user_id      TEXT    NOT NULL,
    session_id   TEXT    NOT NULL,
    model        TEXT    NOT NULL,
    prompt       TEXT    NOT NULL,
    response     TEXT,               -- NULL until response arrives
    latency_ms   REAL,
    prompt_chars INTEGER,
    resp_chars   INTEGER,
    status       TEXT    NOT NULL DEFAULT 'success',
    error_msg    TEXT
);
```

Indexes on `user_id`, `timestamp`, and `session_id` enable the three most common audit queries:
- "Show me all requests from user X" → `user_id` index
- "Show me all requests between time A and time B" → `timestamp` index
- "Reconstruct this conversation" → `session_id` index

---

## Two-Phase Logging

The logger uses a two-phase write: the request is logged before the model is called, and the response is written back once it arrives. This is intentional.

If the model call fails (timeout, Ollama crash, network error), the request record still exists in the database with `status='pending'`. During an incident review, a pending record is evidence that the request was submitted but no response was received — which is different from no record at all.

```python
# Phase 1 — before calling Ollama
request_id = logger.log_request(user_id, session_id, model, prompt)

# Phase 2 — after response (or on error)
logger.log_response(request_id, response, latency_ms, status="success")
# or
logger.log_response(request_id, "", latency_ms, status="error", error_msg=str(exc))
```

This pattern is sometimes called write-ahead logging in database systems. The principle is the same: record intent before action.

---

## What the Code Does

`02_audit_logger.py` runs three demo inferences across two users and demonstrates the audit trail.

### Demo Requests

**Request 1 — engineer_alice, root cause question:**
```
The payments API is returning HTTP 503 since 14:23 UTC. GET requests work.
Database health checks pass. 3,200 transactions per minute are failing.
What is the most likely root cause in one sentence?
```

**Request 2 — engineer_alice, resolution question:**
```
The fix requires creating a PostgreSQL index on a 47-million-row table
with 200 writes per second. What SQL command should I use and why?
```

**Request 3 — engineer_bob, escalation question:**
```
Should I escalate a P2 storage incident where the RAID-6 replacement drive
has a 4-6 hour procurement lead time? Answer in two sentences.
```

---

## Experiment Results (M4 24 GB, gemma4:26b)

```
Audit Logger Demo
Database   : /tmp/audit.db
Session ID : 4a617c9c
```

### Audit Trail

| Field | Request 1 | Request 2 | Request 3 |
|-------|-----------|-----------|-----------|
| User | engineer_alice | engineer_alice | engineer_bob |
| Model | gemma4:26b | gemma4:26b | gemma4:26b |
| Latency | 19,195ms | 12,830ms | 3,249ms |
| Status | success | success | success |

**Request 1 response (truncated):**
> The most likely root cause is a resource exhaustion or configuration issue (such as a connection pool exhaustion)...

**Request 2 response (truncated):**
> To perform this operation without locking your table and causing an outage, you must use the `CONCURRENTLY` option...

**Request 3 response (truncated):**
> Yes, you should escalate the incident because a 4-6 hour delay in replacing a drive in a degraded RAID array...

All three responses are technically correct and consistent with Phase 6 benchmark findings.

### User Activity Report — engineer_alice

```
Total requests   : 2
Successes        : 2
Errors           : 0
Avg latency      : 16,013ms
Max latency      : 19,195ms
Chars sent       : 335
Chars received   : 1,464
First request    : 2026-04-21T09:20:58Z
Last request     : 2026-04-21T09:21:17Z
```

**Latency observation:** Request 1 (19,195ms) is slower than Request 2 (12,830ms) despite being a simpler prompt. This is consistent with Phase 1 findings: the first request after a model load is slower due to KV cache warmup. By Request 2, the model is warm.

---

## Compliance Export

The logger can export the full audit trail as a JSON file for regulatory submission:

```python
count = logger.export_compliance_json(Path("/tmp/audit_export.json"))
# → 3 records → /tmp/audit_export.json
```

The export format is a flat list of records, one per inference event, in the same schema as the database. This can be ingested directly into a SIEM (Security Information and Event Management) system or submitted to a compliance auditor.

---

## What to Log vs What Not to Log

A common mistake is logging everything indiscriminately and discovering that the logs themselves become a compliance liability.

**Log:** the full prompt and response. This is required for auditability. If the prompt contains PII because the user included it, that PII is now in your log. Manage this with access controls on the log database, not by redacting the log.

**Do not log:** authentication tokens, API keys, or secrets that may appear in configuration. The audit logger receives the prompt after the API layer strips headers — it should never see credentials.

**Retention policy:** define a retention period before deploying. Logs kept indefinitely become a data minimisation liability. Logs deleted too quickly cannot satisfy a compliance audit. 90 days is a common minimum for ITSM tooling.

---

## Key Concepts Demonstrated

| Concept | What the experiment shows |
|---------|--------------------------|
| Two-phase write | Request logged before model call. Pending records are evidence of attempted but unanswered requests — this matters for incident reconstruction. |
| UUID request linking | `request_id` connects the pre-call record to the post-call record. This pattern works across distributed systems where request and response may be logged by different services. |
| Per-user activity report | The user report query aggregates latency, volume, and error rates per user. This is the data that feeds a per-team usage dashboard or a billing system. |
| Session reconstruction | `get_session()` returns all requests for a session in order. A compliance auditor can follow the reasoning chain that led to an engineering decision. |

---

## Next

`03_guardrails.py` — input and output filters that sit between the client and Ollama. Blocks prompt injection, enforces domain scope, and detects PII before and after the model call.
