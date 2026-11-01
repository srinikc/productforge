# Agent Runtime Adapters

**Scope: PF-SB / Plane A** — the coding session that changes Product Forge itself. PF-GP / Plane B
uses Product Forge's pipeline stages and `agents/*.agent.json` specs; it is not governed by this
adapter contract.

Product Forge is framework-neutral. A runtime adapter is how a specific coding environment invokes
models and tools; it is not the source of Product Forge behavior.

## Canonical sources

- `agents/*.agent.json` — neutral agent specs (canonical)
- `docs/AGENT-ROLE-CONTRACTS.md` — role behavior
- `docs/REVIEW-GATES-LIFECYCLE.md` — Gate 0/1.5/2.5/1/2
- `docs/ENGINEERING_OPERATING_STANDARD.md` — engineering quality
- `docs/DESIGN-QUALITY-RCCA.md` — runtime-proof design

The neutral resolver is `core/agent_spec.py`; `core/agent_card_loader.py` defaults to the neutral
`agents/` directory, not `.opencode`.

## Adapter responsibilities

An adapter may define:

- model/provider and model ID;
- tool availability and permissions;
- runtime prompt formatting;
- how to launch or resume a session;
- how to capture tool output and session metadata.

An adapter must not define:

- backlog items or IDs;
- acceptance criteria;
- gate decisions or approvals;
- review evidence semantics;
- completion status;
- a second design or review process.

## OpenCode adapter (optional)

The current OpenCode adapter lives in `.opencode/agent/*.md`. It is optional and loaded only when the
runtime selects it. It contains model/tool/permission metadata and thin pointers to the neutral role
contracts.

The legacy fallback is explicit:

```text
ALLOW_OPENCODE_LEGACY=1
```

Without that flag, Product Forge resolves neutral `agents/` specs first. The repository is not
dependent on `.opencode` for backlog, design, gates, review, or evidence.

The current adapter uses `opencode-go/mimo-v2.6-flash` by default; this is configuration, not framework
coupling. Replacing the model or provider does not change any role or gate.

## Codex adapter

A Codex adapter must:

- load the same backlog item, design pack, and role contract;
- enforce the same Gate 0/1.5/2.5/1/2 evidence;
- return review findings to the worker/orchestrator for canonical evidence storage;
- keep model/tool settings in adapter config, not in role contracts.

## Antigravity adapter

An Antigravity adapter must follow the same contract as Codex. The runtime's prompt format, tool names,
and planning UI may differ; the work item, gates, evidence, and completion rules must not.

## Adding a runtime

1. Implement an adapter that can read the neutral agent specs and role contracts.
2. Map the adapter's tools to the role capabilities (read-only review vs write implementation).
3. Wire model/provider configuration in the adapter/config, not in policy docs.
4. Prove it can create an item, run Gate 0, submit a design for Gate 1.5, implement after Gate 1,
   submit the full candidate for Gate 2.5, and record evidence.
5. Add a conformance test showing the adapter cannot bypass gates or write evidence it did not produce.
6. Keep `.opencode` disabled by default if it is not the selected adapter.

## Evidence destination

Regardless of runtime:

| Artifact | Path |
|---|---|
| Design | `engineering/design/<ITEM-ID>.md` |
| Gate 1.5 review | `engineering/reviews/<ITEM-ID>-<design-sha>.json` |
| Gate 2.5 review | `engineering/reviews/<ITEM-ID>-<diff-sha>.json` |
| Execution trail | `engineering/trails/<ITEM-ID>.json` |
| Backlog item | `data/backlog/items/<ITEM-ID>.json` |
