"""
Audit Logger — Phase 7, Experiment 2

What this builds:
  A SQLite-backed audit logger that records every inference request
  and response with full attribution. Demonstrates the compliance
  logging layer required for regulated enterprise deployments.

What is logged per request:
  - request_id  : UUID (links request to response)
  - timestamp   : UTC ISO-8601
  - user_id     : who made the request
  - session_id  : groups requests within a conversation
  - model       : which model was used
  - prompt      : full input text
  - response    : full output text
  - latency_ms  : end-to-end response time
  - token_count : estimated (len/4 chars per token)
  - status      : success / error
  - error_msg   : if status == error

Why this matters:
  Without an audit log, "the AI said so" is not a compliance answer.
  With this log, every response is attributable, timestamped, and
  reproducible for regulatory review.

Run standalone:
  python 02_audit_logger.py

This creates /tmp/audit.db and runs 3 demo inferences, then shows
the audit trail and a user activity report.
"""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

DB_PATH      = Path("/tmp/audit.db")
OLLAMA_URL   = "http://localhost:11434/api/chat"
MODEL        = "gemma4:26b"


# ------------------------------------------------------------------
# SCHEMA
# ------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS inference_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id   TEXT    NOT NULL,
    timestamp    TEXT    NOT NULL,
    user_id      TEXT    NOT NULL,
    session_id   TEXT    NOT NULL,
    model        TEXT    NOT NULL,
    prompt       TEXT    NOT NULL,
    response     TEXT,
    latency_ms   REAL,
    prompt_chars INTEGER,
    resp_chars   INTEGER,
    status       TEXT    NOT NULL DEFAULT 'success',
    error_msg    TEXT
);

CREATE INDEX IF NOT EXISTS idx_user_id   ON inference_log(user_id);
CREATE INDEX IF NOT EXISTS idx_timestamp ON inference_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_session   ON inference_log(session_id);
"""


# ------------------------------------------------------------------
# DATABASE CONTEXT
# ------------------------------------------------------------------

@contextmanager
def get_db(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------
# AUDIT LOGGER
# ------------------------------------------------------------------

@dataclass
class AuditLogger:
    db_path: Path = DB_PATH

    def log_request(
        self,
        user_id: str,
        session_id: str,
        model: str,
        prompt: str,
    ) -> str:
        request_id = str(uuid.uuid4())
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with get_db(self.db_path) as conn:
            conn.execute(
                """INSERT INTO inference_log
                   (request_id, timestamp, user_id, session_id, model,
                    prompt, prompt_chars, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (request_id, ts, user_id, session_id, model, prompt, len(prompt)),
            )
        return request_id

    def log_response(
        self,
        request_id: str,
        response: str,
        latency_ms: float,
        status: str = "success",
        error_msg: Optional[str] = None,
    ):
        with get_db(self.db_path) as conn:
            conn.execute(
                """UPDATE inference_log
                   SET response=?, latency_ms=?, resp_chars=?, status=?, error_msg=?
                   WHERE request_id=?""",
                (response, latency_ms, len(response) if response else 0,
                 status, error_msg, request_id),
            )

    def get_session(self, session_id: str) -> list[dict]:
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                """SELECT request_id, timestamp, user_id, model,
                          prompt, response, latency_ms, status
                   FROM inference_log
                   WHERE session_id = ?
                   ORDER BY id ASC""",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def user_report(self, user_id: str) -> dict:
        with get_db(self.db_path) as conn:
            stats = conn.execute(
                """SELECT
                       COUNT(*)                          AS total_requests,
                       SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS successes,
                       SUM(CASE WHEN status='error'   THEN 1 ELSE 0 END) AS errors,
                       ROUND(AVG(latency_ms), 1)        AS avg_latency_ms,
                       ROUND(MAX(latency_ms), 1)        AS max_latency_ms,
                       SUM(prompt_chars)                AS total_prompt_chars,
                       SUM(resp_chars)                  AS total_resp_chars,
                       MIN(timestamp)                   AS first_request,
                       MAX(timestamp)                   AS last_request
                   FROM inference_log
                   WHERE user_id = ?""",
                (user_id,),
            ).fetchone()
        return dict(stats)

    def export_compliance_json(self, output_path: Path, user_id: Optional[str] = None):
        query = "SELECT * FROM inference_log"
        params: tuple = ()
        if user_id:
            query += " WHERE user_id = ?"
            params = (user_id,)
        query += " ORDER BY id ASC"
        with get_db(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
        records = [dict(r) for r in rows]
        with open(output_path, "w") as f:
            json.dump(records, f, indent=2)
        return len(records)


# ------------------------------------------------------------------
# INSTRUMENTED OLLAMA CALL
# ------------------------------------------------------------------

def infer_with_audit(
    logger: AuditLogger,
    user_id: str,
    session_id: str,
    prompt: str,
    model: str = MODEL,
    max_tokens: int = 300,
) -> str:
    request_id = logger.log_request(user_id, session_id, model, prompt)
    start_ms   = time.perf_counter() * 1000
    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"temperature": 0.0, "num_predict": max_tokens, "num_ctx": 4096},
        }
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        r.raise_for_status()
        response_text = r.json()["message"]["content"].strip()
        latency_ms    = round(time.perf_counter() * 1000 - start_ms, 1)
        logger.log_response(request_id, response_text, latency_ms)
        return response_text
    except Exception as exc:
        latency_ms = round(time.perf_counter() * 1000 - start_ms, 1)
        logger.log_response(request_id, "", latency_ms,
                            status="error", error_msg=str(exc))
        raise


