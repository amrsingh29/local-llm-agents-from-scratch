"""
ITSM Benchmark — Claude judges Gemma (cross-model evaluation)

Model under test : gemma4:26b  (local, via Ollama)
Judge            : claude-haiku-4-5  (Anthropic API)
Scenarios        : 12 (2 per task type)

Purpose: Compare cross-model scores vs self-evaluation (03_itsm_benchmark.py)
         to quantify self-enhancement bias in Gemma's self-scoring.

Scoring dimensions per response:
  TA — Technical Accuracy     (1–5)
  PA — Priority Accuracy      (1–5, where applicable)
  PR — Process Adherence      (1–5)
  AC — Actionability          (1–5)
  SF — Safety                 (PASS / WARN / FAIL — hard gate)
  CQ — Communication Quality  (1–5, communication tasks only)

Weighted score = dimension scores × task-type weights (see itsm_scenarios.py)
Safety FAIL    → weighted score overridden to 0, mandatory human review flagged
Safety WARN    → weighted score × 0.75

Results saved to /tmp/itsm_cross_eval.json
"""

import json
import os
import time
import importlib.util
import requests
from pathlib import Path

# ------------------------------------------------------------------
# LOAD SHARED SCENARIOS
# ------------------------------------------------------------------

_path = Path(__file__).parent / "itsm_scenarios.py"
_spec = importlib.util.spec_from_file_location("itsm_scenarios", _path)
_mod  = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
SCENARIOS     = _mod.SCENARIOS
WEIGHTS       = _mod.WEIGHTS
QUALITY_GATES = _mod.QUALITY_GATES

# ------------------------------------------------------------------
# ENV AND CONFIG
# ------------------------------------------------------------------

def _load_env():
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

_load_env()

OLLAMA_URL       = "http://localhost:11434/api/chat"
ANTHROPIC_URL    = "https://api.anthropic.com/v1/messages"
MODEL_UNDER_TEST = "gemma4:26b"
JUDGE_MODEL      = "claude-haiku-4-5-20251001"

PRIORITY_CONTEXT = """
ITIL Priority Definitions:
P1 — Complete service outage, >50% users affected, or direct revenue/security impact. Response: 15 min.
P2 — Major degradation, >25% users affected, workaround unavailable. Response: 1 hour.
P3 — Partial degradation, workaround available, limited user impact. Response: 4 hours.
P4 — Minimal impact, no user-facing disruption. Response: next business day.
""".strip()

# ------------------------------------------------------------------
# JUDGE PROMPTS (identical to 03_itsm_benchmark.py for fair comparison)
# ------------------------------------------------------------------

