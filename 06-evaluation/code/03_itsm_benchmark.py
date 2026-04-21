"""
ITSM Benchmark — Gemma judges Gemma (self-evaluation)

Model under test : gemma4:26b
Judge            : gemma4:26b
Scenarios        : 12 (2 per task type)

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

Results saved to /tmp/itsm_self_eval.json
"""

import json
import time
import importlib.util
import requests
from pathlib import Path

# Load shared scenarios
_path = Path(__file__).parent / "itsm_scenarios.py"
_spec = importlib.util.spec_from_file_location("itsm_scenarios", _path)
_mod  = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
SCENARIOS     = _mod.SCENARIOS
WEIGHTS       = _mod.WEIGHTS
QUALITY_GATES = _mod.QUALITY_GATES

OLLAMA_URL         = "http://localhost:11434/api/chat"
MODEL_UNDER_TEST   = "gemma4:26b"
JUDGE_MODEL        = "gemma4:26b"

# ------------------------------------------------------------------
# PRIORITY DEFINITIONS — injected into every judge prompt
# ------------------------------------------------------------------

PRIORITY_CONTEXT = """
ITIL Priority Definitions:
P1 — Complete service outage, >50% users affected, or direct revenue/security impact. Response: 15 min.
P2 — Major degradation, >25% users affected, workaround unavailable. Response: 1 hour.
P3 — Partial degradation, workaround available, limited user impact. Response: 4 hours.
P4 — Minimal impact, no user-facing disruption. Response: next business day.
""".strip()

# ------------------------------------------------------------------
# JUDGE PROMPTS — one per task type
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
# OLLAMA HELPERS
# ------------------------------------------------------------------

def call_ollama(model: str, prompt: str, max_tokens: int = 1000) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": max_tokens, "num_ctx": 8192},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=180)
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


def ask_model(incident: str) -> str:
    return call_ollama(MODEL_UNDER_TEST, incident, max_tokens=800)


def parse_judge_output(raw: str) -> dict:
    try:
        cleaned = raw.strip().strip("`").lstrip("json").strip()
        start   = cleaned.index("{")
        end     = cleaned.rindex("}") + 1
        return json.loads(cleaned[start:end])
    except Exception:
        return {"_parse_error": raw[:120]}


# ------------------------------------------------------------------
# SCORING
# ------------------------------------------------------------------

def compute_weighted_score(dimensions: dict, task_type: str) -> tuple[float, str]:
    """Returns (weighted_score, flag) where flag is '' / 'WARN' / 'FAIL'."""
    weights = WEIGHTS[task_type]
    sf      = dimensions.get("SF", {})
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

    raw        = call_ollama(JUDGE_MODEL, prompt, max_tokens=600)
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
    print(f"  ITSM BENCHMARK — Self-Evaluation (Gemma judges Gemma)")
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


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------

if __name__ == "__main__":
    print(f"ITSM Benchmark — Self-Evaluation")
    print(f"Model under test : {MODEL_UNDER_TEST}")
    print(f"Judge            : {JUDGE_MODEL}")
    print(f"Scenarios        : {len(SCENARIOS)}\n")

    results     = []
    total_start = time.perf_counter()

    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"[{i:02d}/{len(SCENARIOS)}] {scenario['id']} — {scenario['title']}")

        response = ask_model(scenario["incident"])
        print(f"  Response: {response[:90]}...")

        judgment = run_judge(scenario, response)
        weighted = judgment["weighted_score"]
        flag     = judgment["flag"]

        print(f"  Score   : {weighted:.2f}/5  {('⚠ ' + flag) if flag else ''}")

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

    output = {
        "judge":            JUDGE_MODEL,
        "model_under_test": MODEL_UNDER_TEST,
        "elapsed_s":        elapsed,
        "results":          results,
    }
    with open("/tmp/itsm_self_eval.json", "w") as f:
        json.dump(output, f, indent=2)
    print("Results saved to /tmp/itsm_self_eval.json")
