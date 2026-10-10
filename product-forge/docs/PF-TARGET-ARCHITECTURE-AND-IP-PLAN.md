# Product Forge â€” Target Architecture & IP-Protection Plan (Consolidated)

**Status:** Pre-implementation baseline / decision record (for review)
**Scope:** the **PF platform itself** (the thing that generates products) â€” its architecture, editioning, and IP protection.
**Explicitly out of scope here:** the generated product's own runtime and any agent-product execution engine.
**Source document reviewed:** `docs/Product_Forge_Code_Aligned_Target_Architecture_PreImplementation_Baseline.md`
(the **CODE-ALIGNED AMENDMENT** section supersedes the earlier sections of that document).
**Backlog items:** BI-PF-0386 (IP-value assessment), BI-PF-0387 (delivery baseline), BI-PF-0388 (ADR).

---

## 1. Executive verdict

The target-architecture document is **directionally sound** but is scoped as a **multi-year polyglot platform program**.
For the current goal â€” a **commercially deployable, IP-protected PF platform** â€” a **disciplined subset** is needed
now, the rest is later/evidence-gated, and some is premature. The single most important correction: **"PF needs a
Go runtime" does not mean "rewrite PF into Go."** The PF platform stays Python for development; what changes is
**what ships** (compiled) and **what new sensitive logic is written in** (Go).

Key principles adopted:
- **Contract-first Â· manifest-first Â· vertical-slice-first Â· implementation-minimal.**
- **One source â†’ many editions** (build profiles + component manifest + entitlements); no per-edition forks.
- **Never ship raw `.py`.** Shipped artifacts are compiled.
- **No undeclared runtime dependency.**
- **Strangler, not big-bang** (keep Python; migrate by value).

---

## 2. Terminology (locked)

| Term | Meaning |
|---|---|
| **PF Factory** | The build-time platform that **produces** products. Runs on PF-side (SaaS) or installed on-prem/OEM. Python. |
| **PF Runtime** | (Separate feature) an engine that **executes** an agent/EAP product. **Parked** â€” only needed if PF ships agent products. |
| **Generated product** | What the Factory produces. Runs **on its own** stack (chosen by the Technology Selection Engine). Independent of PF's stack. |
| **EAP (manifest role)** | The **authoritative delivery/build manifest** â€” composition of the contracts that says what to build/ship/license/deploy. **Kept.** |
| **EAP (executor role)** | A runtime that interprets the EAP to run a product. **Parked.** |
| **Component Manifest** | Per-component declaration: `language`, `runtime_required`, `customer_delivered`, `compiled`, `ip_zone`, `license`. Drives packaging. |
| **Runtime Dependency Compiler (RDC)** | Reads EAP + build/deployment profiles â†’ emits exactly what ships (the **IP-leakage guard**). |

**EAP is still needed** â€” but in the current context it is the **delivery manifest**, not an execution engine.
Its executor role activates only if PF later ships agent products.

---

## 3. IMPACT REVIEW (themes vs verdicts)

| # | Theme | Verdict | Evidence | Recommendation |
|---|---|---|---|---|
| 1 | Polyglot platform (TS/Go/Python/Rust/WASM) | new-path | 0 Go/Rust; UI is Python `dashboard/server.py` | approve direction; adopt customer-runtime/platform Go; defer Rust/WASM |
| 2 | Factory / Runtime / Commercial / Shared planes | new-path | `core/pipeline_executor.py:1`, `core/job_manager.py` | logical separation now; physical later |
| 3 | EAP as boundary | new-path | no `core/eap` | **needed now** (manifest) |
| 4 | Canonical contracts | new-path | no `core/contracts` | **needed now** (thin) |
| 5 | Capability registry + entitlement-at-boundary | new-path | `core/licensing.py` | **needed now** |
| 6 | Asymmetric licensing (replace HMAC) | aligned (modify) | `core/licensing.py:13,137` | **needed now** |
| 7 | Build profiles / OEM / white-label | new-path | no `build_profiles/` | now (profiles) / later (OEM) |
| 8 | Technology Selection Engine | aligned (extend) | `core/tech_stack.py:166` | extend, don't replace |
| 9 | Gateways (Model/Tool/Memory/Infra) | aligned (extend) | `core/orchestrator/model_router.py:291`, `core/tool_registry.py` | later |
| 10 | Change-classification gate + drift guard + no-source test | new-path (process) | extends `AGENTS.md`, `precheck.py` | **needed now** |
| 11 | Go platform core | new-path (major) | 0 Go | **needed now (minimal)**; full migration later |
| 12 | Rust core / WASM / service decomposition | new-path | no need measured | **defer** |
| 13 | PostgreSQL / persistence adapters | new-path | `core/job_manager.py:67` | later |
| 14 | Dashboard â†’ TypeScript | **violates** | `AGENTS.md` frozen dashboard | **reject** |
| 15 | IP zones A/B/C; SaaS-first | aligned | doc Â§13 | approve; lead with SaaS + licensing |
| 16 | Product portfolio / editions | new-path | no edition packaging | **needed now** (profiles) |

