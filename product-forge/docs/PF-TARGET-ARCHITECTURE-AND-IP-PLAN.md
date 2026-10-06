# Product Forge — Target Architecture & IP-Protection Plan (Consolidated)

**Status:** Pre-implementation baseline / decision record (for review)
**Scope:** the **PF platform itself** (the thing that generates products) — its architecture, editioning, and IP protection.
**Explicitly out of scope here:** the generated product's own runtime and any agent-product execution engine.
**Source document reviewed:** `docs/Product_Forge_Code_Aligned_Target_Architecture_PreImplementation_Baseline.md`
(the **CODE-ALIGNED AMENDMENT** section supersedes the earlier sections of that document).
**Backlog items:** BI-PF-0386 (IP-value assessment), BI-PF-0387 (delivery baseline), BI-PF-0388 (ADR).

---

## 1. Executive verdict

The target-architecture document is **directionally sound** but is scoped as a **multi-year polyglot platform program**.
For the current goal — a **commercially deployable, IP-protected PF platform** — a **disciplined subset** is needed
now, the rest is later/evidence-gated, and some is premature. The single most important correction: **"PF needs a
Go runtime" does not mean "rewrite PF into Go."** The PF platform stays Python for development; what changes is
**what ships** (compiled) and **what new sensitive logic is written in** (Go).

Key principles adopted:
- **Contract-first · manifest-first · vertical-slice-first · implementation-minimal.**
- **One source → many editions** (build profiles + component manifest + entitlements); no per-edition forks.
- **Never ship raw `.py`.** Shipped artifacts are compiled.
- **No undeclared runtime dependency.**
- **Strangler, not big-bang** (keep Python; migrate by value).

---

## 2. Terminology (locked)

| Term | Meaning |
|---|---|
| **PF Factory** | The build-time platform that **produces** products. Runs on PF-side (SaaS) or installed on-prem/OEM. Python. |
| **PF Runtime** | (Separate feature) an engine that **executes** an agent/EAP product. **Parked** — only needed if PF ships agent products. |
| **Generated product** | What the Factory produces. Runs **on its own** stack (chosen by the Technology Selection Engine). Independent of PF's stack. |
| **EAP (manifest role)** | The **authoritative delivery/build manifest** — composition of the contracts that says what to build/ship/license/deploy. **Kept.** |
| **EAP (executor role)** | A runtime that interprets the EAP to run a product. **Parked.** |
| **Component Manifest** | Per-component declaration: `language`, `runtime_required`, `customer_delivered`, `compiled`, `ip_zone`, `license`. Drives packaging. |
| **Runtime Dependency Compiler (RDC)** | Reads EAP + build/deployment profiles → emits exactly what ships (the **IP-leakage guard**). |

**EAP is still needed** — but in the current context it is the **delivery manifest**, not an execution engine.
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
| 14 | Dashboard → TypeScript | **violates** | `AGENTS.md` frozen dashboard | **reject** |
| 15 | IP zones A/B/C; SaaS-first | aligned | doc §13 | approve; lead with SaaS + licensing |
| 16 | Product portfolio / editions | new-path | no edition packaging | **needed now** (profiles) |

