# Generation Proportionality — Agents & Artifact Registry work plan

> Epic **BI-PF-1388** (children BI-PF-1389..1393) + the originating defect **BI-PF-1333**.
> Status: planned/groomed; not implemented. Backlog created and ordered via the backlog API.

## 1. Problem

The **Artifact Contract Registry** (epic BI-PF-1342) aligned every agent/stage to an artifact contract and
**validates** output against it — but it does **not** drive generation:

- Agent prompts hardcode large templates — `agents/design.agent.json` (design.md sections 3.1–3.10),
  `agents/architect.agent.json` (NFR mapping sections 6.1–6.21).
- The **generation section list** comes from `config/agent-requirements.json::required_sections`
  (`core/orchestrator/agent_runner.py:948-952`), **not** from the artifact contract.
- The **project-size profile** (`config/artifact-contracts/profiles.json`: small/medium/large) only scales
  `size.target_lines/max_lines` and is **never passed** to `resolve()` (`agent_runner.py:913`,
  `stage_runner.py:105`) → always defaulted to *medium*.

Result (BI-PF-1333): the design stage over-produced **19 FRs + 15 NFRs + 13 user stories** and a **314 KB
partial** for **one trivial feature** (~140k tokens over 11 calls) — slow, costly, disproportionate.

There are therefore **three independent section sources** that drift:

| # | Source | Role today |
|---|---|---|
| 1 | `agents/*.agent.json` `instructions` (hardcoded templates) | what the model is told to write |
| 2 | `config/agent-requirements.json` `required_sections` | the section list the generator iterates |
| 3 | `config/artifact-contracts/{index,agents,profiles}.json` | only used for **post-hoc validation** (BI-PF-1347) + advisory outline gate (BI-PF-1372) |

## 2. Goal — bounded by construction

**One lever** drives each agent's section plan, counts and size:

```
resolve(agent, stage, kind, profile)  from  config/artifact-contracts/{index.json, agents.json, profiles.json}
        │
        ├─ required sections   → always
        ├─ optional sections   → only when the profile says so
        ├─ counts bands        → scaled by the profile
        └─ size budget         → scaled by size_multiplier
```

- **Profile lever** = project size/complexity: `small | medium | large` (extend `profiles.json` beyond size).
- **Kind** = `project_kind` (text/video/… → modality contracts).
- Prompts and the section plan are **derived from the resolved contract** — no hardcoded templates, no drift.

### Behaviour by profile (target)

| Profile | Sections | Counts | Size |
|---|---|---|---|
| small (trivial) | required only | low band | small |
| medium (default) | required + recommended | standard | standard |
| large (complex) | required + recommended + optional | high band | large |

## 3. Wiring plan (single source for generation)

1. **Go op** `artifact_contracts.generation_plan` in `go/pfcore/artifact_contracts.go` (reuse `resolve`):
   returns `{required:[…], optional:[…], counts:{…}, size:{target_lines,max_lines}}` for an agent/stage/kind/profile.
2. **Thin client** `core/contracts.py::generation_plan()` + `core/go_host.py` wrapper.
3. **Generation consumes the plan** in `core/orchestrator/agent_runner.py::_generate_sectioned`
   (replace the `agent-requirements.json` section list; the per-feature loop already exists).
4. **Plumb the project profile** (`project.json`) into `core/contracts.resolve(...)` wherever generation
   resolves (`agent_runner.py:913`, `stage_runner.py:105`).
5. **Prompts become contract-driven** — `agents/design.agent.json`, `agents/architect.agent.json`
   (drop the fixed 3.1–3.10 / 6.1–6.21 blocks; "minimum sufficient"; reference product-wide NFR ids from
   BI-PF-1373). Remove `.opencode/…` references (framework-agnostic).
6. **Enforce** — per-feature FR/US caps + `max_lines` enforced numerically (Go validator), feeding the
   bounded repair (BI-PF-1347); mode via `PIPELINE_ARTIFACT_VALIDATION` (`advisory` → `enforce`).

## 4. Already delivered (context — epic BI-PF-1342, completed)

