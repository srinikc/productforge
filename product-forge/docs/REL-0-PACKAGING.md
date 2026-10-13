# REL-0 — Packaging / Licensing / Entitlement / Deployment

**Phase:** REL-0 of `PRODUCT_FORGE_MASTER_API_FIRST_ENGINEERING_FACTORY_E2E_EXECUTION_PLAN-updated.md` (§25)
**Status:** Implemented (edition manifest build/validate) — gate PASS
**Depends on:** API-4 (commercial architecture), ENG-10 (release), BOM/licensing/deploy owners

## What this phase builds

REL-0 produces and validates the **deployment-specific package manifest** for each edition, consuming the
canonical owners — it does **not** reimplement SBOM, entitlements or deployment, and makes **no commercial
decision** (licensing/pricing stays human-governed).

```
core/packaging.py              # edition manifest orchestration + fail-closed validation
api/routers/packaging.py       # GET /packaging/editions|/manifest|/validate ; POST /packaging/build
scripts/dev/packaging_check.py # gate (in precheck)
config/engineering-flow.json   # package_deploy step: planned -> partial
```

## EAP — the delivery/build manifest (A4, BI-PF-0397)

The **EAP (Edition/Artifact Package)** is the authoritative, **build-time** manifest of what goes into an
edition's package: it **composes** the canonical contracts (`component-manifest`, `runtime-profile`,
`deployment-profile`, `license-profile`, `entitlement-profile`, `bom`, `evidence`) + the edition's
**entitlement** (A2) + **SBOM/build provenance**, and declares the **EAP version + compatibility**. It is
**not shipped to customers** — it is how Product Forge decides package contents.

- Owner: `core/packaging.py` (`eap_build` / `eap_validate` / `eap_compatible` / `eap_write` / `eap_load`).
- Registry: `config/eap-registry.json` (known versions + compatibility ranges).
- API: `GET /packaging/eap`, `GET /packaging/eap/validate`, `GET /packaging/eap/registry`, `POST /packaging/eap` (operator).
- Fixture: `test-framework/tests/fixtures/contracts/sample-product/sample.eap`; tests `test-framework/tests/pipeline/test_eap.py`.
- Validation is **fail-closed** (unknown version / missing fields ⇒ invalid); compatibility = the EAP's declared
  ranges must cover the registry's current version. Concrete artifact **formats** (added by **A3**) ride in the EAP.

## Editions (§25)

```
community | enterprise | saas | on-prem | oem
```

| edition | licensing tier | deploy target | distribution |
|---|---|---|---|
| community | trial | local | open-source |
| enterprise | enterprise | kubernetes | commercial |
| saas | pro | docker | hosted |
| on-prem | enterprise | docker | commercial |
| oem | enterprise | command | white-label |

## Distinctions kept separate (§25)

`source` · `build` · `artifact` · `package` · `license` · `entitlement` · `configuration` ·
`deployment_target` · `runtime_policy`

## Generated / validated (delegated to owners)

| Output | Owner |
|---|---|
| package metadata, dependencies, SBOM, license metadata | `core.bom` |
| version + build provenance | `core.build_manager` |
| entitlement requirements per edition/tier | `core.licensing` |
| deployment manifest / runtime policy | `core.deploy_providers` |
| upgrade / rollback path, installation validation, footprint | `core.release_manager` |
| manifest persistence (single writer) | `core.packaging` -> `packaging-manifest.json` |

## Fail-closed validation

Every REL-0 distinction must be populated and coherent, and the edition entitlement must resolve; any gap =>
`valid: false` with `unmet`. No commercial value is decided by code.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/packaging/editions` | editions + distinctions |
| GET | `/api/v1/packaging/manifest?scope=&project=` | persisted manifest |
| GET | `/api/v1/packaging/validate?edition=` | build + validate (read-only) |
| POST | `/api/v1/packaging/build` | build + persist (operator) |

## 360° dependency check

- Reuses `bom`, `build_manager`, `licensing`, `deploy_providers`, `release_manager`; **no duplicate engine**.
- One derived manifest (`packaging-manifest.json`) registered in `config/store-registry.json` (owner `core/packaging.py`).
- Commercial licensing/entitlement decisions remain human-governed (plan §25).

## Verification (executed)

```
python -m compileall -q api core scripts          # 0
python scripts/dev/store_check.py                 # OK (packaging manifest registered)
python scripts/dev/packaging_check.py             # OK (5 editions, distinctions, fail-closed, single manifest)
python scripts/dev/precheck.py                    # PASS
```

**REL-0 GATE: PASS.** Next: **FULL DOGFOOD** + **FINAL AUDIT**.
