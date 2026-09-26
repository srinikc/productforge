# Product One-Stop Page (Portal) — design

Owner: Product Forge. Status: **design (proposal)**. Companion: `docs/multimodel_architecture_support.md`,
`docs/tools-and-generators.md`. Backlog: backend BI-0215..0218, dashboard BI-0147..0149.

**What it is:** ONE page per product that is the single place to (a) **manage the build** and (b) **present,
launch and operate the finished product**. It is separate from the pipeline-engineer / engine pages
(stage runners, logs, model router) which stay separate.

---

## 1. Why one page (usability review)

Two audiences share one identity over a lifecycle:

| Audience | When | Wants |
|---|---|---|
| **Builder / operator** | during build | artifacts, feature status, quality, progress %, blockers, cost |
| **Owner / GTM / support** | after build | what it is, launch, docs, deploy, BOM/footprint, links, releases, maintenance |

- **Two separate pages** -> fragmentation, duplicated/contradicting data, broken links.
- **One flat page** -> engineer + GTM content mixed = clutter.
- **Chosen:** **one route, two tabs (Project Management | Product), default tab driven by lifecycle state.**
  Same identity; emphasis shifts as the product progresses. It is the "one-stop page".

---

## 2. Lifecycle states (the spine)

`ideation -> designing -> building -> verifying -> built -> launching -> live -> maintaining` (+ `on-hold`, `archived`).

| State | Driven by | Default tab |
|---|---|---|
| ideation | idea/intake + feasibility triage (BI-0214) | Project Management |
| designing | stages 0a..1d, 2 | Project Management |
| building | stages 4-0..4f (+4m) | Project Management |
| verifying | stages 5..7 + evals | Project Management |
| built | quality gate GO + package ready | both (Product enabled) |
| launching | deploy/pre-production/production | Product |
| live | deployed + observability active | Product |
| maintaining | change requests / releases rolling | Product (+ PM = change history) |

---

## 3. What the page shows at each state (what / where / how)

| State | Project Management tab | Product tab | Source of truth |
|---|---|---|---|
| ideation | idea, feasibility triage, modalities/packs, provisional cost | stub ("in progress") | intake, feasibility.json, capability profile |
| designing | features F-x being defined, requirements/IDs, arch+ADRs, NFRs, delivery mode | stub | design/architect artifacts |
| building | **progress % by phase**, feature status, artifacts per stage, quality gates, blockers, budget actuals, activity/decisions | stub | backlog, artifacts, run_quality_gate, progress |
| verifying | quality summary (security/NFR/tests/evals/go-no-go), change log | drafts (what it is, deploy brief, docs) | compliance, qa, evals, package |
| built | history + change requests | **launch link, docs/guides, install/deploy brief, BOM/footprint, links, versions** | package, BOM, docs, metadata |
| live | change requests -> features -> releases | product details, health/observability, releases, roadmap, feedback | portfolio, change_spec, observer |
| maintaining | maintenance/changes | product details + release history + support | observer, product-analytics, support |

---

## 4. Traditional SDLC vs AI-era SDLC — what changes (and what does not)

**Traditional SDLC:** requirements -> design -> build -> test -> deploy -> maintain.
Post-release = ops/monitoring, bug fixes, versioned releases, support, roadmap, sales/marketing, customer
success. Roles: PM, dev, QA, DevOps, support, GTM.

**What AI engineering ADDS (the page must reflect it):**

| Concern | Traditional | AI-era addition |
|---|---|---|
| "Testing" | unit/integration/QA | + **evals** (offline/online), thresholds, non-determinism, human review |
| Versioned artifacts | code, build | + **prompt/model/agent versions** (registry, A/B, model swaps) |
| Quality | correctness, perf | + **model quality** (hallucination, drift, toxicity), guardrails |
| Cost | infra | + **per-unit/token media cost** tracked as a quality dimension |
| Observability | uptime logs | + **AI observability** (traces, model quality, drift) — OTel GenAI |
| Data | — | + **feedback loop / data flywheel** (feedback -> dataset -> improve) |
| Release | versioned deploy | + prompt/config changes that may ship **without** a full release |
| Governance | security | + model cards, provenance (C2PA), EU AI Act / NIST AI RMF compliance |
| Skills/agents | — | tool/agent reliability, retrieval quality, agent traces |

**What does NOT change:** requirements, design, release discipline, support, GTM, maintenance — same
product discipline. AI adds an **eval + observability + versioning + feedback** layer around it.

---

## 5. Information architecture

```
/products/<id>                       (one route, role-aware)
 ├─ Header:  identity · lifecycle state · overall progress % · quality chip · cost vs budget · key links
 ├─ Tab: Project Management
 │    progress by phase · features (F-x) table+status · artifacts by stage · quality summary ·
 │    blockers · budget/cost · activity + decisions · change requests
 └─ Tab: Product
      what it is · launch · docs/guides · install/deploy brief · BOM/footprint (runtime req, licenses,
      sizes) · links (sales/onboarding/support) · versions/releases · maintenance/observability
```

