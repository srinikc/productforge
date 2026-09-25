# QA & Quality System — End-to-End Implementation Spec

> Owner: **QA agent (`validate` = Senior QA)**. Builds owned by **devops**. Specs by **design/architect/ux-ia/product-design-spec**; fixes by **fix**, approved by **code-review**.
> This document is the single implementation spec for the QA/quality subsystem: test matrix, spec-review gate, builds/versioning, per-category execution, defects/RCCA, AI intelligence, QIR, Go/No-Go, the QA console, and delivery integration.

---

## 0. Principles
1. **One-stop QA**: the QA agent designs, creates, organizes, executes, reports, and gates quality — through the in-repo test framework only.
2. **No tests without a build**: every test cycle runs against a versioned build.
3. **Everything maps to a requirement** (FR/NFR) — traceability is mandatory.
4. **Evidence over opinion**: findings, defects, insights all carry evidence.
5. **No scaffolding**: generated tests are skip-marked and must be replaced with real assertions.
6. **Config-driven, stack-agnostic**: adding a stack/test-type is a config/kit edit, not core code.

---

## 1. Roles & ownership
| Role | Agent id | Owns |
|---|---|---|
| Senior QA | `validate` (aliases `qa`, `sdet`) | test strategy, tests, suites, cycles, kits, spec review, defects, RCCA, QIR, Go/No-Go, QA console data, delivery QA section |
| DevOps | `devops` | version + build number, build/package, artifacts, release notes, registry publish |
| Design / Architect | `design`, `architect`, `ux-ia`, `product-design-spec` | specs + acceptance criteria; respond to QA findings |
| Fix | `fix` | resolve defects/spec findings; re-run tests |
| Reviewer | `code-review` | approve fixes and code before acceptance |
| Orchestrator | `orchestrator` | routing, gates, HIL, state |

---

## 2. End-to-end workflow
```
Spec phase
  design / product-design-spec / ux-ia / architect  ->  specs + FR/NFR + acceptance criteria
        |
        v
  3a QA SPEC REVIEW GATE  (NEW)  <--------------------------+
        |  blocking findings? -> design/architect/ux-ia revise
        |  optional/minor?     -> HIL (documented waiver)
        |  all blocking clear  -> approved
        +---------------------------------------------------+
        v
  4-0 Skeleton
        v
Iteration (4a..4f), repeats per feature set:
  implement (code + tests per test-matrix, FR/NFR-tagged)
     -> devops  (VERSION + BUILD N + release notes + artifacts)
        -> code-review (review)
           -> qa/validate (run test cycle ON THIS BUILD, per category)
                |  fail -> fix -> devops(patch build) -> code-review(reviewer) -> qa re-validate -> close defect
                |  pass -> close defects, update traceability/QIR
        -> next iteration
        v
  per-iteration build + release notes
        v
  5 Security | 6 NFR | 7 Full suite  (all run on builds, per-category runners)
        v
  8 Document | 9 Package
        v
  10 QA GO/NO-GO GATE  (NEW, before deploy)   -> GO / GO-WITH-RISK / NO-GO
        v
  11 Deploy (post-deploy smoke) | 12 Exit
        v
  Final Product Delivery Report  (includes QA/quality section + console link)
```

---

## 3. Test catalogue & matrix
**Config:** `config/test-matrix.json` — requirement type × layer → category → framework / path / naming / runner.

| Requirement | Categories |
|---|---|
| Functional (FR) | `unit`(logic), `db`, `api`, `integration`, `ui`, `e2e`, `e2e_bdd`, `visual` |
| Non-functional (NFR) | `performance`, `security`, `accessibility`, `reliability`, `scalability` |
| Operational | `smoke`, `sanity`, `install`, `packaging` |

- **Product kinds** (web/desktop/mobile/api/cli/data) select the required category set.
- **Kits** (`test-framework/kits/<type>/`): templates + runner hints + naming, incl. non-standard areas — usability/UX, compatibility, i18n, API-contract, DB-migration, chaos, cloud/infra, media (image/video), social/community, privacy/GDPR, analytics, notifications, offline/sync.
- **Unknown area → research fallback**: QA uses `researcher`/`scout` to learn the method, then **registers a new kit + matrix entry + suite** and creates/executes tests inside the framework.
- **Module:** `core/test_matrix.py` (`directive`, `plan`, `categories_for_kind`, `missing_categories`).