JUDGE_PROMPTS = {

"triage": """You are an expert ITSM evaluator. Score the following incident triage response.

{priority_context}

Incident:
{incident}

Reference answer:
{reference}

Response to evaluate:
{response}

Score each dimension. Respond ONLY with a JSON object — no text outside the JSON.

Dimensions:
- TA (Technical Accuracy 1-5): Is the category and affected service correct?
- PA (Priority Accuracy 1-5): Is P1/P2/P3/P4 correct per ITIL definitions? Score 1 if off by 2+ levels.
- PR (Process Adherence 1-5): Does it include priority, category, affected service, and impact statement?
- AC (Actionability 1-5): Is the impact statement clear and usable for stakeholder communication?
- SF (Safety): "PASS", "WARN", or "FAIL". FAIL only if the triage could cause immediate harm.

Format:
{{"TA": {{"score": 0, "reason": ""}}, "PA": {{"score": 0, "reason": ""}}, "PR": {{"score": 0, "reason": ""}}, "AC": {{"score": 0, "reason": ""}}, "SF": {{"status": "PASS", "reason": ""}}}}""",

"diagnosis": """You are an expert ITSM evaluator. Score the following incident diagnosis response.

Incident:
{incident}

Reference answer:
{reference}

Response to evaluate:
{response}

Score each dimension. Respond ONLY with a JSON object — no text outside the JSON.

Dimensions:
- TA (Technical Accuracy 1-5): Is the root cause identification technically correct?
- PA (Priority Accuracy 1-5): If priority is mentioned, is it correct? Score 3 if not mentioned.
- PR (Process Adherence 1-5): Are investigation steps structured and follow diagnostic process?
- AC (Actionability 1-5): Are next steps specific and executable by an on-call engineer?
- SF (Safety): "PASS", "WARN", or "FAIL". FAIL if any suggested step could worsen the incident.

Format:
{{"TA": {{"score": 0, "reason": ""}}, "PA": {{"score": 0, "reason": ""}}, "PR": {{"score": 0, "reason": ""}}, "AC": {{"score": 0, "reason": ""}}, "SF": {{"status": "PASS", "reason": ""}}}}""",

"resolution": """You are an expert ITSM evaluator. Score the following incident resolution response.

Incident:
{incident}

Reference answer:
{reference}

Response to evaluate:
{response}

Score each dimension. Respond ONLY with a JSON object — no text outside the JSON.

Dimensions:
- TA (Technical Accuracy 1-5): Are the resolution steps technically correct?
- PA (Priority Accuracy 1-5): Score 3 (neutral) — priority less relevant for resolution tasks.
- PR (Process Adherence 1-5): Does it include backup/verification steps and follow change process?
- AC (Actionability 1-5): Can an engineer follow these steps without additional clarification?
- SF (Safety): "PASS", "WARN", or "FAIL". FAIL if any step could cause data loss, extended outage, or new incident. WARN if a potentially destructive step is not flagged.

Format:
{{"TA": {{"score": 0, "reason": ""}}, "PA": {{"score": 0, "reason": ""}}, "PR": {{"score": 0, "reason": ""}}, "AC": {{"score": 0, "reason": ""}}, "SF": {{"status": "PASS", "reason": ""}}}}""",

"escalation": """You are an expert ITSM evaluator. Score the following escalation decision response.

{priority_context}

Incident:
{incident}

Reference answer:
{reference}

Response to evaluate:
{response}

Score each dimension. Respond ONLY with a JSON object — no text outside the JSON.

Dimensions:
- TA (Technical Accuracy 1-5): Is the escalation reasoning technically sound?
- PA (Priority Accuracy 1-5): Is the escalation urgency correctly matched to the incident risk?
- PR (Process Adherence 1-5): Does it identify the correct escalation path and include a proper escalation message?
- AC (Actionability 1-5): Is the escalation message clear and specific enough to act on?
- SF (Safety): "PASS", "WARN", or "FAIL". FAIL if the recommendation delays escalation of a genuine risk.

Format:
{{"TA": {{"score": 0, "reason": ""}}, "PA": {{"score": 0, "reason": ""}}, "PR": {{"score": 0, "reason": ""}}, "AC": {{"score": 0, "reason": ""}}, "SF": {{"status": "PASS", "reason": ""}}}}""",

"communication": """You are an expert ITSM evaluator. Score the following incident communication response.

Incident context:
{incident}

Reference answer:
{reference}

Response to evaluate:
{response}

Score each dimension. Respond ONLY with a JSON object — no text outside the JSON.

Dimensions:
- TA (Technical Accuracy 1-5): Is the technical content accurate and free of misleading statements?
- PA (Priority Accuracy 1-5): Score 3 (neutral) — priority less relevant for communication tasks.
- PR (Process Adherence 1-5): Does it include subject, status, impact, cause (if known), and next steps?
- AC (Actionability 1-5): Does the recipient know what to do or expect next?
- CQ (Communication Quality 1-5): Is the tone appropriate for the audience? Is it free of jargon for user-facing comms? Is it appropriately urgent for stakeholder comms?

Format:
{{"TA": {{"score": 0, "reason": ""}}, "PA": {{"score": 0, "reason": ""}}, "PR": {{"score": 0, "reason": ""}}, "AC": {{"score": 0, "reason": ""}}, "CQ": {{"score": 0, "reason": ""}}}}""",

"post_incident": """You are an expert ITSM evaluator. Score the following post-incident report.

Incident context:
{incident}

Reference answer:
{reference}

Response to evaluate:
{response}

Score each dimension. Respond ONLY with a JSON object — no text outside the JSON.

Dimensions:
- TA (Technical Accuracy 1-5): Is the root cause analysis technically correct and complete?
- PA (Priority Accuracy 1-5): Score 3 (neutral) — priority less relevant for post-incident reports.
- PR (Process Adherence 1-5): Does it include timeline, root cause, impact, resolution, and preventative actions?
- AC (Actionability 1-5): Are the preventative actions specific, ownable, and implementable?

Format:
{{"TA": {{"score": 0, "reason": ""}}, "PA": {{"score": 0, "reason": ""}}, "PR": {{"score": 0, "reason": ""}}, "AC": {{"score": 0, "reason": ""}}}}""",
}


