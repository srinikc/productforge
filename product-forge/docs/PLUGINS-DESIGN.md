# Plugin / Registry Framework (Ports & Adapters) — Design (BI-0200)

## Goal
A generic plugin framework so a new **provider / tool / agent / stage / validator** registers via a
config entry + a small adapter, **without core edits**. The core depends on **ports**; plugins are
adapters resolved by dotted name. Generalizes capability packs (BI-0189) + provider kinds (BI-0193).

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Generic plugin abstraction | **none** | new registry + loader | new `core/plugins.py` |
| Dotted `module:callable` resolve | `pipeline_capabilities._mk/_fn` | **reuse** as the resolver | `pipeline_capabilities` |
| Dispatch pattern | `capability_bridge.REGISTRY/STAGE_HOOKS` | generalize | reuse pattern |
| Provider port | `provider_kinds` (headers/adapt_body/extract_content/supports) | adapter target | reuse |
| Tool port | `tool_registry.ToolRegistry.register(ToolSpec)` | adapter target | reuse |
| Stage/validator | `pipeline_composition.effective_definition` (pack-shaped) | adapter target | reuse (**no 4th enable path**) |
| Agent | `agent_spec.AgentSpec/load_specs/save_spec` | adapter target | reuse |
| Model/generator | `generator_adapters` / `model_catalog` | config entries | reuse |
| Knowledge/skill | `knowledge_registry`, `skills_registry` | config entries | reuse |
| Config catalogs shape | `{ "<id>": {kind,…} }` (capability-packs/generators) | mirror | — |
| Wiring/audit | new core module must be invoked; new store registered; **adapters outside `core/`** | comply | `wired_audit` |

**Blast radius:** new `core/plugins.py` + `config/plugins-registry.json` + `adapters/plugins/` (adapters),
API endpoints, one runtime call site, store-registry entry, tests. No fork of existing registries.

## Design decisions (modular)
- **New `core/plugins.py`** — single writer of `config/plugins-registry.json`. API:
  `catalog()`, `list_plugins(kind="", enabled_only=True)`, `view(pid)`, `enabled(kind="")`,
  `resolve(pid)` (load adapter by dotted name), `run(pid, context, *a, **k)`, `validate()` (fail-closed),
  `describe()`. **Resolve via the existing `pipeline_capabilities._mk`/`_fn` convention** (don't reinvent).
- **Plugin kinds + ports:** `provider|tool|agent|stage|validator`. Each adapter is a callable/factory
  `build(context) -> port dict`; per-kind the returned dict matches the existing port:
  provider→`provider_kinds` shape; tool→`{spec, handler}`; stage/validator→pack-shaped
  (`{stages,agent_stages,validator_stages}`); agent→`AgentSpec` dict.
- **Adapters live OUTSIDE `core/`** at `adapters/plugins/<name>.py` (so `invocation_audit` does not flag
  them UNWIRED; they're resolved at runtime by dotted name).
- **No fork, no 4th enable path:** stage/validator plugins **feed `pipeline_composition.effective_definition`**;
  agent plugins **materialize via `agent_spec`**; tools via `ToolRegistry.register`; providers via `provider_kinds`.
- **Fail-closed:** unknown kind / unresolved adapter / missing `requires` ⇒ warning + not enabled (mirror
  `capability_packs.resolve`); `run()` never raises into the pipeline (mirror `capability_bridge`).
- **API-first:** `GET/POST /api/v1/plugins*` read via `core.plugins`; mutations under `operator_guard`;
  the API never writes the store.
- **Audit compliance:** register the store (visibility=shared); invoke `core/plugins.py` from a runtime
  entry (mirror `_run_extended_capabilities`); adapters outside `core/`; `ROOT` from `core.paths`.

## Plan (branch `feature/bi-0200-plugin-framework`)
1. `docs/PLUGINS-DESIGN.md` (this file).
2. `core/plugins.py` — catalog + resolver (reuse `_mk`/`_fn` convention) + per-kind port validation +
   `run` + fail-closed `validate`.
3. `adapters/plugins/` — a **dummy example plugin** (kind=tool) proving drop-in registration + a
   stage example feeding composition (test fixture / example, disabled by default).
4. `config/plugins-registry.json` — empty registry (mirror capability-packs shape); register in
   `config/store-registry.json`.
5. Wire: invoke `plugins.validate()`/`describe()` from the run-start path (mirror `_run_extended_capabilities`);
   optionally let enabled **stage plugins** contribute packs to `pipeline_composition`.
6. `dashboard/api/app.py` — `/api/v1/plugins`, `/api/v1/plugins/{pid}`, `/api/v1/plugins/kinds`,
   `POST /api/v1/plugins`, `POST /api/v1/plugins/{pid}/{action}`.
7. Tests `test_plugins.py` — register a dummy tool plugin + a stage plugin; unresolved/unknown kind
   fail-closed; stage plugin feeds composition; text-only unaffected; API shape.
8. Gates: compileall, wired_audit (0 unwired; store registered), workflow_matrix, pipeline tests, precheck.
9. Merge; close `BI-0200` through the loop.

## Acceptance
- A new provider/tool/agent/stage/validator registers via config + a small adapter, **no core edit**; the
  plugin appears in the registry/roster and runs; audits green.
- Unknown kind / unresolved adapter / missing requires ⇒ fail-closed (warning, not enabled).
- Stage/agent plugins reuse `pipeline_composition`/`agent_spec` (no parallel enable path).
- API-first; `precheck` PASS; scalable (registry entry, no code change per plugin).

## Out of scope (tracked separately)
MCP/A2A/AG-UI (0196–0198), OTel (0199), real remote plugin discovery/loading from packages.