No `derails`/`stale`. One `violates` (#14) → rejected. The doc as a whole is a **major new path**, approved via this review.

---

## 4. IP-protection strategy

### 4.1 The problem
The PF platform is **100% Python** (`core/packaging.py:123` ships `source_dir`; no compilation, no source exclusion;
632 tracked `.py`). Deploying it on-prem/OEM exposes readable source → IP/reverse-engineering risk and loss of
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
2. **New logic that ships in a customer edition and is sensitive → Go.** Build-time-only / SaaS-only / experimental → Python.
3. **Existing/remaining → compiled** (no raw `.py` shipped).
4. **One baseline for all editions** (build profiles; no forks).
5. **Later: rewrite high-value modules → Go** (per the IP-value assessment).
6. **Later (aspiration): rewrite remaining → Go** — retain the compiled-Python escape hatch.

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
- **Build-time tooling (never shipped):** tests, docs/dev scripts — stay Python.

### 4.6 How Go and Python coexist (same environment)
```text
on-prem host
┌───────────────────────────────────────────────┐
│ PF platform core — Go (compiled)              │  strong protection
│  orchestration, planning, tech-selection,     │
│  licensing, packaging, model-routing logic    │
│              │ contract (JSON/HTTP/gRPC)      │
│              ▼                                 │
│ remainder — Python (compiled via Nuitka)      │  partial protection (no readable .py)
│  as subprocess/sidecar/worker                 │
└───────────────────────────────────────────────┘
```
- **Go = host/core.** **Python = sidecar/worker** over a **contract**.
- Python ships **compiled**; Go ships as a **native binary**.
- The **Component Manifest** declares the Python worker (language, license, BOM) — explicit, not hidden.
- As logic migrates to Go, the Python footprint shrinks and protection improves.

### 4.7 Value retention (beyond hiding source)
**Signed updates** (only PF issues new versions) + **licensing/entitlements** + keeping the *living* intelligence
(models, learnings, new capabilities) under PF's control.

### 4.8 One codebase, one implementation per feature (the language rule)
There is **one repo / one baseline**. SaaS and customer editions differ by **build profile**, never by a second
codebase.

- **SaaS** runs the **source** (Python, plus any Go) server-side — nothing ships, so no compilation is needed.
- **Customer** **compiles the same source** (`go build` for Go; **Nuitka** for Python) and ships the compiled
  artifact + license. **No raw `.py`.**

**Each feature is implemented in exactly one language** (decided at design time, A6):

| If the feature… | Language | SaaS runs | Customer ships |
|---|---|---|---|
| ships to customers **and is sensitive/IP-bearing** | **Go** | Go | Go binary |
| ships but is **low-sensitivity/plumbing** | **Python** | Python | **compiled** Python (Nuitka) |
| is **PF-side only** (SaaS/build-time/tooling/tests/docs) | **Python** | Python | not shipped |
| is **AI/ML-heavy** or **experimental** | **Python** | Python | compiled / declared worker |

**Hard rules:**
- **Build time compiles — it never translates.** `go build` and Nuitka are different mechanisms; there is **no**
  "Python → Go at compile time."
- **No duplication.** A feature is **either Go or Python**, never both. Migration is a **one-time deliberate
  replacement** (BI-PF-0386, by value), not a parallel copy.
- **Language is chosen by placement:** *"will this ship to a customer and does it matter?"* → Go; else Python.
- The **Go footprint grows over time** as high-value Python modules are migrated; SaaS always runs the current
  baseline; the customer artifact is always its compiled form.

---

## 5. Target architecture (PF platform)

```text
PF FACTORY (build)  ── Product Compiler ──►  EAP (delivery manifest)
      │                                            │
      │ contracts: ProductSpec, TechnologyProfile, RuntimeProfile,
      │   DeploymentProfile, LicenseProfile, EntitlementProfile,
      │   ComponentManifest, BOM, Evidence
      │                                            ▼
      │                                  Runtime Dependency Compiler
      │                                            │
      │                          (build profile + OS/arch + license/entitlement)
      │                                            ▼
      │                                  compiled, signed customer package
      │                                            │
      │                          Go core + compiled-Python sidecar + license
      ▼                                            ▼
   build profiles (community/professional/enterprise/on-prem/airgap/oem/embedded)
```

Two compiler stages: **Product Compiler** (requirements → product + EAP) and **Runtime Package Compiler**
(EAP + profiles → signed package). The **RDC** is the IP-leakage guard.

---

## 6. Phases & epics

### EPIC A — PF Commercial & IP Foundation (needed now)
| Item | Deliverable | Depends on | Fixture |
|---|---|---|---|
| A0 | Baseline freeze; reconcile doc (amendment = authority; fix 16- vs 39-stage); **ADR register** | — | repo SHA + test baseline |
| A1 | **Contracts** (thin, grow by need) incl. the **Go↔Python contract** | A0 | `sample-*/…` fixture |
| A2 | Capability Registry + entitlement-at-boundary + **asymmetric licensing** | A1 | license issued+verified |
| A3 | **Compiled packaging** (Nuitka) + signing + SBOM/LBOM + **no-raw-`.py` release gate** | A1,A2 | compiled package |
| A4 | **EAP (manifest)** + validator/registry + compatibility | A1 | `sample.eap` |
| A5 | **Runtime Dependency Compiler** (authoritative composition engine) | A1,A4 | `sample-runtime-package/` |
| A6 | Governance: change classifier + drift guard + no-undeclared-dep + language rule | A1 | gate on the fixture |
| A7 | **Vertical slice**: Requirement→Tech→Factory→EAP→RDC→compiled+signed package | A1–A6 | e2e |

### EPIC B — Scale & Extensions (trigger/evidence-gated)
| Item | Deliverable | Trigger |
|---|---|---|
| B1 | **PF Go core** (compiled host; new shipped/sensitive logic lands here) | none — architectural |
| B2 | Gateways (Model/Tool/Memory/Infra) | provider coupling hurts |
| B3 | Persistence scaling (SQLite/JSON/Postgres) | scale/HA need |
| B4 | OEM / white-label profiles | OEM deal |
| B5 | Rust protected components | measured security/perf |
| B6 | WASM plugins | plugin contract + need |
| B7 | Service decomposition | independent scaling/security |
| Bmig | **Migrate high-value → Go**, then remaining | IP-value assessment |

### Backlog items created
- **BI-PF-0386** — IP-value assessment of PF platform modules (rewrite-by-value ranking).
- **BI-PF-0387** — PF platform delivery baseline (one source; new→Go; existing→compiled; no raw `.py`). *(blocked_by 0388)*
- **BI-PF-0388** — ADR: shipped editions use compiled artifacts; never raw `.py`; one source many editions.

---

## 7. Execution order (in order, with gates)

```text
STEP 0  ADR + strategy lock          (BI-PF-0388)   → decision recorded in the A0 register
STEP 1  A0 baseline freeze           → repo SHA, test baseline, doc reconciliation, ADR register
STEP 2  A1 contracts (thin)          → ProductSpec…ComponentManifest…BOM…Evidence + Go↔Python contract
STEP 3  A2 licensing/entitlements    ∥  A4 EAP (delivery manifest + compatibility)
STEP 4  A3 compiled packaging        → Nuitka build + signing + SBOM/LBOM + NO-RAW-.py release gate
STEP 5  A5 Runtime Dependency Compiler (authoritative composition engine)
STEP 6  A6 governance                → change classifier + drift guard + language rule + no-undeclared-dep
STEP 7  A7 vertical slice            → Requirement→Tech→Factory→EAP→RDC→compiled+signed package   [APPROVAL GATE]
────────────────────────────────────────────────────────────────────────────────────────────
STEP 8  B1 PF Go core (seam)         → minimal Go host + Go↔Python contract wired
STEP 9  BI-PF-0386 IP-value assessment → ranked module list (drives migration)
STEP 10 Bmig migrate high-value → Go  → replace, not duplicate
STEP 11 (B2 gateways ∥ B3 persistence ∥ B4 OEM profiles)   [trigger-gated]
STEP 12 Bmig migrate remaining → Go (aspiration)   ∥   B5 Rust / B6 WASM / B7 decomposition (defer)
```

**Critical path:** A1 contracts → A3 compiled packaging → A4 EAP(manifest) → A5 RDC → A7 vertical slice.
**Two prerequisites** before "new sensitive logic → Go" can start: **B1 Go seam** and **A3 compiled packaging**.
**Gate:** no normal feature work until the A7 vertical slice passes; the customer package must contain **no raw `.py`**.

---

## 8. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Go slows feature velocity | only shipped/sensitive new logic → Go; build-time/SaaS stays Python |
| Long-lived Go+Python hybrid complexity | contract-first; small seam (A1) |
| Compiled-Python fragility (dynamic imports/eval/C-ext) | test compiled build in CI; avoid dynamic features in shipped modules |
| Team Go skill | tiny kernel first; grow gradually |
| "All → Go" never finishes | treat as aspiration; keep compiled-Python escape hatch |
| Over-promising IP protection | pair compiled artifacts with licensing + signed updates |
| Doc internal inconsistency (16 vs 39 stage) | reconcile in A0 |

---

## 9. Open questions
1. **Confirm strategy** (options 1–6) and the refinements (new→Go only for shipped/sensitive).
2. **Compiled-Python acceptance:** is Nuitka-level protection acceptable for early on-prem, or is Go required from the start?
3. **Edition priority:** which of Community/Professional/Enterprise/VPC/on-prem/air-gap/OEM ships first after SaaS?
4. **Go seam contract:** JSON-over-stdio, HTTP, or gRPC for Go↔Python?
5. **ADR register location** (`docs/adr/` vs existing `docs/guidelines/architecture/decisions.md`).
6. **Scope of A7 vertical slice:** which real PF product is the reference fixture?

---

## 10. Appendix — commercial Python IP practices (see companion answer)
Compiled packaging (Nuitka/PyInstaller/PyArmor), licensing/entitlement, SaaS-first, source-available vs proprietary
splits, signed updates, and keeping high-value intelligence server-side are the industry norms. See the analysis
in the companion response.
