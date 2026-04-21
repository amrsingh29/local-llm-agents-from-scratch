# ITSM Evaluation Framework

## Why ITSM Needs a Dedicated Evaluation Framework

A generic 1–5 quality score is insufficient for evaluating AI responses in Incident Management. Consider two responses to a P1 database outage:

**Response A:** Technically accurate diagnosis, correct remediation steps, wrong priority (marked P3 instead of P1). Delayed escalation by 2 hours.

**Response B:** Slightly imprecise diagnosis, correct priority (P1), immediate escalation recommended. Operations notified.

A generic judge scores Response A higher because the technical content is better. But in production, Response A caused a 2-hour SLA breach. Response B — despite being technically weaker — was operationally correct.

ITSM evaluation requires multiple dimensions with different weights per task type. The evaluation framework must reflect what actually matters in each context.

---

## The Six ITSM Task Types

Incident management involves six distinct AI task types. Each has different quality criteria, different failure modes, and different evaluation weights.

| Task Type | What the AI does | Primary failure risk |
|-----------|-----------------|---------------------|
| **Triage** | Classifies priority, category, affected services | Wrong priority → SLA breach or over-escalation |
| **Diagnosis** | Identifies root cause, recommends investigation steps | Wrong diagnosis → wasted effort, prolonged outage |
| **Resolution** | Provides step-by-step remediation instructions | Unsafe steps → making the incident worse |
| **Escalation** | Decides whether/how to escalate and to whom | Wrong call → delay or unnecessary noise |
| **Communication** | Drafts user-facing or stakeholder messages | Wrong tone/content → erodes trust |
| **Post-incident** | Summarises timeline, RCA, and improvement actions | Incomplete RCA → recurrence |

---

## Evaluation Dimensions

Every response is scored on five core dimensions plus one communication-specific dimension.

### Dimension 1 — Technical Accuracy (TA)
Is the technical content correct? Does the diagnosis reflect what the symptoms indicate? Are the remediation steps technically sound?

```
5 — Fully correct. No technical errors. All key technical points covered.
4 — Mostly correct. Minor imprecision but not misleading.
3 — Partially correct. Right direction but missing important technical detail.
2 — Mostly wrong. Contains correct fragments but overall technically unsound.
1 — Completely wrong or harmful. Would cause the responder to take incorrect action.
```

### Dimension 2 — Priority Accuracy (PA)
Is the priority/severity assignment correct per ITIL P1–P4 criteria?

```
5 — Correct priority with correct justification.
4 — Correct priority, weak or missing justification.
3 — Priority off by one level (P1 called P2, or P3 called P2). Marginal.
2 — Priority off by two levels. Would materially affect response.
1 — Completely wrong priority. P1 called P3/P4 or vice versa. SLA breach risk.
```

**Note:** Priority accuracy is binary in real incidents — a P1 called P2 is an SLA breach, not a "close enough." The numeric score is included for training feedback, but a score of 3 or below should trigger mandatory human review.

### Dimension 3 — Process Adherence (PR)
Does the response follow the organisation's ITSM process? Does it include required fields, follow escalation paths, and reference the correct runbooks?

```
5 — Fully process-compliant. Correct fields, correct escalation path, references correct runbook.
4 — Mostly compliant. Minor omission (e.g., missing one required field).
3 — Partially compliant. Follows some process steps but skips important ones.
2 — Mostly non-compliant. Process is mostly ignored.
1 — Completely ignores process. Response would not be accepted by ITSM tooling.
```

### Dimension 4 — Actionability (AC)
Are the recommended steps concrete, executable, and ordered correctly? Can a Level 1 engineer follow them without additional clarification?

```
5 — Steps are specific, ordered, and executable. No ambiguity.
4 — Steps are mostly specific. One step requires interpretation.
3 — Steps are vague. Direction is correct but executor needs to figure out the details.
2 — Steps are mostly vague or incorrectly ordered. Would cause confusion.
1 — No actionable steps, or steps are counterproductive.
```

### Dimension 5 — Safety (SF)
Does the response avoid recommending actions that could extend the incident, cause data loss, or create a new incident?

```
PASS — No unsafe recommendations. Steps are reversible or clearly flagged as destructive.
WARN — Response includes a potentially unsafe step without flagging it.
FAIL — Response includes a clearly unsafe recommendation (e.g., "restart the production database" without a backup check).
```

Safety is treated as a hard gate: a FAIL on safety overrides all other scores and requires human review before the response is used.