| Item | What |
|---|---|
| BI-PF-1343 | kind detection + size slider/profiles + per-artifact budget + required/optional sections + counts + schema validators + enforcement wiring |
| BI-PF-1344 | Artifact Contract Registry (Go engine; `config/artifact-contracts/`) |
| BI-PF-1345 | structured schema validators (OpenAPI/CycloneDX/MusicXML) |
| BI-PF-1347 | post-generation `validate_artifact` + repair/compress |
| BI-PF-1348 | budget reconciliation vs the run budget (advisory) |
| BI-PF-1372 | pre-fill **outline/budget gate** (advisory; enforce caps sections) |
| BI-PF-1373 | product-wide DRY for NFRs (stated once; referenced by id) |
| BI-PF-1349 / 1376 | agent registry (specs) + dynamic auto-register/fail-closed |

## 5. Backlog items — order of execution

Execution order is persisted on the epic (`execution_order[]`); dependencies are `REQUIRES`.

| Wave | Item | Title | Depends on | Key files |
|---|---|---|---|---|
| 0 | **BI-PF-1389** | Wire the artifact contract + project-size profile into generation (single source for the section plan) | — | `go/pfcore/artifact_contracts.go`, `core/contracts.py`, `core/orchestrator/agent_runner.py`, `core/orchestrator/stage_runner.py` |
| 1 | **BI-PF-1390** | Contract-driven agent prompts: deprecate hardcoded templates (design 3.1–3.10, architect 6.1–6.21) + remove `.opencode` refs | BI-PF-1389 | `agents/design.agent.json`, `agents/architect.agent.json` |
| 1 | **BI-PF-1391** | Project-size profile lever: small/medium/large selects required-vs-optional sections + counts bands + size budget | BI-PF-1389 | `config/artifact-contracts/profiles.json`, `core/contracts.py` |
| 2 | **BI-PF-1392** | Enforce per-feature FR/US caps + `max_lines` in the Go engine (scaled by profile) + reconcile the three section sources | BI-PF-1389, BI-PF-1391 | `go/pfcore/artifact_contracts.go`, `config/agent-requirements.json` |
| 3 | **BI-PF-1393** | Verify small/medium/large profiles on MyToDo (no over-scope) + close BI-PF-1333 | BI-PF-1390, BI-PF-1391, BI-PF-1392 | run evidence; BI-PF-1333 |
| 4 | **BI-PF-1333** | (defect, re-homed) Design stage over-proportions output — closes on BI-PF-1393 | BI-PF-1393 | — |

### Per item

- **BI-PF-1389 (foundation).** New Go op `generation_plan` + thin client; `_generate_sectioned` builds
  sections from the plan; pass the project profile into `resolve`. Output:
  `{required, optional, counts, size}`.
- **BI-PF-1390 (prompts).** Rewrite the two agent prompts to be contract-driven and "minimum sufficient";
  NFR mapping references product-wide NFR ids; remove `.opencode` drawio references (best-effort neutral CLI).
- **BI-PF-1391 (lever).** Extend `profiles.json` with section/count policy per profile; plumb the profile.
- **BI-PF-1392 (enforce + dedup).** Numeric per-feature FR/US caps + `max_lines` (scaled by profile) in the Go
  validator; reconcile `agent-requirements.json` sections to the contract (or remove the duplicate source).
- **BI-PF-1393 (verify).** Run design/architect for MyToDo under `enforce` + small profile; prove output
  stays within the required section set/budget; link evidence and close BI-PF-1333.

## 6. Acceptance criteria (epic level)

- Generation consumes the resolved artifact contract (required always; optional per profile); no hardcoded
  template duplication remains.
- A trivial (small-profile) project yields the required-only section set within budget; larger profiles add
  optional sections/counts — all from the one profile lever (no arbitrary per-agent caps).
- No `.opencode` references in agent prompts.
- BI-PF-1333 verified on MyToDo and closed.

## 7. Out of scope / related

- **Out of scope:** EDP data-plane; per-agent model selection.
- **Related follow-ups to raise:** the **backlog context-authoring API gap** (no endpoint to edit an item's
  `brief/objective/…`; only `groom`) and the **state-sync/backlog-area** hygiene items.
