# Pipeline Phases Proposal — Business, Market, Monetization & Operate

| Field | Value |
| --- | --- |
| Status | Proposal — owner-approved target design recorded for implementation planning |
| Owner | `product-owner` |
| Scope | Pipeline phases, stages, agents, per-project tailoring |
| Model-class legend | `R` Reasoning · `G` Generation · `C` Coding · `I` Insight/Analysis |
| Related docs | `docs/PIPELINE-TEMPLATE-SPEC.md`, `docs/schemas/pipeline-template.v1.schema.json`, `docs/PIPELINE-CODE-TRUTH.md`, `docs/STRUCTURE-CONTRACT.md` |

This document records an approved design. It is descriptive of the target pipeline; implementation is sequenced in section 11 and governed by the repo working agreement (plan and confirmation before coding, wire-before-done, compliance and Go/No-Go gates).

---

## 1. Purpose

Product Forge's pipeline must be a **customizable, adaptable orchestrator**. It must be able to build, end to end:

- a **product** (software product with users and revenue),
- a **system** (internal or platform system),
- a **workflow** (process automation),
- a **research** project (investigation and findings),
- a **simple app** (small, single-purpose application),
- a **hardware/software (IoT)** project (device + firmware + service),
- a **media** project (content, publishing, distribution).

For each, the pipeline must **tailor its phases, stages, agents, and their order to the idea** rather than forcing every idea through one fixed sequence.

The pipeline must also **self-educate**: when the idea requires domain knowledge the pipeline does not yet hold, it must research the domain, compile that knowledge into reusable assets, register the resulting skills, and use them within the same run.

Two consequences drive this proposal:

1. The common pipeline gains two phases today missing from it — business/market/monetization (before design) and operate/grow/engage (after delivery).
2. The pipeline gains four **adaptation mechanisms**: per-project pipeline tailoring, dynamic agent creation, dynamic knowledge/skill acquisition, and a single-source-of-truth runtime integration that keeps every projection consistent.

---

## 2. Current state (verified)

| Fact | Verified value |
| --- | --- |
| Stages | **32** |
| Phases | **6** |
| Agents per stage | **1** (one MAIN agent per stage) |
| Business / growth / customer / ops agents | exist as **CARDS** but are **NOT wired** into the pipeline |
| `product-owner` | **orphan** (defined, not reachable on the runtime path) |
| `marketing` | **sub-agent of `document`** (not a first-class stage owner) |
| Templates | `pipeline_templates/` exist **but are NOT wired** (legacy dashboard only) |
| Dynamic agent creation | **does not exist** |

### 2.1 Templates and schemas that already exist (unwired)

| Asset | Path | Status |
| --- | --- | --- |
| Template set | `pipeline_templates/` | exists, legacy dashboard only, not runtime-wired |
| Template schema | `docs/schemas/pipeline-template.v1.schema.json` | exists |
| Template spec | `docs/PIPELINE-TEMPLATE-SPEC.md` | exists |

These are the intended basis for the per-project customization described in section 7 (wire as-is, or extend).

### 2.2 Dynamic knowledge / skill modules that already exist

| Module | Role |
| --- | --- |
| `core/domain_research.py` | domain research over the web |
| `core/knowledge_compiler.py` | compile gathered material into knowledge artifacts |
| `core/skills_registry.py` | register skills |
| `core/skill_contracts.py` | skill contracts / interfaces |
| `core/business_skills_selector.py` | select business skills for a context |
| `core/squad_manager.py` | squad composition, includes a `web_search` tool |

### 2.3 Advisors that already exist

| Advisor | Role |
| --- | --- |
| `target_advisor` | target / goal advisory |
| `integration_advisor` | integration advisory |
| `model_recommendation` | model selection advisory |

The building blocks for adaptation are present; what is missing is **wiring** them onto the runtime path and giving them a place in the phase/stage model.

---

## 3. New Phase 1.5 — Business, Market & Monetization (stages 0b–0e)

**Position:** runs **after stage 0a** (discovery) and **before the design phase**. It converts a raw idea into a validated business, market, pricing, and go-to-market position that the design and build phases then serve.