### Dimension 6 — Communication Quality (CQ)
Applies to communication task type only. Is the tone appropriate for the audience? Does it avoid jargon for end users? Is it appropriately urgent for stakeholder communications?

---

## Dimension Weights Per Task Type

Different task types prioritise different dimensions. These weights reflect what drives real-world outcomes.

| Task Type | TA | PA | PR | AC | SF | CQ |
|-----------|----|----|----|----|-----|-----|
| Triage | 25% | 40% | 25% | 10% | gate | — |
| Diagnosis | 45% | 15% | 15% | 25% | gate | — |
| Resolution | 35% | 10% | 15% | 25% | 15% | — |
| Escalation | 20% | 35% | 35% | 10% | gate | — |
| Communication | 20% | 10% | 30% | 10% | — | 30% |
| Post-incident | 40% | 5% | 25% | 30% | — | — |

**Triage** weights priority accuracy highest — getting the priority wrong has the greatest operational consequence.

**Diagnosis** weights technical accuracy highest — a wrong diagnosis sends the team in the wrong direction.

**Resolution** weights safety as a scored dimension (15%) rather than a pure gate — because resolution steps inherently involve risk and partial safety awareness is still better than none.

**Communication** and **Post-incident** do not have a safety gate — these are write tasks, not action tasks.

---

## Weighted Score Calculation

```
weighted_score = (TA × w_TA) + (PA × w_PA) + (PR × w_PR) + (AC × w_AC)

If SF == FAIL:
    weighted_score = 0  (hard override — human review required)
If SF == WARN:
    weighted_score = weighted_score × 0.75  (25% penalty)
```

The final weighted score is on a 1–5 scale, consistent with the per-dimension scores.

---

## Quality Gates Per Task Type

| Task Type | Minimum weighted score |
|-----------|----------------------|
| Triage | 4.0 |
| Diagnosis | 3.5 |
| Resolution | 4.0 |
| Escalation | 4.0 |
| Communication | 3.5 |
| Post-incident | 3.5 |

Responses below the gate are flagged for human review before use.

---

## What the Code Does

Three Python files implement this framework:

### `itsm_scenarios.py` — Shared Benchmark Data

Defines 12 scenarios (2 per task type), the dimension weights per task type, and the quality gates. Both evaluation scripts import from this file so they use identical scenarios and scoring rules.

Each scenario has:
- `id` — unique identifier (e.g., `triage_01`)
- `task_type` — which of the six task types applies
- `difficulty` — easy / medium / hard
- `incident` — the situation presented to the model under test
- `reference` — the expert answer used by the judge

### `03_itsm_benchmark.py` — Self-Evaluation (Gemma judges Gemma)

1. Loads all 12 scenarios from `itsm_scenarios.py`
2. For each scenario: calls `gemma4:26b` with the incident prompt
3. Passes the response, reference answer, and task-type-specific judge prompt to a second call of `gemma4:26b` acting as the judge
4. The judge returns a JSON object with one score per dimension
5. `compute_weighted_score()` applies the task-type weights and safety gate
6. Prints a per-scenario breakdown and saves results to `/tmp/itsm_self_eval.json`

This is the **self-evaluation** design — Gemma scores its own outputs. This is inexpensive (no API cost) but introduces a known risk: self-enhancement bias.

### `04_itsm_cross_model_eval.py` — Cross-Model Evaluation (Claude judges Gemma)

1. Same scenarios, same model under test (`gemma4:26b` via Ollama)
2. The judge is `claude-haiku-4-5` via the Anthropic API — a different model family
3. Identical judge prompts to ensure a fair comparison
4. After scoring all 12 scenarios, `print_bias_comparison()` loads the self-eval results and computes per-scenario score deltas
5. If the average delta exceeds 0.15, self-enhancement bias is flagged

The two-script design lets you run either in isolation (self-eval is free; cross-eval costs API tokens) and compare results directly.

---

## The 12 Benchmark Scenarios

### Triage Scenarios

**triage_01 — Payments API complete outage (Hard, P1)**

```
The payments API has been returning HTTP 503 for all POST /v1/payments requests
since 14:23 UTC. GET requests return 200. Database health checks pass.
3,200 transactions per minute are failing. No successful payments in the last
26 minutes. Three enterprise clients have called the support line.
Classify this incident: assign priority, category, affected services,
and write a one-sentence impact statement.
```

Expected: P1, Application/API, Payment API. This is the unambiguous P1 case — complete outage, revenue impact, enterprise escalations.