Nav placement: under a **Products** section (portfolio list -> product page). Pipeline-engineer pages
(stage runner, logs, model router) remain separate and are linked from the PM tab, not merged here.

---

## 6. Wireframes (ASCII)

### 6a. Project Management mode (during build)
```
┌ Product: Helios Reels ─────────────────────────────── lifecycle: BUILDING ── 68% ── Q: passing ┐
│ [ Project Management ]  Product(stub)         Owner: A. Rao   Cost: ₹42k/₹80k   ─── links ───  │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ PROGRESS  P1 ok · P2 ok · P3 ok · P4 ok · P5 ▓▓▓▓▓░░ 68% · P6 · P7 · P8                         │
│ FEATURES  F-1 done · F-2 done · F-3 in-progress · F-4 queued · F-5 queued                      │
│ ARTIFACTS 1 Design ok · 2 Arch ok · 4a Impl ok · 4m Media ok · 5 Security pending              │
│ QUALITY   gates: compile ok · audit ok · tests 469/469 · media-qa ok · evals 0.87 (>=0.85 ok)  │
│ BLOCKERS  3 (overflow, ...)                        BUDGET  ₹42k of ₹80k (media 61%)            │
│ ACTIVITY  recent decisions / approvals / change requests                                       │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 6b. Product mode (after build)
```
┌ Product: Helios Reels ─────────────────────────────────── lifecycle: LIVE ── v1.2.0 ─────────┐
│ Project Management(history)  [ Product ]        Owner: A. Rao   ─────── product links ─────── │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ WHAT IT IS   AI short-video generator + editor (image/video/music/voice)                       │
│ LAUNCH       https://app.example.com   ▸ status: live, 99.9%, region: India                    │
│ DOCS/GUIDES  user guide · admin guide · API · release notes                                     │
│ INSTALL/DEPLOY  docker compose · env vars · GPU/CPU footprint (brief)                           │
│ BOM/FOOTPRINT   models: FLUX-schnell(6.0GB), Wan-1.3B(3.0GB), Kokoro(0.3GB), Whisper(1.5GB)    │
│                 licenses: Apache-2.0 x4 (bundle-safe) · runtime: 12GB VRAM min                 │
│ LINKS        sales deck · pricing · customer onboarding · support · status page                 │
│ RELEASES     v1.2.0 (2026-..) · v1.1.0 · v1.0.0        MAINTENANCE  change requests · health    │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Data mapping (element -> source of truth -> API)

| Element | Source of truth | Read-model API |
|---|---|---|
| identity, owner, links, launch | product registry (BI-0215) | `/products/<id>` |
| lifecycle state | product registry (BI-0215, derived) | `/products/<id>` |
| progress %, phase | progress / portfolio | `/products/<id>/progress` |
| features + status | backlog (project scope) | `/products/<id>/features` |
| artifacts by stage | stage_paths / asset store | `/products/<id>/artifacts` |
| quality summary | run_quality_gate / compliance / evals | `/products/<id>/quality` |
| budget/cost | budget_planner (+ per-unit media) | `/products/<id>/cost` |
| BOM/footprint | packaging (BI-0217) | `/products/<id>/bom` |
| releases/versions | releases / portfolio | `/products/<id>/releases` |
| activity/decisions | events / approvals / backlog history | `/products/<id>/activity` |

Everything is **derived** (single writer per store); the page never hand-maintains data. Only a tiny
editable **metadata/links** set lives in the registry (owner, launch URL, links).

---

## 8. Post-build operations (what happens after the product is built)

- **Launch:** deploy (BI: production-deploy), pre-production checks, go-live link + status page.
- **Operate:** observability (uptime + **AI quality**), cost/token tracking, incident/on-call.
- **Support / success:** customer-success agent, onboarding, support links.
- **GTM:** marketing/pricing/sales artifacts, sales deck, pricing page.
- **Maintain / evolve:** change intake -> `change_spec` -> features -> iterations -> releases; versioning;
  deprecation/archival.
- **Feedback loop (AI):** user feedback + telemetry -> eval sets -> prompt/model improvements -> new version.

---

## 9. Lifecycle / workflow (ASCII)

```
 idea ─► designing ─► building ─► verifying ─► built ─► launching ─► live ─► maintaining ─► (archived)
   │         │            │            │          │          │          │            │
 PM tab ────┴────────────┴────────────┴──────────┘          │          │            │
                                        Product tab ────────┴──────────┴────────────┘
                                                             │
                          feedback loop:  live telemetry ─► evals ─► change requests ─► next release ─┘
```

---

## 10. Backlog created for this

**Backend:** BI-0215 product registry + lifecycle + metadata/links · BI-0216 one-stop read-model API ·
BI-0217 BOM/footprint artifact · BI-0218 AI-era operations layer (evals + prompt/model versioning +
feedback + model-quality observability).
**Dashboard:** BI-0147 EPIC product one-stop page · BI-0148 Project Management tab · BI-0149 Product tab.

Existing pieces reused: `portfolio`, `progress`, backlog, `run_quality_gate`, `package`, `change_spec`,
`observer`, `product-analytics`, `customer-success`, `growth`, `finops`.