| Stage | Name | MAIN agent | Supporting agents | Artifact | depends_on | Approval gate | Next | Model |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **0b** | Business & Product Definition | `product-owner` | — | `business-brief.md` | 0a | Owner approves problem, users, value, scope, AI/MOAT thesis | 0c | R |
| **0c** | Market, Competition & Positioning | `researcher` | `scout`, `analyst` | `market-analysis.md` | 0b | Owner approves market, competitors, positioning | 0d | R / I |
| **0d** | Monetization & Unit Economics | `pricing-strategist` **(NEW)** | `finops` | `monetization.md` | 0b, 0c | Owner approves pricing model and unit economics | 0e | R |
| **0e** | Go-to-Market & Customer Journey | `marketing` **(promoted)** | `growth` **(NEW)**, `customer-onboarding` | `gtm-plan.md` | 0b, 0c, 0d | Owner approves GTM plan and journey | Design phase | G |

### 3.1 Stage detail — inputs, gate, handoff

| Stage | Required inputs | Gate decision recorded on | Handoff consumed by |
| --- | --- | --- | --- |
| 0b | idea brief / 0a output, constraints | `business-brief.md` | 0c, 0d, 0e, design, `ai-integration-recommendation` |
| 0c | `business-brief.md` | `market-analysis.md` | 0d, 0e, design |
| 0d | `business-brief.md`, `market-analysis.md` | `monetization.md` | 0e, design, operate |
| 0e | `business-brief.md`, `market-analysis.md`, `monetization.md` | `gtm-plan.md` | design, operate, growth |

Each stage is a **gated** stage: the artifact is produced, the owner reviews and approves, and only then does the next stage start. A rejected gate returns the stage to its MAIN agent with recorded feedback.

---

## 4. New Phase 7 — Operate, Grow & Engage (stages 13, 13a, 13b)

**Position:** runs **after stage 12** (delivery/launch). **OPT-IN per project** — a project declares whether Phase 7 is enabled during tailoring (section 7). When disabled, the pipeline ends at 12.

| Stage | Name | MAIN agent | Supporting agents | Artifact | depends_on | Approval gate | Model |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **13** | Operate & Observability | `observer` | `post-production`, `maintenance`, `performance` | `ops-report.md` | 12 | Owner approves operational readiness and observability coverage | I |
| **13a** | Customer Success & Support | `customer-success` **(NEW)** | `customer-onboarding` | `customer-success-playbook.md` | 13 | Owner approves support model and success playbook | G |
| **13b** | Growth, Engagement & Feedback | `growth` **(NEW)** | `community-social` **(NEW)**, `marketing`, `analyst`, `insight-extractor` | `growth-plan.md` | 13, 13a | Owner approves growth plan and feedback loop | I |

Phase 7 closes the loop: production telemetry (13), customer signal (13a), and growth/engagement feedback (13b) feed back into the next idea cycle.

---

## 5. Agent roster changes

### 5.1 Promotions to MAIN (existing agents)

| Agent | Current state | New role |
| --- | --- | --- |
| `product-owner` | orphan | MAIN — stage 0b |
| `marketing` | sub-agent of `document` | MAIN — stage 0e (supporting at 13b) |

### 5.2 Promoted from sub-only to MAIN-capable (existing agents)

These agents exist but are only reached as sub-agents. They become MAIN-capable so they can own a stage when tailoring selects them:

`finops`, `researcher`, `customer-onboarding`, `observer`, `maintenance`, `post-production`, `performance`, `scout`, `analyst`, `guardian`, `quality_gate`, `a11y-audit`, `static_verifier`, `security-audit`, `iterative_evaluator`, `consensus`.

### 5.3 NEW MAIN agents to create

| Agent | Owning stage | Purpose |
| --- | --- | --- |
| `pricing-strategist` | 0d | pricing model, packaging, unit economics |
| `growth` | 0e / 13b | acquisition, activation, retention, growth loops |
| `customer-success` | 13a | onboarding, support model, success playbook |
| `community-social` | 13b | community, social, engagement |
| `sales-crm` *(optional)* | 0e / 13b | pipeline, CRM, sales motion |
| `legal-privacy` | cross-cutting | legal, privacy, licensing, compliance posture |
| `product-analytics` | 13 / 13b | product analytics, metrics, instrumentation |

Each new agent is created through the same definition path as the dynamic-agent mechanism (section 8): capabilities, model, prompts, inputs, artifacts, and dependencies, validated and stitched into the pipeline before it can own a stage.

---

## 6. AI Integration = MOAT (mandatory ASK, optional IMPLEMENT)