**triage_02 — Dashboard slow load for subset of users (Medium, P3)**

```
The analytics dashboard is loading slowly (8–12 seconds instead of the normal
2 seconds) for approximately 15% of users, specifically those whose accounts
were migrated to the new data tier last week. A workaround exists: refreshing
the page twice resolves the issue temporarily.
Classify this incident: assign priority, category, affected services,
and write a one-sentence impact statement.
```

Expected: P3. This tests priority discrimination — the model must recognise that a workaround, limited user scope (<25%), and no data loss all point to P3, not P2.

---

### Diagnosis Scenarios

**diag_01 — Web server CPU spike and timeout errors (Medium)**

```
All three web servers show CPU utilisation at 98% since 09:47 UTC (40 minutes ago).
Response times increased from 200ms to 8,000ms. No deployments in the last 72 hours.
Error logs show: 'HikariCP connection pool timeout — pool size: 10, wait timeout: 30s'.
The database server itself shows normal CPU and memory.
What is the most likely root cause? Provide your next three investigation steps.
```

Expected root cause: database connection pool exhaustion. The key signal is that the database itself is healthy — the issue is in the connection layer, not the database. A correct diagnosis identifies SHOW PROCESSLIST and increasing the pool size as immediate steps.

**diag_02 — Intermittent login failures with no clear pattern (Hard)**

```
Users are reporting intermittent login failures — approximately 1 in 8 login attempts
fails with 'Authentication error'. Both SSO and password logins are affected equally.
Auth service logs show: 'JWT validation failed: signature verification error'
on the failing requests. The JWT signing key was not changed.
The auth service runs on 4 pods in a Kubernetes cluster.
What is the most likely root cause and what are your next three investigation steps?
```

Expected root cause: key mismatch across auth pods. The 1-in-8 failure rate (12.5%) is the signal — it is consistent with exactly 1 of 4 pods being misconfigured. The model needs to identify the statistical pattern and propose pod-level key verification.

---

### Resolution Scenarios

**res_01 — Missing PostgreSQL index on live production table (Hard)**

```
Root cause confirmed: a missing index on the orders table is causing full table scans
on every checkout query. The orders table has 47 million rows.
Current query time: 18 seconds average. SLA target: under 500ms.
The database is PostgreSQL 14. The production system is live with active transactions
— approximately 200 writes per second to the orders table.
Provide step-by-step resolution instructions.
```

Expected: The model must know to use `CREATE INDEX CONCURRENTLY` — the standard `CREATE INDEX` locks the table and blocks all writes, which would extend the incident. This tests whether the model recognises that the resolution step itself can cause harm if done incorrectly.

**res_02 — Memory leak in Node.js service (Medium)**

```
A Node.js API service is experiencing a gradual memory leak.
Memory grows from 512MB at startup to 3.8GB over approximately 6 hours,
at which point the pod is OOMKilled and restarts.
Memory profiling shows heap growth concentrated in an event listener array
that is never cleared.
Provide step-by-step resolution instructions.
```

Expected: The model must separate the immediate mitigation (restart threshold in Kubernetes) from the permanent fix (removing or bounding the event listener). It should also include a test to verify the fix.

---

### Escalation Scenarios

**esc_01 — P2 storage degradation with procurement gap (Medium)**

```
A P2 storage degradation incident has been open for 3.5 hours.
Root cause confirmed: a failed SSD in a RAID-6 array.
Replacement drive is not in the on-site spare kit.
Procurement lead time: 4–6 hours.
A RAID-6 array can tolerate two simultaneous drive failures. One has already failed.
Should this be escalated? To whom? What is the escalation message?
```

Expected: Yes — escalate immediately. The risk has changed: during the procurement window the array has zero fault tolerance. A second failure means complete data loss. The escalation message must communicate the risk window, not just the current state.

**esc_02 — P3 that is actually a security incident (Hard)**

```
A P3 was raised: an internal reporting tool is returning empty results for some users.
The affected users all have access to a specific financial dataset.
A check of the table shows it currently has 3 records. It should have 14,000.
No one has reported deleting data. No scheduled jobs ran today.
Should this be escalated? To whom? What priority should this be re-classified as?
```

Expected: Re-classify to P1 immediately, escalate to security team and CISO. The model must recognise that this is no longer a reporting tool issue — 13,997 records are missing with no known cause, which meets the threshold for a security incident. Crucially, it should also note: do not alert the users until evidence is preserved.

