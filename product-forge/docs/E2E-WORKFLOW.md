# End-to-End Workflow (framework-neutral)

This document explains the two different delivery planes in Product Forge, the backlog-item lifecycle,
and the Cursor-style working loop. It is intentionally independent of any agent runtime.

## Two delivery planes

### Plane A — Product Forge builds itself

An AI coding session (OpenCode, Codex, Antigravity, etc.) changes the Product Forge repository.
The runtime is only an adapter; Product Forge owns the backlog, design contract, gates, evidence, and
merge rules.

### Plane B — Product Forge builds another product

Product Forge runs its own orchestrator, scheduler, workers, and neutral agent specs to produce a
generated product. That product has its own repository, backlog, design, tests, and release lifecycle.

Do not mix the two planes:

- Plane A work is a Product Forge backlog item.
- Plane B work is a generated-product backlog item inside that product's scope.
- A runtime adapter never owns either backlog or any gate.

### Which workflow am I in?

| You are changing... | Workflow | Backlog/scope | Governing docs | Evidence |
|---|---|---|---|---|
| Product Forge code/docs/config/gates | **PF-SB / Plane A** | `product_forge` | `AGENTS.md`, `REVIEW-GATES-LIFECYCLE.md`, `AGENT-ROLE-CONTRACTS.md` | `engineering/design`, `engineering/reviews`, `engineering/trails` |
| A product Product Forge generates | **PF-GP / Plane B** | generated product scope | product's own AGENTS/design/backlog; `pipeline-definition.json`; `agents/*.agent.json` | product repository evidence |
| The runtime/session itself | Runtime adapter | none | `AGENT-RUNTIME-ADAPTERS.md` | none |

**Rule:** if the work item is `BI-PF-*` in `product_forge`, it is PF-SB. If it is a generated product's
item, it is PF-GP. Do not apply PF-SB Gate 0/1.5/2.5 to a PF-GP item unless that product explicitly
adopts them.

### Agent-card mapping

| Card/agent | Workflow |
|---|---|
| `docs/AGENT-ROLE-CONTRACTS.md` roles | PF-SB |
| `.opencode/agent/implement.md`, `review.md`, `code-review.md`, `architect-reviewer.md` | PF-SB runtime adapters (optional) |
| `design`, `design_critic`, `architect` cards | PF-GP pipeline |
| `implement-api`, `implement-db`, `implement-logic`, `implement-ui` cards | PF-GP pipeline |
| `fix`, `validate`, `static_verifier`, other stage agents | PF-GP pipeline |
| `agents/*.agent.json` neutral specs | Runtime-neutral agent data; PF-GP uses these for pipeline cards |

## Plane A — Product Forge self-build lifecycle

```text
Idea / defect / change
        |
        v
[1] Intake -> Product Forge backlog item
        |
        v
[2] Gate 0: reconciliation + impact + language/API checks + AC
        |
        v
[2.5] Gate 0.5: functional spec freeze (`engineering/specs/<ID>.md`)
        |
        v
[3] Design pack + architecture/ADR + runtime call-site map + conditional spec pack
        |
        v
[4] Gate 1.5: independent read-only design review
        |
        v
[5] Gate 1: HIL design approval
        |
        v
[6] Feature branch / isolated worktree
        |
        v
[7] Implementer: failing runtime proof -> smallest implementation -> red-to-green
        |
        v
[8] Gate 2.5: independent read-only full-candidate review
        |
        v
[9] Gate 2: HIL delivery approval + independent AC verification
        |
        v
[10] Precheck/CI -> PR -> merge gate
        |
        v
[11] Closure guard -> delivery provenance -> DoD
```

### What each stage produces

