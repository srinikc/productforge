# Re-run Impact Analysis — Dependency & Invalidation Model

> Scope: when an agent/stage is re-executed (or the pipeline continues, or a project is
> restarted), which downstream agents **must** re-run — and how to guarantee the product
> is rebuilt correctly while not wasting tokens.
> Principle: **correctness first.** Never skip a rerun unless it is *provably* a no-op.

## 1. Why this matters
If a re-run of an upstream agent changes an artifact that a downstream agent consumes,
and the downstream agent is **not** re-run, the product is built on **stale inputs**
(wrong requirements, outdated design, mismatched code/tests). That is the failure mode
the user warned about. Over-invalidation (rerunning too much) only costs time/tokens;
under-invalidation produces a **wrong product**. So the default must be conservative.

## 2. Dependency inputs we actually have (verified)
| Source | What it gives | Coverage / quality |
|---|---|---|
| `pipeline-definition.json` `depends_on` / `runs_after` | stage→stage order (DAG) | ✅ complete |
| `parallel_groups` | sibling stages that can run together | ✅ |
| `agent_dependencies` (per stage) | agent→agent order **within** a stage | ⚠️ only impl stages (`4-0/4a…`, `10`) |
| `allowed_inputs` (AgentSpec / contract) | semantic inputs per agent (e.g. `design_spec`, `component_plan`, `test_results`) | ⚠️ only 17/53 agents |
| artifacts (`artifacts/<stage>/<agent>-output.md`) | real files produced by agents | ✅ but **provenance is implicit** |
| `sub_agents` / `can_invoke` | e.g. `implement` → `implement-api/db/logic/ui` | ✅ |
| `tech-stack.json`, feature list (`product-plan.md` F-n) | cross-cutting inputs | ✅ but not part of the DAG |

**Critical gap found:** `allowed_inputs` are **semantic** (`design_spec`), but artifacts
are keyed as `<stage>_<agent>` (`1_design`). There is **no mapping** between them, so:
- context filtering (`_build_agent_prompt`) can drop artifacts it should keep, and
- invalidation cannot be computed at artifact precision.

This same missing map is both a **context-assembly bug** and the reason invalidation is
currently coarse.

## 3. Correctness rule (the model)
An agent **A must re-run** iff any **input A consumes changed**, where inputs are:
1. **Artifacts** produced by other agents (semantic ids mapped to files),
2. **Config** it reads (`project.json`, `tech-stack.json`, feature list),
3. **Code/files** on disk it depends on (for reviewers/validators).

Re-run propagates **transitively** (A→B→C). This is a standard incremental-build / build-
dependency problem (like Make/Bazel): a target is rebuilt if any prerequisite changed.

**The only safe "no re-run" exception** is when the re-run produced **byte-identical
output** (content hash unchanged) → nothing downstream can be affected.

## 4. Options evaluated
| Option | Precision | Risk | Verdict |
|---|---|---|---|
| A. Stage-DAG closure (current) | coarse | over-invalidates (safe) | keep as **safety net** |
| B. Agent-level proximity | medium | needs `agent_dependencies` filled for all stages | **fill it** |
| C. Artifact-provenance closure | **precise** | needs the semantic→artifact map | **adopt** |
| D. Content-hash skip | exact no-op detection | none | **adopt** |
| E. Hand-marked "advisory agents" | ad-hoc | **under-invalidation** | **reject** |

**Recommendation: C + D, with A + B as fallback when the map/graph is incomplete.**
Reject hand-waved "this agent doesn't need re-run" lists — they risk the exact stale-product
problem.

## 5. Recommended design
### 5.1 Canonical artifact registry
Map each **semantic input/output id** → producing agent(s)/stage and file(s):
```
product_spec    -> ideation, discovery        (docs/product-plan.md)
design_spec     -> design, product-design-spec (docs/design.md)
design_tokens   -> ux-ia
component_plan  -> architect                  (docs/architecture.md)
api_contract    -> architect / implement-api
source_diff     -> implement*, implement-*    (src/**)
test_results    -> validate                   (tests/**)
deploy_config   -> devops                     (Dockerfile, CI)
```
- Seed from the 17 agents that declare `allowed_inputs`; extend to the rest from
  `agent_dependencies` + spec `output_format`.
- Add `outputs` to `AgentSpec` (semantic ids) so provenance is explicit.

### 5.2 Invalidation algorithm (on selective re-run)
```
changed = rerun(seed_agents_or_stages)         # execute the targets
for out in changed.outputs:                     # semantic ids
    if hash(out.file) == hash(previous): skip   # D: provable no-op
    else: propagate to agents whose inputs include out
propagate transitively
stages = union(affected_agents, dag.dependents(seeds), agent_dependencies closure)
mark affected stages STALE (blocked until deps met)
```
Fallback: if an agent's inputs aren't mapped, treat **all downstream DAG dependents** as
affected (option A) — never assume "no impact".

### 5.3 Cross-cutting changes
- `tech-stack.json` changed → invalidate `architect` + all downstream.
- Feature list (F-n) changed → invalidate `design` (requirements) + downstream.
- Human code edits → invalidate `code-review`, `validate`, `security` for those files.

### 5.4 Continue/pause ≠ re-run
Resume continues the same run; **no invalidation**. Only an explicit re-run/project edit
triggers the algorithm.

## 6. Risk table
| | Under-invalidate | Over-invalidate |
|---|---|---|
| Cause | wrong/advisory exceptions, missing map | conservative closure |
| Effect | **product built on stale inputs (BROKEN)** | wasted tokens/time |
| Acceptable? | ❌ never | ✅ yes |
| Mitigation | default to conservative fallback (A) | hash skip (D) + precise map (C) |

## 7. Implementation plan
1. **Fix the map**: add `inputs`/`outputs` (semantic ids) to every `AgentSpec`; map ids →
   artifact files. (Also fixes context assembly in `_build_agent_prompt`.)
2. Fill `agent_dependencies` for all stages (from spec `outputs`→`inputs`).
3. **Artifact hashing**: on re-run, hash outputs before/after; skip propagation if identical.
4. **Invalidation service** (`core/orchestrator/invalidation.py`): compute affected stages
   = (artifact-provenance consumers) ∪ (stage-DAG dependents) ∪ (agent_dependencies closure),
   then `dag.mark_stale` + persist.
5. Expose in `get_status` (already shows `stale`/`blocked`) and API.

## 8. Recommendation
Adopt **artifact-provenance + content-hash** invalidation with **stage-DAG as the safety
net**; fill the semantic→artifact map and `agent_dependencies`; **do not** add hand-waved
"no re-run" exceptions. Rejecting those exceptions is the only way to guarantee the product
is rebuilt as needed.
