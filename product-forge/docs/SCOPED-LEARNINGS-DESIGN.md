# Scoped Learnings + Memory Read-Back — Design (BI-PF-0294)

## Goal
Make approved learnings apply **on need** (per project/area/agent), not globally to every project — and
make the already-written **agent memory readable** into prompts (bounded, opt-in). Static instructions
untouched; no change to the evidence-gated/approval contract (BI-PF-0293).

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| Learnings store | one global `data/learnings.json` (`_FILE`) | global + **per-project** `products/<p>/learnings.json` | `core/learnings.py` |
| `learnings.render` | filters by `area` only; no project | add `project=`/`agent=`; union global+project | `core/learnings.py` |
| Injection site | `agent_runner.py:1330` `_ln.render()` (global, every agent) | `render(project=, area=)` need-based | `agent_runner` |
| Adding | `add(rule, area, source_ref)` → global file | `add(..., project=)` → project store when scoped | `core/learnings.py` |
| learning_synth apply | `learnings.add(text, area=…)` (global) | pass `project=` from candidate scope | `learning_synth` |
| Memory | written (`agent_execution`) **never read** | bounded read-back block (opt-in) | `core/agent_memory` + `agent_runner` |

**Blast radius:** `learnings.py` (add/render/load/save scoping), `agent_runner` injection, `learning_synth.apply`,
store-registry (project store), env flags, tests. Single writer preserved; no new module.

## Design decisions (modular)
- **Scoped store resolution in `learnings.py`:** `_file(project)` → project path when `project` given else
  global. `add(rule, area, source_ref, project="")`, `all_learnings(project="")` (union global + project,
  project wins on dedup), `render(area="", project="", agent="", …)`.
- **Need-based injection:** `agent_runner` calls `render(area=<module-or-blank>, project=self.project)` so
  a project-scope learning only appears in that project's prompts; **global remains a fallback**.
- **`learning_synth.apply`:** when a candidate's `scope` is `project:<p>`, call
  `learnings.add(..., project=<p>)`; `area:<m>` → `area=`; `global` → global (explicit promotion only).
- **Memory read-back (opt-in, bounded):** new `agent_runner` injection calling
  `agent_memory.create_agent_memory(products_dir, project).retrieve(MemoryQuery(query=task, source_filter=agent_id,
  max_results=N))` → a bounded `PRIOR RUN NOTES` block (≤`PIPELINE_MEMORY_CHARS`). Guarded; skip when empty.
  Mirrors the `learnings.render()` pattern; **off unless `PIPELINE_MEMORY_READBACK=1`**.
- **Backward-compatible:** default `project=""` everywhere → existing global behavior unchanged (tests pass).
- **No new truth:** learnings content unchanged; we only *scope* storage + *select* on need.

## Plan (branch `feature/bi-pf-0294-scoped-learnings`)
1. `docs/SCOPED-LEARNINGS-DESIGN.md` (this file).
2. `core/learnings.py` — project-scoped add/load/render (union global+project; area/agent filters).
3. `core/learning_synth.py` — pass `project=` on apply for project scope.
4. `core/orchestrator/agent_runner.py` — need-based `render(project=…)` + opt-in bounded memory read-back.
5. `config/store-registry.json` — `learnings.json` project entry (owner `core/learnings.py`).
   `config/env-flags.json` — `PIPELINE_MEMORY_READBACK`.
6. Tests `test_scoped_learnings.py` — global still works; project learning appears only for that project;
   area filter; `learning_synth.approve` writes to the project store; memory read-back bounded + opt-in.
7. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
8. Merge; close `BI-PF-0294` through the loop.

## Acceptance
- A project-scoped approved learning is injected **only** in that project; global remains a fallback.
- Need-based: an `area:` learning reaches matching agents; unrelated agents unaffected.
- Memory read-back (opt-in) injects a bounded PRIOR RUN NOTES block; empty ⇒ no-op.
- Default/global behavior unchanged; `precheck` PASS; one writer per store.

## Out of scope (tracked separately)
Knowledge/skill registration (`BI-PF-0295`), measured routing/effectiveness loop.
