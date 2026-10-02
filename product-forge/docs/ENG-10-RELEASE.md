# ENG-10 — RELEASE Execution

**Phase:** ENG-10 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN-updated.md` (§24)
**Status:** Implemented (release gate + checks) — gate PASS
**Depends on:** ENG-6 (validation profiles), ENG-8 (merge gate), ENG-5 (evidence), ENG-3 (vcs)

## What this phase builds

ENG-10 qualifies a **release candidate**: it validates the **actual artifact intended for distribution**
(not merely source tests) across full regression, security, NFR/performance, packaging, SBOM/provenance,
deployment, and upgrade/rollback, then applies the **release gate** and produces **release evidence**.

```
core/release.py                 # release readiness + fail-closed gate; composes existing owners
api/routers/release.py          # GET /release/readiness, /release/gate, /release/evidence; POST /release/gate
scripts/dev/release_check.py    # gate (in precheck)
config/engineering-flow.json    # release step: planned -> partial
```

## Flow (§24)

```
release candidate → exact commit/tag → build → full regression → security → NFR/performance → packaging
  → SBOM/provenance → deployment validation → upgrade/rollback validation → release gates → release evidence
  → approved release
```

## Release gate

`core.release.gate(...)` builds a checklist (fail-closed); `readiness()` returns `can_release` + `unmet`:

| Item | Owner / source |
|---|---|
| `release_validation` | `core.validation_engine` RELEASE profile |
| `validation.security` / `.pr_gate` / `.tests` / `.verification` / `.quality_gate` | RELEASE profile checks |
| `build` | `core.build_manager` (build-info.json) |
| `packaging_bom` | `core.bom` (dependencies + licenses footprint) |
| `deployment` | `core.deploy_providers` (deployment record) |
| `merge_gate` | `core.merge_gate` (integration already green) |

Any item not `pass` ⇒ **release blocked** (no false green). The gate is **mechanical**: licensing/entitlement/
pricing decisions are human-governed and belong to REL-0.

## API / evidence

- `GET /api/v1/release/readiness` — decision (`can_release`, `unmet`); authenticated.
- `GET /api/v1/release/gate` — full checklist; authenticated.
- `GET /api/v1/release/evidence` — audit trail; authenticated.
- `POST /api/v1/release/gate` — evaluate (operator); optional `record: true` appends release evidence to
  `engineering/release-evidence.jsonl` (product_forge) or `<project>/release-evidence.jsonl`.

## 360° dependency check

- Reuses `validation_engine`, `bom`, `build_manager`, `deploy_providers`, `merge_gate`, `change_log`; **no new
  engine, no duplicate store**.
- Deployment is only `pass` when a deployment record proves it; otherwise `unknown` ⇒ blocked (fail-closed).
- New file `engineering/release-evidence.jsonl` is append-only, not a config store.

## Verification (executed)

```
python -m compileall -q api core scripts dashboard                # 0
python scripts/dev/wired_audit.py                                 # OK (unwired 0, naming 0)
python scripts/dev/release_check.py                               # OK (fail-closed, checklist, evidence)
python scripts/dev/precheck.py                                    # PASS
```

## Gate (§24)

| Criterion | Result |
|---|---|
| Exact commit validated (not just source) | ✅ target in RELEASE validation |
| Full regression + security + NFR | ✅ RELEASE profile |
| Packaging/provenance | ✅ BOM/build |
| Deployment + upgrade/rollback validation | ✅ deploy_providers (proven or blocked) |
| Release gate + evidence | ✅ `core.release` + `release-evidence.jsonl` |
| No false green | ✅ fail-closed checklist |
| API-first + wired + exercised | ✅ `/release/*` + gate + tests |
| ENG-0 flow updated | ✅ `release`: planned → partial |

**ENG-10 GATE: PASS.** Next: **REL-0 — Packaging / Licensing / Entitlement / Deployment**.
