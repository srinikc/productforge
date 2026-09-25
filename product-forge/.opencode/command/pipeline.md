---
description: "Multi-agent pipeline: /pipeline (usage), list, new <idea>, continue, fix <desc>, run <agent>, status, health, checkpoints"
agent: orchestrator
model: opencode-go/mimo-v2.5
---

**NOTE:** This command is a **thin adapter** to the generic Python pipeline
(`PipelineExecutor`). It does NOT orchestrate agents itself — it calls the
framework-agnostic runner. Deterministic commands call `scripts/pipeline.py`;
agent runs call `scripts/run_pipeline.py`.

$ARGUMENTS

## STEP 1: empty?
If `$ARGUMENTS` is empty/whitespace → run `python scripts/pipeline.py usage` and STOP.

## STEP 2: deterministic subcommands (no LLM)
Run the matching `scripts/pipeline.py` command and STOP:
`list`, `agents`, `runs`, `test`, `health`, `checkpoints`, `dlq`, `status`.

## STEP 3: agent execution (delegates to the generic orchestrator)
For `new`, `continue`, `fix`, `changes`, `run`, `resume`, `retry`, `abort`, `run-agent`:

Tier: default to the tier in the user's args, else `project.json:model_tier`, else
ASK (or use `free-trial-fast` for a fast free run). Pass it with `--tier <tier>`.

- **new <idea>** →
  `python scripts/run_pipeline.py new <project> --idea "<idea>" --tier <tier> [--interactive]`
  (if no idea provided, ASK the user first; do not invent one. Add `--interactive` to
  relay the pipeline's own prompts through chat — see the Interactivity note).
- **continue | resume** →
  `python scripts/run_pipeline.py continue <project>` (journal/checkpoint resumes state).
- **fix "<desc>"** →
  store the fix brief and run:
  `python scripts/run_pipeline.py --project <project> --idea "FIX: <desc>" --tier <tier>`
- **run <agent>** → run the pipeline (selective agent runs are handled by the executor/delegation).
- **tier passthrough**: `/pipeline new <idea> tier=free-trial-fast` (or `--tier free-trial-fast`).
- **control**: `/pipeline pause|resume|stop <project>` →
  `python scripts/run_pipeline.py --project <project> --control pause|resume|stop`.

After starting, **stream the project's `pipeline-run.log`** and report progress
between stages; the executor writes `PROJECT-STATUS.md`, `agent-audit.md`, and
telemetry/alerts itself.

## Interactivity note
Two kinds of "interactive":
1. **Agent-mediated (works here)** — YOU (the orchestrator agent) are the interface:
   ask the user in chat for project / idea / tier, then invoke `run_pipeline.py` with
   explicit flags. Stream `products/<project>/pipeline-run.log` and narrate stages/agents
   as they complete. This is how `/pipeline` is interactive.
2. **Runner stdin prompts** — the Python script's own `input()` prompts need a real TTY.
   Pass `--idea`/`--tier` (approvals follow the project's `auto_approve`), OR launch with
   `--interactive` to relay **every** prompt through `products/<project>/interactive/prompts.json`
   (BI-0026). Then drive it from chat:
   `python -m core.interactive --project <p> --list` (show pending) and
   `python -m core.interactive --project <p> --answer <id> "<value>"` (answer), plus
   `approve.py` for gates. `--interactive` implies `--step`.
   For the raw script-level flow the user runs `python scripts/run_pipeline.py` in their terminal.

## Enforcement
- NEVER perform stage work yourself and NEVER use Task()-based orchestration.
- The Python pipeline is the single brain; this command only invokes it.
- Report progress from the executor's outputs (status/audit/telemetry), not from
  your own reasoning.