No `derails`/`stale`. One `violates` (#14) â†’ rejected. The doc as a whole is a **major new path**, approved via this review.

---

## 4. IP-protection strategy

### 4.1 The problem
The PF platform is **100% Python** (`core/packaging.py:123` ships `source_dir`; no compilation, no source exclusion;
632 tracked `.py`). Deploying it on-prem/OEM exposes readable source â†’ IP/reverse-engineering risk and loss of
recurring value.

### 4.2 The three paths (per edition)

| Path | What | Effort | Protection | Offline |
|---|---|---|---|---|
| **1. Compile Python** (Nuitka; PyArmor/Cython partial) | ship compiled binaries | low | partial | yes |
| **2. Reimplement in Go/Rust (by value)** | rewrite sensitive modules | high | strong | yes |
| **3. SaaS-first** | don't ship the Factory | none | full | no |

### 4.3 Corrected claim: "AI needs Python"
**PF's AI does not require Python today.** LLM calls are HTTP (`requests.post(.../chat/completions)`,
`urllib.request.urlopen`) and memory is **token-overlap** (`agent_memory.py:271-284`); **no** torch/transformers/
faiss/langchain. So Go can make the same calls and run the same logic. Python becomes necessary only for **local
ML/embeddings** (not present today).

### 4.4 The adopted strategy (strangler)
1. **Keep `.py` now** (development).
2. **New logic that ships in a customer edition and is sensitive â†’ Go.** Build-time-only / SaaS-only / experimental â†’ Python.
3. **Existing/remaining â†’ compiled** (no raw `.py` shipped).
4. **One baseline for all editions** (build profiles; no forks).
5. **Later: rewrite high-value modules â†’ Go** (per the IP-value assessment).
6. **Later (aspiration): rewrite remaining â†’ Go** â€” retain the compiled-Python escape hatch.

### 4.5 What "rewrite by value" means
Rewrite the **high-IP-value** modules to Go/Rust (strong); ship the **low-value remainder** as compiled Python (stopgap).
First-pass tiers:
- **High value (Go/Rust first):** `pipeline_executor.py`, `product_analyzer.py`, `product_plan.py`, `service_catalog.py`,
  `global_orchestrator.py`, `intent_router.py`, `discovery_panel.py`, `tech_stack.py`, `model_gate/strategy/fit`,
  `pidl.py`, `agent_memory.py`, `conversation_models.py`.
- **Commercial/IP-critical (Go):** `licensing.py`, `billing.py`, `packaging.py`, `release.py`, `signing.py`,
  `deploy_providers.py`, `credentials.py`, `artifact_registry.py`, `bom.py`, `sizing.py`.
- **Plumbing (compile now, migrate later):** `backlog.py`, `issues.py`, `traceability.py`, `job_manager.py`,
  `workflow_docs.py`, `marketing.py`, `presentation_generator.py`, `customer_onboarding.py`, `mobile_tester.py`, etc.
- **AI-adjacent (Go-able):** `multi_model_review.py`, `compliance_verifier.py`, `prompt_builder.py`, `agent_tool_loop.py`.
- **Build-time tooling (never shipped):** tests, docs/dev scripts â€” stay Python.