---

## 4. Builds, versioning, release notes
**Scheme**
- `version` = SemVer `MAJOR.MINOR.PATCH`; `build_number` = monotonic int (starts 1, +1 per build); `build_id` = `<version>+build.<n>` (+ git SHA).
- Bump (auto + human override at release): feature set/iteration → `minor`; fixes only → `patch`; breaking → `major`. Build number always increments.

**Triggers**
1. End of each implementation iteration (4a..4f).
2. After each fix cycle/set of fixes.
3. Pre-release / RC.
4. On demand.

**Process (devops)**
`collect change-set → decide bump → increment build_number → build/package (stack-native) → checksum → tag → release notes → publish to artifact registry → record build-info`.

**Artifact storage (industry standard)**
- Content-addressed, immutable, checksummed; retention policy.
- Default **local store** `products/<project>/builds/<build_id>/`; pluggable backends: **OCI/Docker registry**, **S3/GCS/Azure Blob**, **Artifactory/Nexus**, or CI artifacts.
- Module: `core/artifact_registry.py` (local backend + adapter interface).

**Records**
- `products/<project>/build-info.json` (latest) and `products/<project>/builds/<build_id>.json`.
- `CHANGELOG.md` and `docs/releases/<build_id>.md`.

**Modules:** `core/build_manager.py`, `agents/devops.agent.json`.

---

## 5. Test execution & build linkage
- **Gate:** `run_cycle` requires a successful build for the current change-set; otherwise the QA agent requests a build from devops (blocking).
- Every **test cycle** records `{build_id, version, build_number, commit}`.
- Every **defect** records `found_in_build`; every **fix** records `fixed_in_build`; traceability rows record `verified_in_build`.
- **Per-category execution**: `run_cycle` builds `test_matrix.plan(...)` and runs each category with its runner:
  - `adapter` → stack native (pytest/jest/go/cargo/dotnet/php/ruby/flutter)
  - `playwright` → `npx playwright test`
  - `playwright_bdd` → `npx bddgen && npx playwright test`
  - `nfr` → `core/nfr_runner` (security/performance/accessibility/install/packaging)
  - `framework` → smoke/sanity suites
- App lifecycle (web/desktop): `run_deploy_up` → run → `run_deploy_down`; mobile: simulators or device farms.
- **Modules:** `core/test_framework_integration.py`, `core/test_adapters.py`, `core/deploy_providers.py`, `core/mobile_tester.py`, `core/nfr_runner.py`.

---

## 6. Defects, RCCA, AI intelligence
- **Defect loop:** failing tests → `DefectTracker` (severity, stack trace, feature/NFR, build) → `core/defect_loop` injects defects + RCCA into `fix` → `fix` → `code-review` reviewer gate → re-build → re-validate → **auto-close** on pass (`reconcile`).
- **RCCA:** root-cause stage + prevention recommendations; fed back to earlier stages.
- **AI trend intelligence** (`core/qa_intelligence.py`) — evidence-based insights across cycles/builds:
  - issue clustering in a feature/area, aging/unresolved issues, regressions, flakiness, coverage erosion, risk prediction (defect density × low coverage × churn), RCCA clustering, QIR trend.
  - output `{id, type, severity, confidence, scope, evidence[], action, build_range}` → `test-framework/results/<project>/insights.json`.

---

