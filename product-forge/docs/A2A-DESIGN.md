# A2A (Agent2Agent) Interop — Design (BI-0197)

## Goal
Adopt the A2A agent<->agent standard **framework-agnostically** and **contract-based**: expose our agents
(discovery via an Agent Card + a JSON-RPC task endpoint) and consume remote A2A agents (delegate → results) —
with **every cross-agent exchange structured, schema-validated, and tracked at the Product Forge/pipeline
level** (ledger + event stream). No ad-hoc side channels; the pipeline always knows.

## Binding constraints (user)
1. **No opencode dependency.** Agent identity comes from Product Forge's own agnostic specs
   (`core/agent_spec.load_specs` → `agents/*.agent.json`, `AgentSpec`). A2A cards are built from `AgentSpec`,
   NOT from `.opencode/agent/*.md`. → **`BI-0201` (decouple cards/loaders from `.opencode`) is a prerequisite.**
2. **Contract-based + pipeline-tracked.** Every A2A message/delegation is a typed, validated contract and is
   recorded in the pipeline's own ledger/stream; remote agents cannot exchange anything invisibly.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Agent identity (agnostic) | `core/agent_spec.py` `AgentSpec` from `agents/*.agent.json` | A2A Agent Card JSON | reuse |
| Legacy cards | `core/agent_card_loader.py` defaults `.opencode/agent` | neutral source only | **BI-0201** |
| Delegation (in-pipeline) | `core/delegation.py` `DelegationRouter.resolve` + `DelegationRecord` → `products/<p>/delegations.json` | same ledger for remote A2A | reuse + extend |
| Events (tracking) | `core/events.py emit(project_dir,...)` + `core/event_bus.py` | A2A lifecycle events | reuse |
| MCP tools | `core/mcp.py` (BI-0196, done) | complementary | parallel |

**Blast radius:** new `core/a2a.py`, contract schema in `config/contracts/` (or `core/a2a_contract.py`), a
remote-peer store, API endpoints, optional wiring into the delegation router. No new event stream.

## Contract model (the crux)
A2A messages are **not free-form**. Define one canonical envelope, validated on BOTH ends:
```
A2AMessage = {
  "contract": "a2a/v1",
  "id": "<uuid>",                    # message id (idempotency key)
  "correlation_id": "<run_id>",      # ties to the pipeline run
  "from": {"agent": "<spec.id>", "system": "<product-forge|remote>"},
  "to":   {"agent": "<spec.id>", "system": "..."},
  "task": {"skill": "<skill-id>", "input_refs": [...], "params": {...}},
  "budget": {"max_tokens": N, "max_cost": X},
  "expected_outputs": ["<artifact-id/contract>"],
  "signature": "<optional>"
}
TaskResult = { "id", "correlation_id", "status": "submitted|working|completed|failed",
               "outputs": [{artifact/contract refs}], "usage": {...}, "provenance": {...} }
```
- **Validation** (`validate_message`/`validate_result`) rejects unknown contract/version, missing
  correlation, non-whitelisted skills, or outputs not in `expected_outputs` → JSON-RPC error (fail-closed).
- **Contract registry:** skills + allowed inputs/outputs derive from `AgentSpec.outputs/skills/
  allowed_inputs/forbidden_inputs` → 1 truth (the spec), so contracts can't drift.

## Pipeline tracking (no invisibility)
Every A2A interaction is recorded through the SAME owners the pipeline uses — never a private log:
- **Ledger:** remote delegations append a `DelegationRecord` (extended with `remote`, `correlation_id`,
  `contract`, `task_id`) into `products/<p>/delegations.json` — the pipeline's single delegation ledger.
- **Events:** emit `a2a.message.sent` / `a2a.message.received` / `a2a.task.completed` / `a2a.task.failed`
  via `core/events.emit(project_dir, ...)` (+ `event_bus`), so the live feed/analytics/AG-UI see them.
- **Budget:** remote calls draw from the same `DelegationBudget`; over-budget ⇒ refused (fail-closed).
- **Inbound:** a remote call to our agent enters through the pipeline (a task queued to the executor) and its
  result is emitted as an event + tagged with `correlation_id`; the pipeline is the only writer.

## Design decisions (modular)
- **New `core/a2a.py`** — protocol + contract mapping only:
  - `agent_card(specs)`: A2A Agent Card JSON **from `AgentSpec`** (`name, description, version,
    capabilities, skills[]` where skills come from `spec.skills`/`spec.outputs`). One card per agent; a
    well-known card advertises the orchestrator + the skill set.
  - Server `handle(request, ...)`: JSON-RPC `message/send` (validate → enqueue to pipeline → Task),
    `tasks/get` (Task state **derived from the event stream**, not a parallel store).
  - Client `send(remote, message)` / `delegate(remote, message)`: validate outbound contract → POST JSON-RPC
    → validate result → append `DelegationRecord` + emit events. Fail-closed on transport/JSON/contract errors.
  - `list_remotes()`: configured peers.
- **Reuse, never fork:** specs from `agent_spec`, routing from `delegation.py`, tracking from `events.py`.
  A2A is an adapter over these, not a new subsystem.
- **Framework-agnostic:** zero `.opencode` reads; depends on `agents/*.agent.json` only (BI-0201 clears
  residual coupling). A different host framework can supply its own specs.
- **Security:** consume is opt-in + **whitelisted remotes only**; inbound is validated against contracts and
  budgeted; remote content is data, never instructions (fail-closed).
- **API-first:** `GET /.well-known/agent.json` (card), `POST /api/v1/a2a/rpc` (server),
  `GET /api/v1/a2a/{card,remotes,delegations}` (introspection of tracked activity).

## Plan (branch `feature/bi-0197-a2a`)
1. **Prereq BI-0201**: confirm runtime reads `agents/*` (no `.opencode` runtime refs); if residual, fix first.
2. `docs/A2A-DESIGN.md` (this file).
3. `core/a2a.py` — contract validate, `agent_card`, `handle`, `send`/`delegate`, `list_remotes`.
4. `config/a2a-remotes.json` (peers; empty) + `config/store-registry.json`; contract registry from specs.
5. `dashboard/api/app.py` — `/.well-known/agent.json`, `/api/v1/a2a/{rpc,card,remotes,delegations}`.
6. Env flags `A2A_ENABLE_EXPOSE`/`A2A_ENABLE_CONSUME`(warn default)/`A2A_MAX_REMOTE_TOKENS` in `env-flags.json`.
7. Tests `test_a2a.py` — card built from `AgentSpec` (no opencode); server `message/send`+`tasks/get`;
   contract rejects (bad version/unknown skill/output-mismatch) fail-closed; client send against loopback
   fake; `delegate` writes a `DelegationRecord` + emits events (pipeline-tracked); budget refusal.
8. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
9. Merge; close `BI-0197` (and `BI-0201` if fixed here) through the loop.

## Acceptance
- Round-trip: our agent invoked via `/api/v1/a2a/rpc` (`message/send` → Task); remote agent invoked via
  client `send`/`delegate` against a fake.
- **Every** exchange is contract-validated and appears in `delegations.json` + the event stream
  (pipeline-tracked; not ad-hoc); `tasks/get` state derives from the stream.
- No runtime `.opencode` dependency; cards come from `agents/*.agent.json`.
- Invalid contract / unwhitelisted remote / over-budget ⇒ fail-closed JSON-RPC error. `precheck` PASS.

## Out of scope (tracked separately)
MCP (0196, done), AG-UI (0198, done), remote A2A auth/OAuth, streaming transports.