---

### Communication Scenarios

**comm_01 — Post-resolution user communication (Easy)**

```
A P1 email service outage has been resolved. Duration: 47 minutes.
Root cause: a misconfigured DNS record introduced during routine maintenance.
All services restored. No emails were lost — messages queued during the outage
are being delivered now.
Audience: affected end users (non-technical).
Draft the post-resolution communication.
```

Expected: Plain language, no jargon, confirmation that no emails were lost, brief apology, contact for questions.

**comm_02 — Ongoing P2 degradation stakeholder update (Medium)**

```
A P2 performance degradation has been ongoing for 90 minutes.
The checkout process is slow (12–15 seconds instead of 2 seconds) for all users.
Root cause identified: connection pool exhaustion due to a slow database query.
A fix is being tested in staging and is expected to be deployed within 45 minutes.
Audience: executive stakeholders and the VP of Engineering.
Draft the stakeholder update.
```

Expected: BLUF format, specific ETA, revenue impact acknowledgement, no technical jargon beyond what an executive would know.

---

### Post-Incident Scenarios

**post_01 — Payments API outage post-incident report (Medium)**

```
Write a post-incident report for the following:
P1 incident — Payment API outage.
Start: 14:23 UTC | Resolved: 15:10 UTC | Duration: 47 minutes.
Root cause: connection pool exhausted due to slow queries from a missing index.
Impact: 3,200 failed transactions per minute, $94,000 revenue impact.
Resolution: CREATE INDEX CONCURRENTLY, connection pool size increased from 10 to 25.
Cover: timeline, root cause, impact, resolution, and three preventative actions.
```

Expected: The three preventative actions must be specific and ownable. Vague actions like "improve monitoring" score low on actionability — good actions name what to build, where, and who is responsible.

**post_02 — Financial data deletion security post-incident (Hard)**

```
Write a post-incident report for the following:
P1 security incident — Unauthorised deletion of financial records.
Root cause: a misconfigured migration script ran in production instead of staging
due to an incorrect environment variable.
13,997 records deleted. Recovered from 06:00 UTC backup.
7 hours 45 minutes of data manually reconstructed from audit logs.
Cover: timeline, root cause, impact, resolution, and three preventative actions.
```

Expected: The timeline must include the estimated incident start time (not just detection time). The preventative actions must address the root cause (environment variable isolation, migration approval gates, backup frequency for regulated data).

---

## Experiment Results

Both evaluation scripts were run on `gemma4:26b` on Apple M4 (24 GB RAM) with Ollama.

### Self-Evaluation — Gemma judges Gemma

Model under test: `gemma4:26b` | Judge: `gemma4:26b` | Duration: 555.6 seconds

| Task Type | Score | Gate | Result |
|-----------|-------|------|--------|
| Escalation | 4.83 | 4.0 | PASS |
| Communication | 4.80 | 3.5 | PASS |
| Diagnosis | 4.70 | 3.5 | PASS |
| Triage | 4.40 | 4.0 | PASS |
| Resolution | 3.90 | 4.0 | FAIL |
| Post-incident | 3.48 | 3.5 | FAIL |
| **Overall** | **4.35** | | |

**Per-scenario breakdown:**

| Scenario | Score | Notes |
|----------|-------|-------|
| triage_01 | 5.00 | P1 correctly identified, all fields present, clear impact statement |
| triage_02 | 3.80 | PA=2: model assigned P2 instead of P3 — 2-level error, correct category |
| diag_01 | 4.70 | Correct root cause (connection pool), all steps actionable |
| diag_02 | 4.70 | Correct key mismatch diagnosis, correct kubectl steps |
| res_01 | 3.90 | PR=4: correctly used CONCURRENTLY but missing strict change-freeze step |
| res_02 | 3.90 | PR=4: mitigation and fix both present but no unit test step |
| esc_01 | 5.00 | Escalation decision, path, and message all correct |
| esc_02 | 4.65 | Correctly re-classified to P1, evidence-preservation note included |
| comm_01 | 4.80 | Offered three template options; plain language, correct facts |
| comm_02 | 4.80 | BLUF format, correct technical explanation for executive audience |
| post_01 | 3.20 | AC=1: preventative actions present but vague — no owners, no specifics |
| post_02 | 3.75 | AC=2: only one of three preventative actions was specific |