AI integration is treated as the product's primary differentiator, so it is **mandatory to ask** and **optional to implement**:

- **Mandatory ASK:** `product-owner` (stage 0b) and `architect` (stage 2) **MUST** produce an `ai-integration-recommendation`.
- **Optional IMPLEMENT:** an optional stage **4g AI Integration** runs only if the recommendation is accepted.

| `ai-integration-recommendation` field | Content |
| --- | --- |
| Runtime AI capability | what the product does with AI at runtime |
| Workflow | where AI sits in the user journey / job to be done |
| Data | data required, sources, quality, rights |
| Models | model class / provider / hosting choices |
| Guardrails | safety, evaluation, fallbacks, human-in-the-loop |
| Cost | inference cost, unit economics impact |
| Differentiation / MOAT | why this is hard to copy and how it compounds |

**Decision:**
- accepted → optional stage **4g AI Integration** is enabled for the project;
- declined → the recommendation and rationale are recorded and the pipeline proceeds without 4g.

---

## 7. Dynamic per-project pipeline (customization)

Every project runs a **customized pipeline** generated from the common pipeline, not the common pipeline verbatim.

**Mechanism — a Pipeline Tailoring step at stage 0b:**

1. From the idea/goal (`business-brief.md`), recommend which **optional phases, stages, and agents** apply.
2. Write **`pipeline-plan.json`** — the per-project list of enabled stages and agents.
3. The **user accepts or overrides** in the dashboard (accept/override is recorded on the plan).
4. The **executor honors the plan**: disabled optional stages are skipped; enabled optional stages run in their declared order.

| `pipeline-plan.json` field | Meaning |
| --- | --- |
| `project_kind` | product / system / workflow / research / simple app / IoT / media |
| `enabled_stages` | ordered stage ids that will run |
| `disabled_stages` | optional stage ids skipped for this project |
| `enabled_agents` | MAIN agents engaged per stage |
| `phase_7_enabled` | whether Phase 7 (13, 13a, 13b) runs |
| `ai_integration_enabled` | whether optional stage 4g runs |
| `overrides` | user accept/override decisions and rationale |
| `tailored_at` / `tailored_by` | provenance of the plan |

**Basis:** reuse the existing `pipeline_templates/` system and `docs/schemas/pipeline-template.v1.schema.json` (currently unwired, legacy dashboard only). Decide in section 12 whether to wire as-is or extend; either way, the tailoring step emits `pipeline-plan.json` and the executor consumes it.

---

## 8. Dynamic agent creation

The pipeline can **create/add a MAIN agent** when the idea needs a capability no existing agent covers.

| Definition field | Content |
| --- | --- |
| Identity | name, role, kind (MAIN) |
| Capabilities | what the agent can do |
| Model | model class / tier assignment |
| Prompts | system + task prompts |
| Inputs | artifacts/context it consumes |
| Artifacts | artifact it produces |
| Dependencies | stages/agents it depends on and feeds |

**Flow:**
1. AI **recommends** an agent from the idea/goal, and/or the **user defines** one.
2. The definition is **validated** (schema, capabilities, uniqueness).
3. It is **stitched into the pipeline** (assigned a stage/position) and **registered** so the runtime can route to it.
4. Registration keeps the source-of-truth files in section 10 consistent.

---

## 9. Dynamic knowledge / skill acquisition

When the pipeline lacks domain expertise for an idea, it **self-educates** within the run:

1. **Research** the net, open-source projects, and blogs for the domain.
2. **Compile** the gathered material into knowledge artifacts (`core/knowledge_compiler.py`).
3. **Register skills** and their contracts (`core/skills_registry.py`, `core/skill_contracts.py`).
4. **Use** the registered skills in the relevant stages (via `core/business_skills_selector.py` and `core/squad_manager.py`).

**Modules to wire onto the runtime path:** `core/domain_research.py` + `core/knowledge_compiler.py` + `core/skills_registry.py` / `core/skill_contracts.py` + the `web_search` tool in `core/squad_manager.py`.

---

## 10. Runtime integration / single source of truth

These files and surfaces **MUST change together** for any phase/stage/agent change. A change to one without the others leaves the pipeline inconsistent (unwired or misrouted).