### 4.6 How Go and Python coexist (same environment)
```text
on-prem host
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ PF platform core â€” Go (compiled)              â”‚  strong protection
â”‚  orchestration, planning, tech-selection,     â”‚
â”‚  licensing, packaging, model-routing logic    â”‚
â”‚              â”‚ contract (JSON/HTTP/gRPC)      â”‚
â”‚              â–¼                                 â”‚
â”‚ remainder â€” Python (compiled via Nuitka)      â”‚  partial protection (no readable .py)
â”‚  as subprocess/sidecar/worker                 â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```
- **Go = host/core.** **Python = sidecar/worker** over a **contract**.
- Python ships **compiled**; Go ships as a **native binary**.
- The **Component Manifest** declares the Python worker (language, license, BOM) â€” explicit, not hidden.
- As logic migrates to Go, the Python footprint shrinks and protection improves.

### 4.7 Value retention (beyond hiding source)
**Signed updates** (only PF issues new versions) + **licensing/entitlements** + keeping the *living* intelligence
(models, learnings, new capabilities) under PF's control.

### 4.8 One codebase, one implementation per feature (the language rule)
There is **one repo / one baseline**. SaaS and customer editions differ by **build profile**, never by a second
codebase.

- **SaaS** runs the **source** (Python, plus any Go) server-side â€” nothing ships, so no compilation is needed.
- **Customer** **compiles the same source** (`go build` for Go; **Nuitka** for Python) and ships the compiled
  artifact + license. **No raw `.py`.**

**Locked rule (Go-first for new work):** new features are implemented in **Go**; existing Python is **compiled**;
high-value existing modules are **migrated to Go** later by value.

| If the featureâ€¦ | Language | SaaS runs | Customer ships |
|---|---|---|---|
| **new feature (default)** | **Go** | Go | Go binary |
| new but **AI/ML-heavy** or **experimental** (Go impractical) | **Python** | Python | compiled / declared worker |
| **existing** Python | stays Python | Python | **compiled** Python (Nuitka) |
| **existing high-value** module (migrated) | **Go** (one-time replacement) | Go | Go binary |
| **PF-side only** (build-time/tooling/tests/docs) | **Python** | Python | not shipped |

**Hard rules:**
- **Build time compiles â€” it never translates.** `go build` and Nuitka are different mechanisms; there is **no**
  "Python â†’ Go at compile time."
- **No duplication.** A feature is **either Go or Python**, never both. Migration is a **one-time deliberate
  replacement** (BI-PF-0386, by value), not a parallel copy.
- **Go is mandatory from the start** (B1) so new features land in Go immediately â€” no deferred ambiguity.
- The **Go footprint grows over time**; SaaS always runs the current baseline; the customer artifact is always its
  compiled form. A full Pythonâ†’Go rewrite remains a **non-goal/aspiration** (compiled Python is the fallback for
  low-value remainder).

---

## 5. Target architecture (PF platform)

```text
PF FACTORY (build)  â”€â”€ Product Compiler â”€â”€â–º  EAP (delivery manifest)
      â”‚                                            â”‚
      â”‚ contracts: ProductSpec, TechnologyProfile, RuntimeProfile,
      â”‚   DeploymentProfile, LicenseProfile, EntitlementProfile,
      â”‚   ComponentManifest, BOM, Evidence
      â”‚                                            â–¼
      â”‚                                  Runtime Dependency Compiler
      â”‚                                            â”‚
      â”‚                          (build profile + OS/arch + license/entitlement)
      â”‚                                            â–¼
      â”‚                                  compiled, signed customer package
      â”‚                                            â”‚
      â”‚                          Go core + compiled-Python sidecar + license
      â–¼                                            â–¼
   build profiles (community/professional/enterprise/on-prem/airgap/oem/embedded)
```

Two compiler stages: **Product Compiler** (requirements â†’ product + EAP) and **Runtime Package Compiler**
(EAP + profiles â†’ signed package). The **RDC** is the IP-leakage guard.

---

## 6. Phases & epics