**Observations:**
- Gemma awarded itself TA=5 on nearly every scenario — Technical Accuracy was almost never the failure mode
- The two gate failures (resolution, post-incident) were caused by low Actionability and Process Adherence — not technical errors
- Self-critique was inconsistent: post_01 received AC=1 (honest), but resolution scenarios received AC=5 despite missing steps

---

### Cross-Model Evaluation — Claude judges Gemma

Model under test: `gemma4:26b` | Judge: `claude-haiku-4-5` (Anthropic API) | Duration: 369.5 seconds

| Task Type | Score | Gate | Result | Notes |
|-----------|-------|------|--------|-------|
| Communication | 4.80 | 3.5 | PASS | — |
| Escalation | 4.57 | 4.0 | PASS | — |
| Triage | 4.40 | 4.0 | PASS | — |
| Diagnosis | 3.53 | 3.5 | PASS | Parse error on diag_01, WARN on diag_02 |
| Resolution | 3.19 | 4.0 | FAIL | SF=WARN on both scenarios |
| Post-incident | 3.15 | 3.5 | FAIL | — |
| **Overall** | **3.98** | | |

**Per-scenario breakdown:**

| Scenario | Score | Notes |
|----------|-------|-------|
| triage_01 | 5.00 | Perfect agreement with self-eval |
| triage_02 | 3.80 | PA=2: same priority error caught by both judges |
| diag_01 | 0.00 | Parse error — Claude's JSON output was malformed, scored as 0 |
| diag_02 | 3.53 | SF=WARN: Claude flagged missing evidence-preservation step |
| res_01 | 3.90 | Aligned with self-eval; SF=PASS, PR=4 |
| res_02 | 2.47 | SF=WARN: recommending memory limit increase without rollback plan flagged unsafe |
| esc_01 | 4.80 | TA=4 (not 5) — Claude noted missing vendor SLA negotiation detail |
| esc_02 | 4.35 | TA=4, PR=4 — Claude deducted for incomplete escalation path |
| comm_01 | 4.80 | Perfect agreement with self-eval |
| comm_02 | 4.80 | Perfect agreement with self-eval |
| post_01 | 3.35 | AC=2: same finding as self-eval — preventative actions too vague |
| post_02 | 2.95 | AC=2, TA=3: Claude marked RCA incomplete on the security incident |

**Key difference from self-eval:** Claude applied SF=WARN on two resolution scenarios where Gemma gave SF=PASS. This is the most consequential disagreement — safety flags affect whether responses are surfaced to engineers.

---

## Self-Enhancement Bias Analysis

The core question: does a model score its own outputs more generously than an independent judge would?

| Scenario | Self-eval | Cross-eval | Delta |
|----------|-----------|------------|-------|
| comm_01 | 4.80 | 4.80 | 0.00 |
| comm_02 | 4.80 | 4.80 | 0.00 |
| diag_01 | 4.70 | 0.00 | +4.70 (parse error) |
| diag_02 | 4.70 | 3.53 | +1.17 |
| esc_01 | 5.00 | 4.80 | +0.20 |
| esc_02 | 4.65 | 4.35 | +0.30 |
| post_01 | 3.20 | 3.35 | -0.15 |
| post_02 | 3.75 | 2.95 | +0.80 |
| res_01 | 3.90 | 3.90 | 0.00 |
| res_02 | 3.90 | 2.47 | +1.43 |
| triage_01 | 5.00 | 5.00 | 0.00 |
| triage_02 | 3.80 | 3.80 | 0.00 |
| **Average** | **4.35** | **3.98** | **+0.70** |

**Conclusion: self-enhancement bias is present and significant.**

Gemma scored itself an average of **+0.70 points** above Claude across the 12 scenarios. The bias is not uniform — it is concentrated in specific task types and scenarios where the assessment requires judgement rather than rule-checking:

- **Triage and communication** — both judges agreed exactly. These tasks have clear right/wrong answers (priority is correct or not; the draft either has the required fields or it doesn't).
- **Resolution** — Gemma gave itself SF=PASS on `res_02`; Claude gave SF=WARN. This is the highest-stakes disagreement — safety assessments are where self-enhancement bias has the most operational consequence.
- **Post-incident** — both judges scored actionability low, but Claude was stricter on technical accuracy (`post_02` TA=3 vs Gemma's TA=5).
- **diag_01** — the +4.70 delta is caused by a parse error in Claude's response, not true disagreement. The real inflation is in `res_02` (+1.43) and `diag_02` (+1.17).

---

## What This Means for Production Use

**Self-evaluation is useful for development, not production gates.**

During development, self-evaluation is cheap and fast — it costs no API tokens and runs entirely locally. It is well-calibrated for structured tasks (triage, communication) where the rubric is binary. Use it to catch obvious failures early.

For production quality gates, use cross-model evaluation. The +0.70 inflation means that a self-eval score of 4.35/5 corresponds to approximately 3.65/5 from an independent judge. Applying a quality gate of 4.0 against self-eval scores would pass responses that an independent judge would flag.

**Safety assessments need independent validation.** The safety dimension is where self-enhancement bias matters most — Gemma passed resolution responses that Claude flagged as potentially unsafe. In a production ITSM system, safety flags are the mechanism that routes responses to human review before they reach an engineer.

**Communication tasks can use self-evaluation.** Both judges agreed exactly on all four communication scenarios. For tasks where quality is determined by structure (does the draft include the required fields?) rather than by judgment (is this recommendation safe?), self-evaluation is reliable.

---

## The Parse Error Problem

`diag_01` received a score of 0.0 in cross-eval due to a parse error — Claude's JSON output contained additional reasoning text that `parse_judge_output()` could not extract cleanly.

This highlights a real production issue: judge output parsing is a failure mode in its own right. In production, a parse error should not silently score a response as 0. It should trigger a retry with a stricter prompt before falling back to a parse-error flag.

The current parser extracts the first complete JSON object from the response:

```python
def parse_judge_output(raw: str) -> dict:
    cleaned = raw.strip().strip("`").lstrip("json").strip()
    start   = cleaned.index("{")
    end     = cleaned.rindex("}") + 1
    return json.loads(cleaned[start:end])
```

This handles markdown code blocks and leading text, but fails if the JSON itself contains a formatting error. A production implementation would use `json.JSONDecoder().raw_decode()` or retry with a higher-temperature judge call.

---

## Calibration Guidance

Before using this framework in production, the judge should be calibrated against human expert ratings. Recommended calibration set:

- 30 triage scenarios (10 per priority band: P1/P2, P3, P4)
- 20 resolution scenarios (10 safe, 10 with at least one unsafe step)
- 20 communication scenarios (10 technical audience, 10 non-technical)

**Agreement threshold:** ≥80% of judge scores within ±0.5 weighted points of human expert scores. If agreement is below threshold, identify which dimension is diverging and refine that dimension's rubric.

**Known ITSM judge biases to watch for:**

- **Severity inflation:** judges rate P1 responses higher regardless of quality, because P1 sounds more important
- **Jargon approval:** responses using ITIL terminology (RACI, KEDB, SLA, OLA) may score higher on process adherence even if the content is vague
- **Completeness over correctness:** a long response covering many possible causes may score higher than a shorter, accurate one

---

## Key Concepts Demonstrated

| Concept | What this experiment shows |
|---------|---------------------------|
| Multi-dimensional scoring | A single 1–5 score is insufficient for operational domains. Separating TA, PA, PR, AC, and SF catches failure modes that a single score would hide. |
| Task-type-specific weights | Triage needs priority accuracy weighted at 40%; diagnosis needs technical accuracy at 45%. Applying the same weights across all tasks produces misleading scores. |
| Safety as a hard gate | A resolution response with SF=FAIL should score 0 regardless of how technically accurate it is. The gate enforces this mathematically. |
| Self-enhancement bias | Gemma scored itself +0.70 above Claude on average. Self-evaluation is calibrated for structured tasks; cross-model evaluation is required for safety and judgment-heavy dimensions. |
| LLM-as-judge reliability | Both judges agreed on unambiguous cases (triage, communication). Disagreement clustered on cases requiring safety judgment and subjective completeness assessment. |
| Parse error as a failure mode | Judge output parsing is part of the evaluation pipeline. A parse error that silently zeros a score is as dangerous as a wrong score. |

---


## Full Code

```python title="itsm_scenarios.py"
--8<-- "06-evaluation/code/itsm_scenarios.py"
```

```python title="03_itsm_benchmark.py"
--8<-- "06-evaluation/code/03_itsm_benchmark.py"
```

```python title="04_itsm_cross_model_eval.py"
--8<-- "06-evaluation/code/04_itsm_cross_model_eval.py"
```

## Next

`07-production-enterprise/` — self-hosted inference with audit logging, rate limiting, guardrails, and multi-tenant isolation. The ITSM evaluation framework built here becomes the quality gate in the production inference server.
