# Entry Points — which script to use

Product Forge has two scripts; they serve different purposes.

## `scripts/run_pipeline.py` — the RUNNER (LLM-driven)
Launches and drives the pipeline (stages, agents, model routing, gates, checkpoints).

```powershell
python scripts/run_pipeline.py --project <name> --tier <tier>
python scripts/run_pipeline.py --project <name> --idea "..." --tier free-trial-fast
python scripts/run_pipeline.py --project <name> --from-stage 4a
python scripts/run_pipeline.py --project <name> --only-stage 0,0a,1,2,3,3a --only
python scripts/run_pipeline.py --project <name> --agent architect --only
python scripts/run_pipeline.py --project <name> --step            # pause after each agent (TTY)
python scripts/run_pipeline.py --project <name> --control stop    # stop|pause|resume|exit
python scripts/run_pipeline.py --project <name> --tier-list
python scripts/run_pipeline.py --project <name> --tier-info free-trial-fast
```

## `scripts/pipeline.py` — UTILITY COMMANDS (deterministic, no LLM)
Inspect state and run small operations; used by tooling/dashboard/helpers.

```powershell
python scripts/pipeline.py list
python scripts/pipeline.py status [project]
python scripts/pipeline.py agents [project]
python scripts/pipeline.py runs
python scripts/pipeline.py checkpoints | dlq | usage | budget
python scripts/pipeline.py compliance <project> [agent] [stage]
python scripts/pipeline.py lock | unlock | circuit-reset
python scripts/pipeline.py architecture | project-architecture
```

## Roles at a glance
| Task | Use |
|---|---|
| Launch / resume / rerun / control the pipeline | `run_pipeline.py` |
| Inspect projects/agents/state, list, health, locks, DLQ, budget, compliance | `pipeline.py` |
| Manage tiers (list/info) | `run_pipeline.py --tier-list/--tier-info` |

## Common workflow
```powershell
# 1) (optional) pick a tier
python scripts/run_pipeline.py --project myapp --tier-info free-trial-fast

# 2) run (idea can be passed now, or provided at Stage 0)
python scripts/run_pipeline.py --project myapp --tier free-trial-fast

# 3) watch / control
python scripts/pipeline.py status myapp
python scripts/run_pipeline.py --project myapp --control pause
python scripts/run_pipeline.py --project myapp --control resume
```

## Notes
- No interactive REPL: launch with `run_pipeline.py`, then drive via `--control` / `--step`.
- Interactive approval prompts require a real TTY (run in your own terminal); non-TTY runs use the project's `auto_approve`.