| Artifact | Change required |
| --- | --- |
| `pipeline-definition.json` | add Phase 1.5 (0b–0e), Phase 7 (13, 13a, 13b), optional 4g |
| `config/agent-hierarchy.json` | promotions, new MAIN agents, MAIN/supporting changes |
| `config/agent-requirements.json` | requirements for new/changed stages |
| `config/model-tier.json` | model class per new stage — **ALL profiles + kctier** |
| `config/discovery-panel-settings.json` | discovery panel entries for new stages |
| `core/orchestrator/artifacts_map.py` | artifact mapping for new artifacts |
| `core/pipeline_telemetry.py` | `PHASE_MAP` entries for new phases/stages |
| `config/store-registry.json` | register any new store with a single writer |
| State files / status / artifacts / backlog | reflect new stages in run state and work tracking |
| Dashboard | surface new stages, `pipeline-plan.json`, and accept/override controls |

Because `config/model-tier.json` must cover **all profiles plus kctier**, adding a stage is never a single-file edit.

---

## 11. Sequencing

1. **Implement after the current spec work** completes — this proposal is not a parallel workstream.
2. **Targeted re-run from 0a**, not a full redo: `invalidate_for_rerun(only_stages=['0a'], run_only=True)` plus **artifact-provenance consumers**, so only stages downstream of the changed Phase 1.5 definition re-run.
3. Wire each addition on the runtime path (invoked, not just defined) and close with an explicit wiring update, per the repo working agreement.

---

## 12. Open decisions

| Decision | Option A | Option B | Notes |
| --- | --- | --- | --- |
| `sales-crm`, `legal-privacy` timing | create now, in the first roster change | defer to a later roster change | legal-privacy is cross-cutting and can be added independently |
| Pipeline tailoring owner | reuse the existing `orchestrator` | create a new `pipeline-tailor` agent | reuse is fewer moving parts; a dedicated agent is more adaptable |
| Templates | wire `pipeline_templates/` as-is | extend them for tailoring and Phase 7 | as-is is faster; extending supports per-project plans directly |

Each decision is resolved before implementation of the affected part, recorded against the owning backlog item, and reflected back into this document.

---

## 13. Business-models knowledge base & dynamic learning

The business agents (`product-owner`, `pricing-strategist`, `marketing`, `growth`, `researcher`, `finops`) must not reason from thin air — they **refer to a curated business knowledge pack**, and **learn** when it lacks what is needed.

- **Business-models pack (curated, versioned)** — business model canvases, revenue & pricing models, unit-economics formulas, GTM playbooks, growth loops, market-sizing methods, competition frameworks. Stored as a knowledge/skills pack with **source + version + `fetched_at` + a staleness/refresh check** (same pattern as the model-cost registry).
- **Refer-then-learn fallback** — if a needed model/skill is absent, the pipeline **researches the net / open-source / blogs**, compiles it into knowledge, registers it as a skill, and uses it (wires `core/domain_research.py` + `knowledge_compiler.py` + `skills_registry.py` / `skill_contracts.py` + `web_search`).
- **Tracked as** `product_forge:BI-0119` (business-models KB) + `product_forge:BI-0118` (dynamic knowledge/skill acquisition), surfaced in the dashboard via `project:ProductForge-Dashboard:BI-0093` (Knowledge & Skills browser).

---

## 14. API-first (owner convention)

**Everything on the pipeline backend is API-first.** Every capability in this program (phases 0b–0e / 13–13b, agent roster, AI-integration recommendation, dynamic tailoring, pipeline templates, dynamic agent creation, dynamic knowledge/skill acquisition, business-models KB, model-tier, runtime integration) is exposed through the **backend API with a stable contract**; the dashboard consumes **only** the API (no direct store access or writes). Tracked as `product_forge:BI-0122`.

---

## 15. Backlog index (tracked)

Backend (`product_forge`): **BI-0111** phase 0b–0e · **BI-0112** phase 13–13b · **BI-0113** roster · **BI-0114** AI-integration/MOAT · **BI-0115** dynamic tailoring · **BI-0116** wire templates · **BI-0117** dynamic agent creation · **BI-0118** dynamic knowledge · **BI-0119** business-models KB · **BI-0120** model-tier · **BI-0121** runtime integration · **BI-0122** API-first.

Dashboard (`ProductForge-Dashboard`): **BI-0087** business/market views · **BI-0088** operate/grow views · **BI-0089** tailoring UI · **BI-0090** agent builder · **BI-0091** AI-integration view · **BI-0092** template gallery · **BI-0093** knowledge & skills browser · **BI-0094** model-tier editor.