### EPIC A â€” PF Commercial & IP Foundation (needed now)
| Item | Deliverable | Depends on | Fixture |
|---|---|---|---|
| A0 | Baseline freeze; reconcile doc (amendment = authority; fix 16- vs 39-stage); **ADR register** | â€” | repo SHA + test baseline |
| A1 | **Contracts** (thin, grow by need) incl. the **Goâ†”Python contract** | A0 | `sample-*/â€¦` fixture |
| A2 | Capability Registry + entitlement-at-boundary + **asymmetric licensing** | A1 | license issued+verified |
| A3 | **PF platform build â†’ package â†’ deploy pipeline** (one-time, rebuildable) + **compiled packaging** (Nuitka for Python, `go build` for Go) + signing + SBOM/LBOM + **no-raw-`.py` release gate**. Absorbs **BI-PF-0383** (build-time plug/unplug: exclude the worker subsystem per edition) | A1,A2,B1 | compiled, signed platform package |
| A4 | **EAP (manifest)** + validator/registry + compatibility | A1 | `sample.eap` |
| A5 | **Runtime Dependency Compiler** (authoritative composition engine) | A1,A4 | `sample-runtime-package/` |
| A6 | Governance: change classifier + drift guard + no-undeclared-dep + language rule | A1 | gate on the fixture |
| A7 | **Vertical slice**: Requirementâ†’Techâ†’Factoryâ†’EAPâ†’RDCâ†’compiled+signed package | A1â€“A6 | e2e |

### EPIC B â€” Scale & Extensions (trigger/evidence-gated)
| Item | Deliverable | Trigger |
|---|---|---|
| B1 | **PF Go core** (compiled host; new shipped/sensitive logic lands here) | none â€” architectural |
| B2 | Gateways (Model/Tool/Memory/Infra) | provider coupling hurts |
| B3 | Persistence scaling (SQLite/JSON/Postgres) | scale/HA need |
| B4 | OEM / white-label profiles | OEM deal |
| B5 | Rust protected components | measured security/perf |
| B6 | WASM plugins | plugin contract + need |
| B7 | Service decomposition | independent scaling/security |
| Bmig | **Migrate high-value â†’ Go**, then remaining | IP-value assessment |

### Backlog items created
- **BI-PF-0386** â€” IP-value assessment of PF platform modules (rewrite-by-value ranking).
- **BI-PF-0387** â€” PF platform delivery baseline (one source; newâ†’Go; existingâ†’compiled; no raw `.py`). *(blocked_by 0388)*
- **BI-PF-0388** â€” ADR: shipped editions use compiled artifacts; never raw `.py`; one source many editions.

---

## 7. Execution order (in order, with gates)

```text
STEP 0  ADR + strategy lock          (BI-PF-0388)   â†’ decision recorded in the A0 register
STEP 1  A0 baseline freeze           â†’ repo SHA, test baseline, doc reconciliation, ADR register
STEP 2  A1 contracts (thin)          â†’ ProductSpecâ€¦ComponentManifestâ€¦BOMâ€¦Evidence + Goâ†”Python contract
STEP 3  B1 PF Go core (seam)         â†’ minimal Go host; new features land here from now on
STEP 4  A2 licensing/entitlements    âˆ¥  A4 EAP (delivery manifest + compatibility)
STEP 5  A3 compiled packaging        â†’ Nuitka (existing Python) + go build (Go) + signing + SBOM/LBOM + NO-RAW-.py gate
STEP 6  A5 Runtime Dependency Compiler (authoritative composition engine)
STEP 7  A6 governance                â†’ change classifier + drift guard + language rule + no-undeclared-dep
STEP 8  A7 vertical slice            â†’ Requirementâ†’Techâ†’Factoryâ†’EAPâ†’RDCâ†’compiled+signed package   [APPROVAL GATE]
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
STEP 9  BI-PF-0386 IP-value assessment â†’ ranked legacy-module list (drives migration)
STEP 10 Bmig migrate high-value legacy â†’ Go  â†’ replace, not duplicate
STEP 11 (B2 gateways âˆ¥ B3 persistence âˆ¥ B4 OEM profiles)   [trigger-gated]
STEP 12 Bmig migrate remaining â†’ Go (aspiration)   âˆ¥   B5 Rust / B6 WASM / B7 decomposition (defer)
```