| Stage | Owner | Output |
|---|---|---|
| Intake | Human / agent / system | Backlog item with scope, AC, dependencies |
| Gate 0 | Worker / design author | Reconciliation, impact table, language/API/AC |
| Gate 0.5 | Design author | Functional spec + traceability skeleton |
| Design | Design author | `engineering/design/<ID>.md`, runtime wiring, failure/proof plan |
| Gate 1.5 | Architect reviewer | Design findings and recommendation |
| Gate 1 | HIL | Design approval and decisions |
| Implementation | Implementer | Source, tests, failing/passing runtime proof |
| Gate 2.5 | Architect reviewer | Full-candidate findings and recommendation |
| Gate 2 | HIL + verifier | Delivery approval, AC-by-AC evidence |
| Precheck/CI | Tools | Executed checks and reports |
| Merge | Git/PR | Commit, merge, PR provenance |
| Closure | Backlog/gates | `completed` only with evidence and delivery provenance |

## Cursor-style working loop

Use this mental model when working in any coding-agent UI:

```text
PLAN -> REVIEW PLAN -> IMPLEMENT -> REVIEW DIFF -> VERIFY -> SHIP
```

| Loop step | Human/agent action | Product Forge artifact |
|---|---|---|
| Plan | Read item, code, call sites; draft design | Backlog item + design + reconciliation |
| Review plan | Independent design review; HIL decides | Gate 1.5 + Gate 1 |
| Implement | Write failing proof, smallest code change | Branch + tests + runtime proof |
| Review diff | Full-candidate review, not delta-only | Gate 2.5 |
| Verify | Run proof, regressions, precheck/CI | AC evidence + reports |
| Ship | HIL delivery decision, PR, merge, closure | Gate 2 + delivery provenance |

The important Cursor-like discipline is: **do not jump from “plan” to “ship.”** The plan and the
complete diff are separate review checkpoints.

## Plane B — generated-product lifecycle

```text
Product idea
  -> intake / product plan
  -> product backlog
  -> product design + architecture
  -> implementation agents
  -> validation / QA / security / tests
  -> release candidate
  -> release / delivery
```

Generated products use the same principles:

- one backlog per product scope;
- a design contract before implementation;
- runtime proof for runtime capabilities;
- independent review before release;
- evidence-backed completion.

The Product Forge runtime adapters invoke models and tools. They do not define the product's
requirements, acceptance criteria, gates, or evidence policy.

## Backlog-item work bundle

For any work item, these files are the operational bundle:

```text
data/backlog/items/<ITEM-ID>.json        # work item, AC, dependencies, decisions
engineering/design/<ITEM-ID>.md          # design pack / runtime contract
engineering/reviews/<ITEM-ID>-<sha>.json # Gate 1.5 and Gate 2.5 evidence
engineering/trails/<ITEM-ID>.json        # lifecycle/trail evidence
```

Do not create a second ad hoc work document. Start from the backlog item and design pack.

## Runtime-adapter boundary

Canonical, framework-neutral sources:

- `agents/*.agent.json` — neutral agent specs
- `docs/AGENT-ROLE-CONTRACTS.md` — role behavior
- `docs/REVIEW-GATES-LIFECYCLE.md` — gate process
- `docs/ENGINEERING_OPERATING_STANDARD.md` — engineering quality
- `docs/DESIGN-QUALITY-RCCA.md` — runtime-proof design

Runtime-specific adapters:

- OpenCode: current optional `.opencode/agent/*.md` adapter
- Codex: its own prompt/config adapter
- Antigravity: its own prompt/config adapter
- Any future runner

An adapter may provide model name, model provider, tool access, prompt formatting, and execution
hooks. It must not own backlog IDs, gates, approvals, review evidence, or completion semantics.

See `docs/AGENT-RUNTIME-ADAPTERS.md` for the adapter contract.

## Stop conditions

Stop and report when:

- the runtime entrypoint or call site cannot be identified;
- the production adapter or failure behavior is unclear;
- a required dependency is unavailable;
- evidence is missing, stale, or belongs to another candidate;
- the design and implementation disagree;
- scope is expanding beyond one independently verifiable capability;
- the worktree or backlog state changes unexpectedly.