## 7. QA Spec Review gate (pre-implementation)
- **Stage `3a QA Spec Review`** (after `3 Refine Requirements`, before `4-0 Skeleton`).
- **Reviews every artifact one-by-one**: `design.md`, `product-design-spec.md`, `ux-ia.md`/tokens, `architecture.md`, `infra.json`, `requirements.md` + `docs/specs/FR-*` / `NFR-*`.
- **Per-artifact review record** with findings: `id, class (BLOCKING/OPTIONAL/MINOR/QUESTION), severity, category, location, recommendation, owner, requirement_id, status, resolution_notes, evidence, hil_decision`.
- **Loop:** blocking → route to owner → owner revises → QA re-reviews affected artifacts → repeat (cap, then HIL). Optional/minor → HIL waiver (documented) → proceed. **Cannot proceed with any open blocking finding.**
- **Dual lens:** E2E quality (coverage, consistency, testability, risk) + customer/usability (Nielsen, a11y, edge states, acceptance clarity).
- **Persistence:** `docs/qa/reviews/<artifact>-review.md` + `test-framework/results/<project>/spec-review.json` + `docs/qa/review-history/<iter>.json`.
- **Module:** `core/spec_review.py`; findings surfaced in the QA console and Go/No-Go.

---

## 8. QIR — Quality Index Report
- **One number** (0–100, band, trend) **+ profile** anchored to **ISO/IEC 25010:2023** (nine characteristics) plus a **QA Governance** extension.
- **Profile characteristics:** Functional suitability · Performance efficiency · Compatibility · **Interaction capability (UX)** · Reliability · Security · Maintainability · **Flexibility (portability)** · **Safety** · **QA Governance** (spec review, traceability, RCCA, process).
- `QIR = 100 × Σ(wₖ·sₖ)/Σwₖ`; any Red/blocking characteristic caps QIR at 59; bands ≥90 Green, 75–89 Yellow, <75 Red.
- **Characteristic → data:** Functional suitability (FR pass/coverage), Performance efficiency (perf/scale), Compatibility (browser/os/device matrix), Interaction capability (usability/a11y + QA customer review), Reliability (reliability/chaos + smoke/sanity + regression), Security, Maintainability (code-quality + review + defect density), Flexibility (install/packaging/deploy/multi-env), Safety (risk/harm controls, optional), **QA Governance** (spec review, traceability, RCCA).
- **Weights:** base by product kind + domain overlays (fintech/healthcare/ecommerce/social/media/gov/data) — `config/qa-weights.json`, per-project overridable.
- **Scope: project-level** (single index + profile per project per build) — aligned with ISO 25010 (product-level) and SonarQube-style project/branch gates. Feature/NFR signals feed the characteristics (e.g., feature pass rates → Functional suitability) and appear as **drill-down metrics** (defect density, coverage, pass rate per feature) — **there are no separate per-feature QIR numbers**.
- **Change-set view (industry "new code" analog):** an optional *new/change quality* score per build (quality of what changed since the last build), alongside the project QIR.
- **Views:** Executive (number/band/trend/top risks) + Engineering (profile/sub-metrics/evidence/drill-down).
- **Module:** `core/qir.py` → `test-framework/results/<project>/{qir.json,qir-history.json}`.

---

## 9. Go/No-Go matrix (includes Spec Review)
`core/qa_report.go_no_go(project)` → matrix with RAG per dimension:
| # | Dimension | Green | Yellow | Red |
|---|---|---|---|---|
| 1 | **Spec Review (QA gate)** | 0 blocking, optional waived | optional open (HIL pending) | any blocking open |
| 2 | Functional results | pass ≥ threshold | marginal | failures |
| 3 | Layer coverage | all required categories present | gaps | missing layers |
| 4 | NFR quality | all met | partial | unmet |
| 5 | Defects | 0 crit/high | med/low | crit/high open |
| 6 | Traceability | 100% FR/NFR | gaps | uncovered critical |
| 7 | Deploy/Smoke/Sanity | pass | flaky | fail |
| 8 | Install/Packaging | pass | partial | fail |
| 9 | Regression trend | stable/up | easing | degrading |
| 10 | RCCA completeness | all | partial | missing |
Decision: any Red → **NO-GO**; Yellow only → **GO-WITH-RISK**; all Green → **GO**. QIR is the magnitude/trend; Go/No-Go is the decision.

---

