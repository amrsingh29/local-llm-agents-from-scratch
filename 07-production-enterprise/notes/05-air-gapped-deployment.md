# Air-Gapped AI Deployment

## What Air-Gapped Means

An air-gapped environment has no external network connectivity. No internet access. No cloud APIs. No package registries. Sometimes no DNS resolution outside the internal network.

This is the standard for defence, intelligence, and some financial and healthcare environments where the data being processed is too sensitive to route near any external network boundary — even encrypted. The question is not "is HTTPS secure enough?" The answer is "the network path does not exist."

Running an LLM in this environment is entirely possible with the local inference stack built in this series. Every component can be pre-staged before the network is severed.

---

## What Calls Home (and How to Stop It)

Before staging an air-gapped deployment, identify every component that makes external network calls by default.

### Ollama

**Default behaviour:** Ollama sends anonymous telemetry to an Anthropic-operated endpoint. It also checks for model updates when pulling.

**In air-gapped use:**
```bash
# Disable telemetry
export OLLAMA_NO_ANALYTICS=true

# Model weights must be pre-pulled before disconnecting
ollama pull gemma4:26b
# Weights are cached at ~/.ollama/models/ — this directory is the model store
```

Once the model is pulled and cached, Ollama runs fully offline. The `~/.ollama/models/` directory can be copied to the air-gapped machine via secure transfer.

### Python Dependencies

```bash
# On a connected machine — download all wheels
pip download fastapi uvicorn requests -d ./wheels/

# Transfer wheels/ to air-gapped machine via removable media
# Install on air-gapped machine
pip install --no-index --find-links ./wheels/ fastapi uvicorn requests
```

The packages used in this series (`fastapi`, `uvicorn`, `requests`, `sqlite3`) are either standard library or have no transitive dependencies that require external access at runtime.

### SQLite

SQLite is built into Python's standard library. No installation required. No external calls. The audit log database file is entirely local.

---

## Pre-Staging Checklist

Complete these steps on a connected machine before the network is severed:

**Model weights:**
- [ ] `ollama pull gemma4:26b` — verify weights in `~/.ollama/models/`
- [ ] `ollama pull gemma4:e2b` (optional — for the scope classifier from Phase 4)
- [ ] Copy `~/.ollama/models/` to air-gapped machine via approved transfer medium

**Runtime dependencies:**
- [ ] `pip download fastapi uvicorn requests -d ./wheels/`
- [ ] Copy `wheels/` directory to air-gapped machine

**Configuration:**
- [ ] Set `OLLAMA_NO_ANALYTICS=true` in the service environment
- [ ] Verify `OLLAMA_HOST=0.0.0.0:11434` is set if the server needs to be reachable on the local network (not just localhost)

**Application code:**
- [ ] All Python scripts from this series
- [ ] `.env` file with any local configuration (no external API keys in air-gapped deployment)

**Verification (on the air-gapped machine, before removing network):**
- [ ] `ollama serve` starts without error
- [ ] `curl http://localhost:11434/api/tags` returns the model list
- [ ] `python 01_concurrent_inference_server.py` starts without error
- [ ] `python 02_audit_logger.py` completes and writes `/tmp/audit.db`
- [ ] Disconnect network and repeat the two curl/python checks — they should still work

---

## The Complete Air-Gapped Stack

Once pre-staged, the production stack looks like this with zero external dependencies:

```
┌──────────────────────────────────────────────────────┐
│  Air-gapped machine (Apple M4 or on-premise server)  │
│                                                      │
│   ITSM tool / web client                            │
│         ↓                                           │
│   Guardrails layer    (03_guardrails.py)            │
│         ↓                                           │
│   Concurrent server   (01_concurrent_server.py)    │
│         ↓                                           │
│   Audit logger        (02_audit_logger.py)         │
│         ↓                                           │
│   Ollama              (localhost:11434)             │
│         ↓                                           │
│   gemma4:26b          (~/.ollama/models/)          │
│         ↓                                           │
│   SQLite audit DB     (/tmp/audit.db)              │
│                                                      │
│   ← No outbound network calls from any layer →      │
└──────────────────────────────────────────────────────┘
```

---

## What Changes in Air-Gapped vs Connected Deployment

| Concern | Connected deployment | Air-Gapped deployment |
|---------|---------------------|----------------------|
| Model updates | `ollama pull` fetches latest | Manual: pull on connected machine, transfer to air-gapped via approved medium |
| Dependency updates | `pip install --upgrade` | Same — stage on connected, transfer offline |
| Compliance export | Write to file, upload to SIEM | Write to file, export via approved medium |
| Model version pinning | Tag-based pull | Fixed model file in `~/.ollama/models/` — cannot change without a network-connected pull |
| Anthropic API (cross-eval) | Available | Not available — cross-model eval requires an internal judge model |

---

## Running a Cross-Model Judge Without Cloud Access

Phase 6's cross-model evaluation used Claude (Anthropic API) as the judge. In an air-gapped environment, you cannot reach the Anthropic API. The options are:

1. **Self-evaluation only** — use `gemma4:26b` as both model under test and judge. Carries self-enhancement bias (+0.70 from Phase 6 results) but is entirely local.

2. **A second local model as judge** — run a different model family locally (e.g., `llama3.1:8b` or `mistral:7b`) as the judge. This approximates cross-model evaluation without leaving the network.

3. **Human review for high-stakes responses** — for responses below the quality gate, flag them for human review rather than using an automated cross-model judge. This is the most defensible approach in a regulated environment.

---

## Security Considerations Specific to Air-Gapped Deployments

**Model provenance:** verify the checksum of the model weights before deployment. Ollama displays the model digest after pulling — record it and verify it matches the expected hash on the air-gapped machine.

```bash
# On connected machine after pull
ollama show gemma4:26b --modelfile | grep FROM
# Note the SHA256 digest

# Verify on air-gapped machine
ollama show gemma4:26b --modelfile | grep FROM
# Must match exactly
```

**Physical access controls:** the audit log database (`audit.db`) contains every prompt and response submitted to the model. On a machine storing sensitive operational data, this file requires the same physical and logical access controls as the source systems.

**Removable media hygiene:** the transfer path for model weights and dependencies is the highest-risk step. Use write-once media where possible. Verify checksums after transfer. Log the transfer in the same way you would log any privileged data movement.

---

## Key Takeaways

Running a production-grade, air-gapped AI inference system is achievable with the stack built in this series. The constraints are:

1. **Pre-staging is irreversible** — once the network is severed, you cannot pull new models or update dependencies. Stage everything in advance.
2. **Model updates require a process** — define how model updates are approved, staged, transferred, and deployed. This is change management, not software development.
3. **The audit log is a high-value asset** — it contains everything submitted to the model. Protect it accordingly.
4. **Cross-model evaluation is the main capability lost** — self-evaluation with known bias is the best available alternative without cloud access.

The local inference stack was built for this from the start. Every design decision in Phases 1–7 — local weights, SQLite logging, regex guardrails, file-based configuration — was made with offline capability as a first-class requirement.
