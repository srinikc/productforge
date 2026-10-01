# AI-Era Operations Layer — Design (BI-0218)

> Status: **design only / parked**. Written for reference; implementation deferred (come back later).
> To implement: follow the plan below, then classify this doc in `scripts/dev/gen_docs_index.py` (or the
> docs-fresh precheck will flag it STALE) before running `scripts/dev/precheck.py`.

## Goal
Traditional SDLC is insufficient for AI products (non-deterministic outputs, prompt/model versions, drift,
feedback). Add the **AI-era lifecycle layer**: (1) **evals** with thresholds as a release gate, (2)
**prompt/model/agent version registry** + artifact version stamping, (3) **feedback → eval set → change
request** loop, (4) **model-quality observability** (drift/hallucination/toxicity + cost/latency). Wired into
verify stages, quality gate, OTel GenAI, and the CLI/dashboard — scalable, fail-closed, API-first.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Verify gates | `core/code_quality_gate` (`gate_agent_output`), `core/quality_metrics`, verify stages 5–7 | add eval gate alongside | extend |
| Agent/prompt versions | cards carry `version`/`spec_version`; no registry/stamping | version registry + per-artifact stamp | new |
| Change requests | `core/change_spec.ensure/render` (change item → spec) | feedback opens a change item | reuse |
| Quality obs | OTel GenAI (`core/otel`), `product_analytics`, `finops`, `observer` | model-quality metrics surfaced | reuse |
| Aggregation | `core/result_aggregator` (BI-PF-0277) | eval evidence folded in | reuse |
| Guardrails | `core/guardrails` (BI-0219) | toxicity findings feed quality | reuse |

**Blast radius:** new `core/aiops.py` (owner of `config/evals.json` + `data/aiops-versions.json`), a hook in
`code_quality_gate`/verify stage, OTel metric emission, API. Two new stores (evals config + version registry),
one derived `Eval-Report` artifact.

## Design decisions (modular, 1 truth per concern)
- **New `core/aiops.py`** — single owner of evals + versioning + feedback:
  - **Evals (`config/evals.json`, versioned):** named eval sets → `{cases[], metric, threshold, gate}`
    (pass/fail). `run_evals(project_dir, sets=None) -> {results[], passed, blocked}` — deterministic,
    threshold-based; a set below threshold ⇒ `passed=False`; **release gate**: any gating set failing blocks.
    Reuses `result_aggregator` for multi-source eval evidence and `guardrails` for toxicity metrics.
  - **Version registry (`data/aiops-versions.json`):** `record_version(kind ∈ prompt|model|agent, name,
    version, meta)`; `stamp(artifact_meta, prompt=, model=, agent=)` records **which versions produced an
    artifact** (prompt+model+agent) into the artifact metadata / a sidecar; `versions_for(artifact)`.
    A/B: `assign_variant(name, key)` deterministic bucketing + `record_version(...,variant=)`.
  - **Feedback loop:** `add_feedback(project, {source, artifact, rating, text, category})` →
    `promote_to_eval_set(feedback_ids, name)` (turn feedback into eval cases) →
    `open_change_request(project, feedback_id)` (calls `change_spec.ensure` on a new backlog change item).
  - **Quality observability:** `quality_metrics(project_dir)` → drift/hallucination(proxy)/toxicity +
    cost/latency, derived from eval results + `cost_model`/`otel`/`guardrails`; emitted as OTel GenAI spans
    (best-effort) and written to the **Eval-Report** artifact (single writer).
- **Reuse, never fork:** eval evidence via `result_aggregator`; toxicity via `guardrails`; change requests via
  `change_spec`/`backlog`; metrics via `otel`. No duplicate gate logic — `code_quality_gate` calls aiops.
- **Wired where decisions happen (no new stage):**
  - **Verify stages 5–7:** run `run_evals`; a failing gating set blocks the quality gate (release blocked).
  - **`code_quality_gate.gate_agent_output`:** appends eval-gate outcome when available (advisory until
    enforced at verify).
  - **Artifact write:** stamp prompt/model/agent versions onto produced artifacts.
- **Fail-closed:** unknown metric/threshold misconfig ⇒ gate fails; missing eval set for a gating eval ⇒
  blocked; never silently pass a regression.
- **API-first:** `GET /api/v1/evals`, `POST /api/v1/evals/run`, `GET /api/v1/aiops/versions`,
  `GET /api/v1/aiops/quality?project=`, `POST /api/v1/aiops/feedback`,
  `POST /api/v1/aiops/feedback/{id}/change-request`.
- **Scalable:** deterministic thresholds; bounded eval cases; one JSONL/JSON artifact per project.

## Plan (branch `feature/bi-0218-aiops`)
1. `docs/AIOPS-DESIGN.md` (this file).
2. `config/evals.json` (versioned; seed a small smoke eval set) + `data/aiops-versions.json` — register both.
3. `core/aiops.py` — `run_evals`, `record_version`, `stamp`, `versions_for`, `assign_variant`,
   `add_feedback`, `promote_to_eval_set`, `open_change_request`, `quality_metrics`, `write_report`/`load_report`.
4. Wire: verify stage (5–7) eval gate; `code_quality_gate` advisory; artifact version stamping; OTel emit.
5. `dashboard/api/app.py` — `/api/v1/evals*`, `/api/v1/aiops*`.
6. Tests `test_aiops.py` — eval threshold pass/fail + gate blocks; version stamping + lookup; A/B deterministic
   bucketing; feedback → eval set promotion; feedback → change request link; quality metrics shape;
   fail-closed misconfig.
7. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
8. Merge; close `BI-0218` through the loop.

## Acceptance
- Verify stages run evals with thresholds (pass/fail recorded); a regression blocks release.
- Every AI artifact records prompt+model+agent versions; a feedback item opens a change request.
- Operate/API view exposes model-quality + cost/latency metrics.
- `precheck` PASS; fail-closed; single writers; reuses aggregator/guardrails/change_spec/otel.

## Out of scope (tracked separately)
Live online A/B traffic splitting, real hallucination model, dashboard visualisations (BI-0149),
dataset-level eval authoring UI.
