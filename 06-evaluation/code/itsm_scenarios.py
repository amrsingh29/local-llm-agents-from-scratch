"""
ITSM Benchmark Scenarios — shared by 03 and 04

12 scenarios across 6 task types (2 per type).
Each scenario has:
  - id, task_type, difficulty, title
  - incident: the situation presented to the model under test
  - reference: the expert answer used by the judge
  - priority: expected P1–P4 (where applicable)
"""

SCENARIOS = [

    # ----------------------------------------------------------------
    # TRIAGE
    # ----------------------------------------------------------------
    {
        "id": "triage_01",
        "task_type": "triage",
        "difficulty": "hard",
        "title": "Payments API complete outage",
        "incident": (
            "The payments API has been returning HTTP 503 for all POST /v1/payments requests "
            "since 14:23 UTC. GET requests return 200. Database health checks pass. "
            "3,200 transactions per minute are failing. No successful payments in the last "
            "26 minutes. Three enterprise clients have called the support line. "
            "Classify this incident: assign priority, category, affected services, "
            "and write a one-sentence impact statement."
        ),
        "reference": (
            "Priority: P1. Category: Application/API. Affected service: Payment API (POST endpoint). "
            "Impact statement: The Payment API is completely unavailable for all write operations, "
            "resulting in 100% transaction failure and active revenue loss affecting enterprise clients. "
            "Justification: complete service outage with direct revenue impact and enterprise client "
            "escalations meets P1 criteria."
        ),
        "expected_priority": "P1",
    },
    {
        "id": "triage_02",
        "task_type": "triage",
        "difficulty": "medium",
        "title": "Dashboard slow load for subset of users",
        "incident": (
            "The analytics dashboard is loading slowly (8–12 seconds instead of the normal 2 seconds) "
            "for approximately 15% of users, specifically those whose accounts were migrated to "
            "the new data tier last week. Other users are unaffected. No errors in the logs — "
            "just slow queries. Users can still access all data. A workaround exists: "
            "refreshing the page twice resolves the issue temporarily. "
            "Classify this incident: assign priority, category, affected services, "
            "and write a one-sentence impact statement."
        ),
        "reference": (
            "Priority: P3. Category: Performance/Application. Affected service: Analytics Dashboard. "
            "Impact statement: A subset of recently migrated users (~15%) are experiencing degraded "
            "dashboard load times; full functionality is available and a workaround exists. "
            "Justification: partial user impact, workaround available, no data loss — meets P3 criteria. "
            "P2 would require >25% impact or no workaround."
        ),
        "expected_priority": "P3",
    },

    # ----------------------------------------------------------------
    # DIAGNOSIS
    # ----------------------------------------------------------------
    {
        "id": "diag_01",
        "task_type": "diagnosis",
        "difficulty": "medium",
        "title": "Web server CPU spike and timeout errors",
        "incident": (
            "All three web servers show CPU utilisation at 98% since 09:47 UTC (40 minutes ago). "
            "Response times increased from 200ms to 8,000ms. No deployments in the last 72 hours. "
            "Memory is normal on all servers. Network I/O is normal. "
            "Error logs show repeated messages: "
            "'HikariCP connection pool timeout — pool size: 10, wait timeout: 30s'. "
            "The database server itself shows normal CPU and memory. "
            "What is the most likely root cause? Provide your next three investigation steps."
        ),
        "reference": (
            "Most likely root cause: database connection pool exhaustion. "
            "The pool (size 10) is fully occupied, likely by slow or blocked queries that are not "
            "releasing connections. Web servers are blocking waiting for connections, causing "
            "thread starvation and CPU saturation from thread management overhead. "
            "Database server health being normal rules out a database crash — the issue is "
            "in the connection layer or query performance. "
            "Next three steps: "
            "1. Run SHOW PROCESSLIST on the database to identify long-running or blocked queries. "
            "2. Check application logs for the specific query or endpoint that started failing at 09:47. "
            "3. Temporarily increase the connection pool size to 25 to restore service while "
            "the root query is identified."
        ),
        "expected_priority": "P2",
    },
    {
        "id": "diag_02",
        "task_type": "diagnosis",
        "difficulty": "hard",
        "title": "Intermittent login failures with no clear pattern",
        "incident": (
            "Users are reporting intermittent login failures — approximately 1 in 8 login attempts "
            "fails with a generic 'Authentication error' message. The failure rate has been "
            "steady at ~12% for the last 90 minutes. There is no pattern by user, browser, "
            "or geography. Both SSO and password logins are affected equally. "
            "Auth service logs show: 'JWT validation failed: signature verification error' "
            "on the failing requests. The JWT signing key was not changed. "
            "The auth service runs on 4 pods in a Kubernetes cluster. "
            "What is the most likely root cause and what are your next three investigation steps?"
        ),
        "reference": (
            "Most likely root cause: key mismatch across auth service pods. "
            "One or more pods may be running a different version of the auth service with a "
            "different signing key, or a pod has failed to load the latest secret from the "
            "secrets store. The 1-in-4 failure rate (12.5%) is consistent with one of four pods "
            "being misconfigured — requests routed to that pod fail, others succeed. "
            "Next three steps: "
            "1. Check the JWT signing key loaded by each pod: kubectl exec into each auth pod "
            "and verify the key fingerprint is identical. "
            "2. Check recent pod restarts or deployments: kubectl get events and rollout history "
            "for the auth deployment. "
            "3. Temporarily remove the suspect pod from the load balancer rotation to stop "
            "the failure while the key mismatch is resolved."
        ),
        "expected_priority": "P2",
    },

    # ----------------------------------------------------------------
    # RESOLUTION
    # ----------------------------------------------------------------
    {
        "id": "res_01",
        "task_type": "resolution",
        "difficulty": "hard",
        "title": "Missing PostgreSQL index on live production table",
        "incident": (
            "Root cause confirmed: a missing index on the orders table is causing full table scans "
            "on every checkout query. The orders table has 47 million rows. "
            "Current query time: 18 seconds average. SLA target: under 500ms. "
            "The database is PostgreSQL 14. The production system is live with active transactions "
            "— approximately 200 writes per second to the orders table. "
            "Provide step-by-step resolution instructions."
        ),
        "reference": (
            "Step 1: Take a backup or verify the last automated backup completed successfully "
            "before making any schema changes. "
            "Step 2: Create the index using CREATE INDEX CONCURRENTLY — this avoids a table lock "
            "and allows reads and writes to continue during index build. "
            "Example: CREATE INDEX CONCURRENTLY idx_orders_customer_id ON orders(customer_id); "
            "Step 3: Monitor index build progress via pg_stat_progress_create_index. "
            "Expect 15–30 minutes for 47M rows. "
            "Step 4: Once complete, run EXPLAIN ANALYZE on the checkout query to confirm "
            "the index is being used and query time has dropped. "
            "Step 5: Monitor query performance in APM for 10 minutes post-index creation. "
            "WARNING: Do NOT use CREATE INDEX without CONCURRENTLY — it will lock the table "
            "and block all writes, extending the incident."
        ),
        "expected_priority": "P1",
    },
    {
        "id": "res_02",
        "task_type": "resolution",
        "difficulty": "medium",
        "title": "Memory leak in Node.js service causing gradual degradation",
        "incident": (
            "A Node.js API service is experiencing a gradual memory leak. "
            "Memory grows from 512MB at startup to 3.8GB over approximately 6 hours, "
            "at which point the pod is OOMKilled and restarts. "
            "The service handles webhooks. A recent deploy (3 days ago) added a new "
            "webhook handler. Memory profiling shows heap growth concentrated in "
            "an event listener array that is never cleared. "
            "Provide step-by-step resolution instructions. The service currently restarts "
            "every 6 hours as a workaround."
        ),
        "reference": (
            "Immediate mitigation (keep in place until fix is deployed): "
            "Step 1: Set a memory limit and liveness probe restart threshold in Kubernetes "
            "to restart the pod at 2GB rather than waiting for OOMKill — reduces user impact. "
            "Permanent fix: "
            "Step 2: In the new webhook handler, identify the event listener registration. "
            "Look for EventEmitter.on() or process.on() calls without corresponding "
            "removeListener() or once() calls. "
            "Step 3: Fix the handler to use emitter.once() for one-time listeners, or "
            "store a reference to the listener function and call removeListener() after use. "
            "Step 4: Write a unit test that registers the handler 1000 times and asserts "
            "the listener count does not grow. "
            "Step 5: Deploy the fix and monitor memory growth rate — it should plateau "
            "at the baseline ~512MB."
        ),
        "expected_priority": "P2",
    },

    # ----------------------------------------------------------------
    # ESCALATION
    # ----------------------------------------------------------------
    {
        "id": "esc_01",
        "task_type": "escalation",
        "difficulty": "medium",
        "title": "P2 storage degradation with procurement gap",
        "incident": (
            "A P2 storage degradation incident has been open for 3.5 hours. "
            "The assigned Level 2 engineer has confirmed root cause: a failed SSD in a RAID-6 array. "
            "The replacement drive is not in the on-site spare kit. "
            "Procurement lead time for the correct drive model is 4–6 hours. "
            "A RAID-6 array can tolerate two simultaneous drive failures. "
            "One drive has already failed. The array is currently in a degraded state. "
            "Should this be escalated? To whom? What is the escalation message?"
        ),
        "reference": (
            "Yes — escalate immediately. "
            "Escalate to: Storage Team Lead and Operations Manager. "
            "Reason for escalation: during the 4–6 hour procurement window, the array is "
            "operating with zero fault tolerance. A second drive failure (which is statistically "
            "more likely on a degraded array due to rebuild stress) would cause complete data loss. "
            "The incident risk has increased from P2 to a P1 risk window even though current "
            "service is degraded but operational. "
            "Escalation message: "
            "'RAID-6 array is degraded with one failed drive. Replacement drive ETA 4–6 hours. "
            "During this window the array has zero fault tolerance — a second failure means "
            "full data loss. Requesting approval to source drive via emergency procurement "
            "and authorisation to begin offsite backup of critical volumes immediately.'"
        ),
        "expected_priority": "P2",
    },
    {
        "id": "esc_02",
        "task_type": "escalation",
        "difficulty": "hard",
        "title": "P3 that may be a security incident",
        "incident": (
            "A P3 incident was raised 2 hours ago: an internal reporting tool is returning "
            "empty results for some users. During investigation, the Level 1 engineer noticed "
            "that the affected users all have access to a specific financial dataset. "
            "The application logs show successful authentication and authorisation for these users, "
            "but the queries are returning 0 rows from a table that should have 14,000 records. "
            "A check of the table shows it currently has 3 records. "
            "No one has reported deleting data. No scheduled jobs ran today. "
            "Should this be escalated? To whom? What priority should this be re-classified as?"
        ),
        "reference": (
            "Yes — escalate immediately and re-classify as P1. "
            "Escalate to: Security team, Data team lead, and CISO (or security on-call). "
            "Reason: this is no longer a reporting tool issue — this is potential data loss "
            "or unauthorised deletion of financial data. 13,997 records are missing with no "
            "known cause. This meets the threshold for a security incident. "
            "Actions before escalation: "
            "1. Do not alert the users — if this is malicious, alerting them may prompt "
            "evidence destruction. "
            "2. Immediately take a snapshot of the current database state and logs. "
            "3. Check audit logs for DELETE or TRUNCATE operations on the table. "
            "Re-classification justification: potential data breach or malicious deletion "
            "of financial records is P1 regardless of current user-facing impact."
        ),
        "expected_priority": "P1",
    },

    # ----------------------------------------------------------------
    # COMMUNICATION
    # ----------------------------------------------------------------
    {
        "id": "comm_01",
        "task_type": "communication",
        "difficulty": "easy",
        "title": "Post-resolution user communication — P1 email outage",
        "incident": (
            "A P1 email service outage has been resolved. "
            "Duration: 47 minutes (14:23 UTC to 15:10 UTC). "
            "Root cause: a misconfigured DNS record introduced during routine maintenance. "
            "All services restored. No emails were lost — messages queued during the outage "
            "are being delivered now. No data loss. "
            "Audience: affected end users (non-technical). "
            "Draft the post-resolution communication."
        ),
        "reference": (
            "Subject: Email Service Restored — [Date] "
            "We want to let you know that our email service experienced an interruption "
            "between 2:23 PM and 3:10 PM UTC today (47 minutes). "
            "The issue has been fully resolved. "
            "Any emails sent to you during this period were queued and are now being delivered. "
            "No emails were lost. "
            "We apologise for the disruption. Our team has identified and corrected the cause "
            "to prevent recurrence. "
            "If you have any questions or notice any issues, please contact support."
        ),
        "expected_priority": None,
    },
    {
        "id": "comm_02",
        "task_type": "communication",
        "difficulty": "medium",
        "title": "Ongoing P2 degradation — stakeholder update",
        "incident": (
            "A P2 performance degradation has been ongoing for 90 minutes. "
            "The checkout process is slow (12–15 seconds instead of 2 seconds) for all users. "
            "Root cause identified: connection pool exhaustion due to a slow database query. "
            "A fix is being tested in staging and is expected to be deployed within 45 minutes. "
            "Workaround: users can complete checkout — it is slow but functional. "
            "Audience: executive stakeholders and the VP of Engineering. "
            "Draft the stakeholder update."
        ),
        "reference": (
            "Subject: [ONGOING P2] Checkout Performance Degradation — Update "
            "Status: Active — Fix in progress. "
            "Impact: All users are experiencing checkout times of 12–15 seconds "
            "(normal: ~2 seconds). Checkout is functional — no transactions are failing. "
            "Root cause: A slow database query is exhausting the connection pool, "
            "causing delays across all checkout requests. "
            "Current action: A fix has been developed and is undergoing testing in staging. "
            "Estimated deployment: within 45 minutes. "
            "Revenue impact: Conversion rate is likely reduced during this window. "
            "Monitoring is in place. Next update in 30 minutes or upon resolution."
        ),
        "expected_priority": None,
    },

    # ----------------------------------------------------------------
    # POST-INCIDENT
    # ----------------------------------------------------------------
    {
        "id": "post_01",
        "task_type": "post_incident",
        "difficulty": "medium",
        "title": "Payments API outage post-incident report",
        "incident": (
            "Write a post-incident report for the following: "
            "P1 incident — Payment API outage. "
            "Start: 14:23 UTC | Resolved: 15:10 UTC | Duration: 47 minutes. "
            "Root cause: connection pool exhausted due to slow queries caused by a missing index "
            "on the orders table (47M rows). "
            "Impact: 3,200 failed transactions per minute, estimated $94,000 revenue impact, "
            "3 enterprise client escalations. "
            "Resolution: index created using CREATE INDEX CONCURRENTLY (no downtime), "
            "connection pool size increased from 10 to 25. "
            "Cover: timeline, root cause, impact, resolution, and three preventative actions."
        ),
        "reference": (
            "Timeline: "
            "14:23 — Payment API begins returning 503 on POST requests. "
            "14:31 — Incident declared P1, on-call engineer paged. "
            "14:45 — Root cause identified: missing index causing full table scans. "
            "14:52 — CREATE INDEX CONCURRENTLY initiated. "
            "15:06 — Index build complete, query times drop to <300ms. "
            "15:10 — All services confirmed normal, incident closed. "
            "Root cause: A missing index on orders(customer_id) caused full table scans "
            "on every checkout query. As table size crossed 47M rows, query time exceeded "
            "the connection pool wait timeout (30s), exhausting the pool and blocking all writes. "
            "Impact: 47 minutes of payment write failures. ~150,000 failed transactions. "
            "$94,000 estimated revenue impact. 3 enterprise escalations. "
            "Resolution: Index created CONCURRENTLY (zero write downtime). Pool size increased "
            "to 25 as a buffer. "
            "Preventative actions: "
            "1. Add automated query plan analysis to the CI pipeline — flag queries with "
            "sequential scans on tables >1M rows before deployment. "
            "2. Add a database index coverage check to the deployment runbook. "
            "3. Set up an alert on connection pool utilisation >80% to catch exhaustion "
            "before it causes user impact."
        ),
        "expected_priority": None,
    },
    {
        "id": "post_02",
        "task_type": "post_incident",
        "difficulty": "hard",
        "title": "Financial data deletion — security post-incident",
        "incident": (
            "Write a post-incident report for the following: "
            "P1 security incident — Unauthorised deletion of financial records. "
            "Start: 10:14 UTC (estimated) | Detected: 13:45 UTC | Contained: 14:20 UTC. "
            "Root cause: a misconfigured database migration script ran in production "
            "instead of staging due to an incorrect environment variable. "
            "The script deleted 13,997 records from the financial_reports table. "
            "Data was recovered from the 06:00 UTC automated backup — 7 hours 45 minutes of "
            "data had to be manually reconstructed from audit logs. "
            "No external breach — internal misconfiguration only. "
            "Cover: timeline, root cause, impact, resolution, and three preventative actions."
        ),
        "reference": (
            "Timeline: "
            "06:00 — Last clean automated backup taken. "
            "10:14 — Migration script executed in production (estimated based on log timestamps). "
            "13:45 — L1 engineer detects missing records during P3 investigation. "
            "13:52 — Incident re-classified P1, security team notified. "
            "14:00 — Database snapshot taken, audit logs preserved. "
            "14:20 — Confirmed internal misconfiguration, no external breach. "
            "15:30 — Data restore from 06:00 backup initiated. "
            "22:00 — Manual reconstruction of 7h45m of missing transactions complete. "
            "Root cause: A database migration script targeted production due to the ENV variable "
            "being set to 'prod' in a shared .env file that was not environment-scoped. "
            "Impact: 13,997 financial records deleted. ~8 hours of data required manual "
            "reconstruction. No external breach. Regulatory notification required per data "
            "governance policy. "
            "Resolution: Data restored from backup. Missing period reconstructed from audit logs. "
            "Preventative actions: "
            "1. Migration scripts must require an explicit --env flag — no fallback to environment "
            "variables for destructive operations. "
            "2. Add a production guard: migration scripts targeting production require a second "
            "engineer approval via the deployment pipeline. "
            "3. Reduce backup interval from 24 hours to 4 hours for all tables containing "
            "financial or regulated data."
        ),
        "expected_priority": None,
    },
]

# Dimension weights per task type
WEIGHTS = {
    "triage":        {"TA": 0.25, "PA": 0.40, "PR": 0.25, "AC": 0.10},
    "diagnosis":     {"TA": 0.45, "PA": 0.15, "PR": 0.15, "AC": 0.25},
    "resolution":    {"TA": 0.35, "PA": 0.10, "PR": 0.15, "AC": 0.25, "SF": 0.15},
    "escalation":    {"TA": 0.20, "PA": 0.35, "PR": 0.35, "AC": 0.10},
    "communication": {"TA": 0.20, "PA": 0.10, "PR": 0.30, "AC": 0.10, "CQ": 0.30},
    "post_incident": {"TA": 0.40, "PA": 0.05, "PR": 0.25, "AC": 0.30},
}

# Quality gate per task type
QUALITY_GATES = {
    "triage":        4.0,
    "diagnosis":     3.5,
    "resolution":    4.0,
    "escalation":    4.0,
    "communication": 3.5,
    "post_incident": 3.5,
}