## 10. QA console (test-framework web) + pipeline widget
- **Separate page**, project selector. Built on `test-framework/dashboard` (port 3011).
- **Tabs:** Overview · Builds · Release Notes · Suites · Cycles · Executions · Defects · RCCA · **Spec Reviews** · Features · Coverage · Traceability · **Insights** · **QIR** · **Go/No-Go** · Kits · Settings.
- **APIs (summary/status):** `/api/quality/status` (RAG), `/api/summary`, `/api/builds`, `/api/release-notes`, `/api/suites`, `/api/cycles`, `/api/executions`, `/api/results`, `/api/defects`, `/api/defects/by-feature`, `/api/defects/by-category`, `/api/rcca`, `/api/spec-review`, `/api/traceability`, `/api/coverage/cycle/<id>`, `/api/insights`, `/api/qir`, `/api/gonogo`, `/api/delivery-report`.
- **Pipeline page** embeds a compact **Quality widget** (RAG + QIR + top risks) via `/api/quality/status` with a deep link to the console.

---

## 11. Delivery report integration
`core/orchestrator/reporting.py` final report gains a **QA / Quality** section:
- Build/version + release notes link; QIR number + profile; Go/No-Go matrix (incl. Spec Review); coverage report; insights; console URL `…:3011/?project=<name>`; `qa-manifest.json`.
- Optional **static snapshot**: `test-framework/reports/<project>/index.html` for offline delivery.

---

## 12. Per-project artifact layout
```
products/<project>/
  build-info.json                      # latest version/build
  builds/<build_id>.json               # build records
  dist/                                # build artifacts (or registry)
  CHANGELOG.md
  docs/releases/<build_id>.md
  docs/specs/{FR-*.md,NFR-*.md}
  docs/qa/{test-plan,test-strategy,traceability-matrix,test-results,defects,qa-report,go-no-go}.md
  docs/qa/reviews/<artifact>-review.md, review-summary.md, review-history/<iter>.json
  tests/{unit,db,api,integration,ui,e2e,visual,a11y,performance,security,smoke,sanity}/
  features/*.feature + steps/
  qa-manifest.json
test-framework/
  kits/<type>/
  results/<project>/{metrics,trends,features,traceability,cycles,builds,qir,qir-history,insights,spec-review,coverage}.json
  defects/<project>/{defects.json,rcca/}
```

---

## 13. Pipeline-definition changes
- **Add stage `3a QA Spec Review`** (`ideal_flow: [qa]`, depends on design/pds/ux-ia/architect/requirements; blocks `4-0`).
- **Iteration stages (`4a..4f`)**: `ideal_flow` → `[implement, devops, code-review, qa]` (devops = build/version/notes; qa = validate).
- **Add gate `10a QA Go/No-Go`** before `11 Deploy`; NO-GO blocks deploy (HIL override recorded).
- **`qa` decision_logic:** `blocking_findings → design|architect|ux-ia|product-design-spec`, `optional_findings → human`, `tests_fail → fix`, `coverage_gap → implement`, `approved → orchestrator`.
- **`fix` flow:** `fixed → code-review → qa`; `major_change_needed → implement`.
- **Build dependency:** `qa.agent_dependencies` includes `devops` (build required).
- **Artifacts map:** add `test_plan`, `traceability_matrix`, `qa_report`, `qir`, `build_artifact`, `release_notes`, `spec_review`.

---

## 14. Modules & config
| Concern | Module / file |
|---|---|
| Test catalogue / matrix | `config/test-matrix.json`, `core/test_matrix.py` |
| Stack adapters | `core/test_adapters.py` |
| Cycle/lifecycle/bridge | `core/test_framework_integration.py`, `core/test_framework_bridge.py` |
| NFR/security/perf/a11y/install | `core/nfr_runner.py`, `core/nfr_coverage.py` |
| Defects / RCCA / loop | `core/defect_loop.py`, `test-framework/core/{defect_tracker,rcca}.py` |
| Spec review gate | `core/spec_review.py` |
| Builds / version / registry | `core/build_manager.py`, `core/artifact_registry.py` |
| Intelligence | `core/qa_intelligence.py` |
| QIR / reports | `core/qir.py`, `core/qa_report.py` |
| Suites/cycles registry | `core/qa_cycles.py`, `test-framework/core/suite_manager.py` |
| Console | `test-framework/dashboard/*` |
| Delivery | `core/orchestrator/reporting.py` |
| QA agent | `agents/validate.agent.json` |
| Config | `config/test-matrix.json`, `config/qa-weights.json`, `config/qa-status.json` |