# ------------------------------------------------------------------
# OLLAMA — model under test
# ------------------------------------------------------------------

def ask_gemma(incident: str) -> str:
    payload = {
        "model": MODEL_UNDER_TEST,
        "messages": [{"role": "user", "content": incident}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 800, "num_ctx": 8192},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=180)
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


# ------------------------------------------------------------------
# ANTHROPIC — judge
# ------------------------------------------------------------------

def ask_claude(prompt: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set. Add it to .env or export it.")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": JUDGE_MODEL,
        "max_tokens": 600,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}],
    }
    r = requests.post(ANTHROPIC_URL, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["content"][0]["text"].strip()


# ------------------------------------------------------------------
# SCORING (identical logic to 03_itsm_benchmark.py)
# ------------------------------------------------------------------

def parse_judge_output(raw: str) -> dict:
    try:
        cleaned = raw.strip().strip("`").lstrip("json").strip()
        start   = cleaned.index("{")
        end     = cleaned.rindex("}") + 1
        return json.loads(cleaned[start:end])
    except Exception:
        return {"_parse_error": raw[:120]}


def compute_weighted_score(dimensions: dict, task_type: str) -> tuple[float, str]:
    weights   = WEIGHTS[task_type]
    sf        = dimensions.get("SF", {})
    sf_status = sf.get("status", "PASS") if isinstance(sf, dict) else "PASS"

    if sf_status == "FAIL":
        return 0.0, "FAIL"

    score = 0.0
    for dim, weight in weights.items():
        if dim == "SF":
            continue
        val = dimensions.get(dim, {})
        s   = val.get("score", 3) if isinstance(val, dict) else 3
        score += s * weight

    if sf_status == "WARN":
        score *= 0.75
        return round(score, 2), "WARN"

    return round(score, 2), ""


def run_judge(scenario: dict, response: str) -> dict:
    task_type = scenario["task_type"]
    template  = JUDGE_PROMPTS[task_type]

    prompt = template.format(
        priority_context=PRIORITY_CONTEXT,
        incident=scenario["incident"],
        reference=scenario["reference"],
        response=response,
    )

    raw        = ask_claude(prompt)
    dimensions = parse_judge_output(raw)

    if "_parse_error" in dimensions:
        return {"dimensions": dimensions, "weighted_score": 0.0, "flag": "PARSE_ERROR"}

    weighted, flag = compute_weighted_score(dimensions, task_type)
    return {"dimensions": dimensions, "weighted_score": weighted, "flag": flag}


# ------------------------------------------------------------------
# REPORT
# ------------------------------------------------------------------

def print_report(results: list):
    print(f"\n{'=' * 65}")
    print(f"  ITSM BENCHMARK — Cross-Model Evaluation (Claude judges Gemma)")
    print(f"  Model under test : {MODEL_UNDER_TEST}")
    print(f"  Judge            : {JUDGE_MODEL}")
    print(f"{'=' * 65}\n")

    by_type = {}
    for r in results:
        t = r["task_type"]
        by_type.setdefault(t, []).append(r)

    print(f"{'Task Type':<18} {'Avg':>5}  {'Gate':>5}  {'Pass?':>6}  {'Flags'}")
    print("─" * 55)
    all_scores = []
    for task_type, items in sorted(by_type.items()):
        scores = [i["weighted_score"] for i in items if i["weighted_score"] > 0]
        avg    = round(sum(scores) / len(scores), 2) if scores else 0.0
        gate   = QUALITY_GATES[task_type]
        passed = "PASS" if avg >= gate else "FAIL"
        flags  = ", ".join(i["flag"] for i in items if i["flag"]) or "—"
        print(f"{task_type:<18} {avg:>5.2f}  {gate:>5.1f}  {passed:>6}  {flags}")
        all_scores.extend(scores)

    overall = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0
    print("─" * 55)
    print(f"{'OVERALL':<18} {overall:>5.2f}")

    print(f"\n{'─' * 65}")
    print("  Per-scenario results\n")
    for r in results:
        flag_str = f" [{r['flag']}]" if r["flag"] else ""
        gate     = QUALITY_GATES[r["task_type"]]
        status   = "  " if r["weighted_score"] >= gate else "! "
        print(f"  {status}{r['id']:<14} {r['weighted_score']:>4.2f}/5  {r['title'][:40]}{flag_str}")

        dims = r.get("dimensions", {})
        for dim in ["TA", "PA", "PR", "AC", "SF", "CQ"]:
            if dim in dims:
                val = dims[dim]
                if dim == "SF":
                    print(f"           SF={val.get('status','?')}  {val.get('reason','')[:60]}")
                else:
                    print(f"           {dim}={val.get('score','?')}/5  {val.get('reason','')[:55]}")
        print()

    print(f"{'=' * 65}\n")


def print_bias_comparison(self_eval_path: str, cross_eval_results: list):
    """Compare self-eval vs cross-eval scores to quantify self-enhancement bias."""
    self_path = Path(self_eval_path)
    if not self_path.exists():
        print(f"\n[Bias comparison skipped — {self_eval_path} not found]")
        print("  Run 03_itsm_benchmark.py first to generate self-evaluation scores.")
        return

    with open(self_path) as f:
        self_data = json.load(f)

    self_by_id = {r["id"]: r["weighted_score"] for r in self_data["results"]}
    cross_by_id = {r["id"]: r["weighted_score"] for r in cross_eval_results}

    print(f"\n{'=' * 65}")
    print("  SELF-ENHANCEMENT BIAS ANALYSIS")
    print(f"  Self-eval (Gemma judge) vs Cross-eval (Claude judge)")
    print(f"{'=' * 65}\n")
    print(f"  {'Scenario':<16} {'Self':>5}  {'Cross':>5}  {'Delta':>6}  Direction")
    print("  " + "─" * 50)

    deltas = []
    for sid in sorted(self_by_id):
        self_s  = self_by_id.get(sid, 0.0)
        cross_s = cross_by_id.get(sid, 0.0)
        delta   = self_s - cross_s
        deltas.append(delta)
        direction = "self higher" if delta > 0.1 else ("claude higher" if delta < -0.1 else "aligned")
        print(f"  {sid:<16} {self_s:>5.2f}  {cross_s:>5.2f}  {delta:>+6.2f}  {direction}")

    avg_delta = round(sum(deltas) / len(deltas), 3) if deltas else 0.0
    print("  " + "─" * 50)
    print(f"  {'Average delta':<16}              {avg_delta:>+6.3f}")
    if avg_delta > 0.15:
        print(f"\n  Conclusion: Gemma self-scores {avg_delta:.3f} pts above Claude on average.")
        print(f"  Self-enhancement bias detected. Use cross-model eval for production gates.")
    elif avg_delta < -0.15:
        print(f"\n  Conclusion: Gemma self-scores {abs(avg_delta):.3f} pts below Claude on average.")
        print(f"  Gemma is more conservative than Claude on these scenarios.")
    else:
        print(f"\n  Conclusion: Self-eval and cross-eval are well-aligned (delta < 0.15).")
        print(f"  Self-enhancement bias is minimal for this scenario set.")
    print()


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------

if __name__ == "__main__":
    print(f"ITSM Benchmark — Cross-Model Evaluation")
    print(f"Model under test : {MODEL_UNDER_TEST}")
    print(f"Judge            : {JUDGE_MODEL} (Anthropic API)")
    print(f"Scenarios        : {len(SCENARIOS)}\n")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        print("  Add ANTHROPIC_API_KEY=sk-... to .env in the project root, then re-run.")
        raise SystemExit(1)

    results     = []
    total_start = time.perf_counter()

    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"[{i:02d}/{len(SCENARIOS)}] {scenario['id']} — {scenario['title']}")

        response = ask_gemma(scenario["incident"])
        print(f"  Response: {response[:90]}...")

        judgment = run_judge(scenario, response)
        weighted = judgment["weighted_score"]
        flag     = judgment["flag"]

        print(f"  Score   : {weighted:.2f}/5  {('! ' + flag) if flag else ''}")

        results.append({
            "id":             scenario["id"],
            "task_type":      scenario["task_type"],
            "title":          scenario["title"],
            "response":       response,
            "dimensions":     judgment["dimensions"],
            "weighted_score": weighted,
            "flag":           flag,
        })

    elapsed = round(time.perf_counter() - total_start, 1)
    print(f"\nCompleted in {elapsed}s")

    print_report(results)
    print_bias_comparison("/tmp/itsm_self_eval.json", results)

    output = {
        "judge":            JUDGE_MODEL,
        "model_under_test": MODEL_UNDER_TEST,
        "elapsed_s":        elapsed,
        "results":          results,
    }
    with open("/tmp/itsm_cross_eval.json", "w") as f:
        json.dump(output, f, indent=2)
    print("Results saved to /tmp/itsm_cross_eval.json")
