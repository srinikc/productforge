# Output Guardrails + Governance Cards + Provenance — Design (BI-0219)

## Goal
AI products need **output-level** safety + governance: guardrails/moderation on LLM + media output (toxicity,
PII, NSFW, prompt-injection) with configurable block/flag/redact; auto-emitted **model/data cards**;
**C2PA Content Credentials** provenance for generated media; and **governance checkpoints** (NIST AI RMF /
EU AI Act) surfaced in compliance + BOM. Wired into the pipeline, fail-closed, scalable, API-first.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Output write path | agents produce text/media → artifacts (`artifact_store`), media QA at validate | pre/post guardrails around output | extend |
| Secret redaction | `core/log_router.redact` (numeric-safe) | reuse for redact action | reuse |
| Media QA | `core/media_qa.validate_asset/validate_project` (validate stage) | + NSFW/guardrail checks | extend |
| BOM | `core/bom.build/write` (stage 9, `artifacts/9 - Package/BOM.json`) | include cards + governance | extend |
| Compliance | `core/compliance_check` (`ComplianceChecker`) | + governance checkpoints | extend |
| Model/license facts | `config/model-catalog.json`, `config/generators.json` (license) | model/data card source | reuse |
| Aggregation | `core/result_aggregator` (BI-PF-0277) | carry guardrail status in results | reuse |

**Blast radius:** new `core/guardrails.py` (owner of `config/guardrail-policy.json` + `Guardrail-Report`
artifact + C2PA tag helper), thin hooks at the output-write boundary + media QA + stage-9 packaging, BOM/
compliance extension, API. No new state store (policy is config; report is derived).

## Design decisions (modular, 1 truth per concern)
- **New `core/guardrails.py`** — single owner of output guardrails + governance:
  - **Policy (`config/guardrail-policy.json`, versioned)**: rules per channel (`text`|`image`|`audio`|`video`)
    with `categories` (toxicity, pii, nsfw, prompt_injection, secret) and `action ∈ allow|flag|block|redact`,
    per-category severity + thresholds; configurable, deterministic.
  - **`check(content, channel, *, meta) -> {action, findings[], redacted, blocked}`**: rule-based detectors
    (regex/keyword + reuse `log_router.redact` for secrets/PII patterns); **fail-closed**: unknown channel or
    detector error ⇒ `flag` (never silent allow for high-severity categories). Action precedence
    `block > redact > flag > allow`.
  - **`enforce(content, channel)`**: apply the resolved action — `block` raises/returns blocked (output never
    lands), `redact` returns sanitized content, `flag` returns content + findings for the report.
  - **Model cards + data cards**: `model_card(model)` / `data_card(dataset)` built from `model-catalog`/
    `generators` (license, provider, intended use, limits, provenance) — auto-emitted into the package.
  - **Provenance (C2PA / Content Credentials)**: `c2pa_manifest(asset, sources)` → a standards-shaped
    claim (assets, actions, ingredients, generator, `c2pa.ai_generative_training_and_use` assertion);
    attached to generated media metadata + carried through packaging. (Signature-ready manifest; no external
    signing dependency — a local digest "soft binding" + manifest is emitted.)
  - **Governance mapping**: `governance_checkpoints()` → NIST AI RMF (Govern/Map/Measure/Manage) + EU AI Act
    (risk tier, transparency, data governance) checkpoints with status, for compliance/BOM.
  - **`report(project_dir, findings)`**: single writer `artifacts/…/Guardrail-Report.json`.
- **Hooks (thin, at boundaries):**
  - **Output write:** before persisting agent text, `enforce(text, "text")`; blocked ⇒ artifact not written +
    an issue raised; flagged ⇒ write + record finding; redacted ⇒ write sanitized.
  - **Media QA (validate):** extend `media_qa` to call `guardrails.check(asset_meta, "image/video/…")` and
    attach `c2pa_manifest` for generated media.
  - **Stage 9 packaging:** `bom.write` includes `model_cards`, `data_cards`, `provenance`, `governance`;
    `compliance_check` surfaces governance checkpoints.
- **Reuse, never fork:** redaction via `log_router.redact`; license facts from existing catalogs; BOM/compliance
  extended (not duplicated). One policy file, one writer for the report.
- **Fail-closed:** high-severity categories never silently pass; detector errors ⇒ flag; policy malformed ⇒
  refuse (block) with a clear reason.
- **API-first:** `GET /api/v1/guardrails/policy`, `GET /api/v1/guardrails/report?project=`,
  `POST /api/v1/guardrails/check` (ad-hoc), `GET /api/v1/governance/checkpoints`.
- **Scalable:** rule-based + bounded regex; no network for checks; signed manifest is local.

## Plan (branch `feature/bi-0219-guardrails`)
1. `docs/GUARDRAILS-DESIGN.md` (this file).
2. `config/guardrail-policy.json` (versioned; channels/categories/actions + governance map) + register store.
3. `core/guardrails.py` — `check`/`enforce`, `model_card`/`data_card`, `c2pa_manifest`, `governance_checkpoints`,
   `report`/`load_report`.
4. Hooks: output-write enforce; `media_qa` guardrail + C2PA; `bom.build` cards/provenance/governance;
   `compliance_check` governance checkpoints.
5. `dashboard/api/app.py` — `/api/v1/guardrails*`, `/api/v1/governance/checkpoints`.
6. Tests `test_guardrails.py` — allow/flag/block/redact per category; block prevents write; redact sanitizes;
   fail-closed high severity; policy validation; model/data card fields; c2pa manifest shape; governance
   checkpoints; BOM includes cards/governance; API shape.
7. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
8. Merge; close `BI-0219` through the loop.

## Acceptance
- A disallowed generation is **blocked/flagged before it reaches an artifact**; policy is configurable.
- A shipped product carries model/data cards + (media) C2PA provenance; packaging (BOM) includes them.
- Governance checkpoints appear in compliance/BOM output.
- `precheck` PASS; fail-closed; one writer; reuses redaction/catalog facts.

## Out of scope (tracked separately)
Real third-party moderation APIs, actual C2PA cryptographic signing/CA trust chain (manifest emitted locally),
dataset-level lineage graphs.