**Critical path:** A1 contracts â†’ B1 Go seam â†’ A3 compiled packaging â†’ A4 EAP(manifest) â†’ A5 RDC â†’ A7 vertical slice.
**Go is mandatory now (B1):** new features are written in Go from day one â†’ no deferred rework.

**B1 implemented (BI-PF-0394):** the native Go core lives in `go/pfcore` (the pfcore-host binary; stdlib-only, `go build`-clean). It speaks the A1 wire contract (contract `host` enum value `go`; pfcore identity rides as `result.host_id="go-pfcore"`) and is invoked from the PF runtime via `core/go_host.invoke(op, ...)` - built on demand, fail-closed. New shipped/sensitive implementations land there.
**Gate:** no normal feature work until the A7 vertical slice passes; the customer package must contain **no raw `.py`**.

---

## 8. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Go slows feature velocity | only shipped/sensitive new logic â†’ Go; build-time/SaaS stays Python |
| Long-lived Go+Python hybrid complexity | contract-first; small seam (A1) |
| Compiled-Python fragility (dynamic imports/eval/C-ext) | test compiled build in CI; avoid dynamic features in shipped modules |
| Team Go skill | tiny kernel first; grow gradually |
| "All â†’ Go" never finishes | treat as aspiration; keep compiled-Python escape hatch |
| Over-promising IP protection | pair compiled artifacts with licensing + signed updates |
| Doc internal inconsistency (16 vs 39 stage) | reconcile in A0 |

---

## 9. Open questions
1. **Confirm strategy** (options 1â€“6) and the refinements (newâ†’Go only for shipped/sensitive).
2. **Compiled-Python acceptance:** is Nuitka-level protection acceptable for early on-prem, or is Go required from the start?
3. **Edition priority:** which of Community/Professional/Enterprise/VPC/on-prem/air-gap/OEM ships first after SaaS?
4. **Go seam contract:** JSON-over-stdio, HTTP, or gRPC for Goâ†”Python?
5. **ADR register location** (`docs/adr/` vs existing `docs/guidelines/architecture/decisions.md`).
6. **Scope of A7 vertical slice:** which real PF product is the reference fixture?

---

## 10. Appendix â€” commercial Python IP practices (see companion answer)
Compiled packaging (Nuitka/PyInstaller/PyArmor), licensing/entitlement, SaaS-first, source-available vs proprietary
splits, signed updates, and keeping high-value intelligence server-side are the industry norms. See the analysis
in the companion response.

---

## 11. A1 implementation note â€” canonical contracts + Goâ†”Python wire (BI-PF-0393)

The contract surface is now materialized as a thin, code-emitted module (`core/contracts.py`) that owns **no
store**: canonical data stays in the existing owners and is projected into the contracts on demand.

- **Product contracts** (`product-forge/<name>@1`): `ProductSpec`, `TechnologyProfile`, `RuntimeProfile`,
  `DeploymentProfile`, `LicenseProfile`, `EntitlementProfile`, `ComponentManifest`, `BOM`, `Evidence`.
  Each has a JSON Schema (draft-07), fail-closed `validate(name, data)` and a thin `canonical(name, data)`
  projection (keeps declared fields, drops unknown keys, stamps `schema`).
- **Wire contract** (`product-forge/wire-request@1` / `product-forge/wire-response@1`, version `1`):
  ops `ping | describe | validate | canonicalize`. `core.contracts.handle_wire(request)` is the Python core
  handler; the Go host reference is `product-forge/go/contract/` (stdlib only) serving the same ops over stdio.
- **Emission from existing code**: `core.bom.contract_view(project_dir)` projects the BOM onto the canonical
  `bom` contract (the pattern for the other profiles as A2/A3/A5 land).
- **Evidence/tests**: fixtures `test-framework/tests/fixtures/contracts/sample-*/` validate against the
  contracts; `test-framework/tests/pipeline/test_contracts.py` proves the **Go host and Python core exchange a
  valid payload** and asserts required-field parity between the Python source of truth and the Go mirror.

Grow by need: add a contract only when a real producer/consumer needs it (no speculative fields).