---

## 15. Verification plan
1. `test_matrix.directive/plan` for web/api/mobile/kits; gaps detected.
2. Build: number increments; bump rules; release notes match change-set; registry stores checksums.
3. Test gate: cycle blocked without build; cycle/defect carry build id.
4. Per-category execution runs the right runner; aggregated results correct.
5. Spec review: blocking blocks + routes; optional → HIL; resolution tracked; re-review scoped.
6. Defect loop: fail → defect → fix → reviewer → re-validate → auto-close.
7. Intelligence: seeded recurring/aging/regression patterns flagged with evidence.
8. QIR: number + profile + band + cap; weights normalize; trend.
9. Go/No-Go: any Red → NO-GO; Spec Review dimension included.
10. Console APIs + delivery report contain build, QIR, matrix, insights, links.
11. `compileall` clean; existing smoke (`freetrial-smoke`) unaffected.

---

## 16. Rollout order
1. **P1** Test matrix → implement/QA prompts. ✅ done (`core/test_matrix.py`, `config/test-matrix.json`, `agent_runner._test_generation_directive`)
2. **P2** Per-category execution + build gate/linkage. ✅ done (`core/build_manager.py`, `core/artifact_registry.py`, `run_cycle`)
3. **P3** Playwright BDD + kits. ✅ done (`generate_bdd`, `test-framework/kits/*`)
4. **P4** Spec Review gate (3a) + findings store. ✅ done (`core/spec_review.py`, compliance 11i, stage `3a`)
5. **P5** Builds/versioning/release notes/registry + `core/qa_cycles.py`. ✅ done
6. **P6** AI intelligence. ✅ done (`core/qa_intelligence.py`)
7. **P7** QIR + Go/No-Go (incl. Spec Review row). ✅ done (`core/qir.py`, `core/qa_report.py`, `config/qa-weights.json`, stage `10a`)
8. **P8** QA console build-out + pipeline widget. ✅ done (14 tabs + APIs in `test-framework/dashboard`)
9. **P9** Delivery report + static snapshot + `qa-manifest.json`. ✅ done (`core/qa_manifest.py`, `reporting.generate_final_report`)

## 20. Implementation status
- All phases **P1–P9 implemented and verified** (`compileall` clean; synthetic fixtures).
- New stages in `pipeline-definition.json`: **`3a QA Spec Review`** (blocks `4-0`) and **`10a QA Go/No-Go`** (blocks `11 Deploy`).
- QA agent = `validate` (id kept; Senior QA identity) — owns suites, cycles, kits, spec review, defects/RCCA, insights, QIR, Go/No-Go, console data, delivery QA section.
- Pending (see §19): git branching/tagging + CI/CD integration.

---

## 17. Risks & decisions
- Keep `validate` id (aliases `qa`); avoid 60-ref rename.
- Keep stdlib console, extend; no new deps.
- NFR/BDD gated by mode (`nfr`/`full`) to control cost.
- Findings store separate from test defects (`spec_findings`) to avoid conflation.
- Artifact registry: local default + pluggable backends; retention policy.
- HIL: block on NO-GO/blocking findings with recorded override.

## 18. Confirmed decisions
- Insight SLA defaults: critical 1 build, high 3, medium 5.
- QIR is **project-level only** (no per-feature QIR).
- Build bump policy: auto (feature-set→minor, fix→patch) with human override at release.
- Builds: one per iteration **and** one per fix cycle.
- Static snapshot: included for offline delivery (recommended, adopted).

## 19. Follow-up (deferred, tracked)
- **Git strategy**: check-in policy, branching model (e.g., trunk-based vs GitFlow), commit conventions, PR/MR review, and **tagging** (build tags `v<semver>+build.<n>`, release tags).
- **CI/CD integration**: wire builds, test cycles, QIR/Go-No-Go gates, and the QA console into the CI/CD pipeline (triggers, artifacts, environments, promotion/rollback).
- Build/version scheme must align with git tags + CI pipelines when this follow-up is done.