# ------------------------------------------------------------------
# DEMO
# ------------------------------------------------------------------

def _print_audit_trail(entries: list[dict]):
    for entry in entries:
        print(f"\n  Request ID : {entry['request_id'][:8]}...")
        print(f"  Time       : {entry['timestamp']}")
        print(f"  User       : {entry['user_id']}")
        print(f"  Model      : {entry['model']}")
        print(f"  Status     : {entry['status']}")
        print(f"  Latency    : {entry['latency_ms']}ms")
        print(f"  Prompt     : {entry['prompt'][:80]}...")
        if entry["response"]:
            print(f"  Response   : {entry['response'][:80]}...")


def _print_user_report(report: dict, user_id: str):
    print(f"\n  User             : {user_id}")
    print(f"  Total requests   : {report['total_requests']}")
    print(f"  Successes        : {report['successes']}")
    print(f"  Errors           : {report['errors']}")
    print(f"  Avg latency      : {report['avg_latency_ms']}ms")
    print(f"  Max latency      : {report['max_latency_ms']}ms")
    print(f"  Chars sent       : {report['total_prompt_chars']}")
    print(f"  Chars received   : {report['total_resp_chars']}")
    print(f"  First request    : {report['first_request']}")
    print(f"  Last request     : {report['last_request']}")


if __name__ == "__main__":
    logger = AuditLogger(DB_PATH)
    session_id = str(uuid.uuid4())[:8]

    demo_requests = [
        {
            "user_id": "engineer_alice",
            "prompt": (
                "The payments API is returning HTTP 503 since 14:23 UTC. "
                "GET requests work. Database health checks pass. "
                "3,200 transactions per minute are failing. "
                "What is the most likely root cause in one sentence?"
            ),
        },
        {
            "user_id": "engineer_alice",
            "prompt": (
                "The fix requires creating a PostgreSQL index on a 47-million-row table "
                "with 200 writes per second. What SQL command should I use and why?"
            ),
        },
        {
            "user_id": "engineer_bob",
            "prompt": (
                "Should I escalate a P2 storage incident where the RAID-6 replacement drive "
                "has a 4-6 hour procurement lead time? Answer in two sentences."
            ),
        },
    ]

    print("Audit Logger Demo")
    print(f"Database   : {DB_PATH}")
    print(f"Session ID : {session_id}")
    print(f"Requests   : {len(demo_requests)}\n")

    for i, req in enumerate(demo_requests, 1):
        print(f"[{i}/{len(demo_requests)}] user={req['user_id']}")
        try:
            response = infer_with_audit(
                logger,
                user_id=req["user_id"],
                session_id=session_id,
                prompt=req["prompt"],
            )
            print(f"  Response: {response[:100]}...")
        except Exception as exc:
            print(f"  Error: {exc}")

    print(f"\n{'=' * 60}")
    print("  Audit Trail — Session", session_id)
    print(f"{'=' * 60}")
    entries = logger.get_session(session_id)
    _print_audit_trail(entries)

    print(f"\n{'=' * 60}")
    print("  User Activity Report — engineer_alice")
    print(f"{'=' * 60}")
    report = logger.user_report("engineer_alice")
    _print_user_report(report, "engineer_alice")

    export_path = Path("/tmp/audit_export.json")
    count = logger.export_compliance_json(export_path)
    print(f"\n  Compliance export: {count} records → {export_path}")
