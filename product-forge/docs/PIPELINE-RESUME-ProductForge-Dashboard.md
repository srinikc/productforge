# Resume Notes — ProductForge-Dashboard pipeline run

> Written for a NEW session. Repo root: `C:\Users\ADMIN\Documents\Srinikc\AI Products\Exploring`
> New session starts with NO memory of this one. Read this top-to-bottom.

## 1. What we are doing
Running the Product Forge pipeline **interactively** to design/build **ProductForge-Dashboard**
(`products/ProductForge-Dashboard/`) — the one-stop dashboard that is the "face" of the
multi-agent / multi-project pipeline. Goal: full parity with the terminal flow — the pipeline
must ask at **every point it is designed to ask**; agents act on their own **only** in `auto` mode.

## 2. Current state (as of this note)
- Stage **0 Ideation**: COMPLETED (`artifacts/0/ideation-output.md`, 10 KB)
- Stage **0a Discovery**: COMPLETED (took ~18 min, free tier)
- Stage **1 Design**: was left `running` when the process was killed → **blocks resume** (see §3)
- Run config: tier `free-trial-fast`, target `docker`, `auto_approve=False`, `approval_mode=interactive`
- integration_choices.json recorded (business_skills/service_catalog/spec_llm ON)
- `pipeline-state.json` currently lies: `pipeline_complete=true` (wrong) — must be repaired.

## 3. The bugs found (state/control) — ISSUES TO FIX
1. **Killed process leaves a stage `running`** → `dag_executor.get_ready_stages()` only returns
   `pending|stale`, so the stuck stage is unrunnable and **blocks all downstream stages** →
   *"No runnable stages ... stopping"*. Resume does nothing.
2. **A "blocked" exit is recorded as COMPLETION.** The `No runnable stages` branch just `break`s,
   so the finalizer sees `phase != FAILED` and sets `COMPLETION` + `completed_at` →
   `pipeline_complete=true` even though nothing completed.
3. **`stop` was ignored** while the process was mid-agent or waiting on a bridge prompt.
   (Partly fixed already — see §5.)
4. **`pipeline-run.log` was blank** (block-buffered on a detached process).
   (Fixed already — see §5.)

## 4. FIXES TO APPLY (code) — `core/pipeline_executor.py`
### 4.1 Reset stale `running` stages on resume
In `_restore_from_checkpoint`, immediately before `self.dag_executor.restore_states(stages)`, insert:

    for _sid, _info in list(stages.items()):
        if isinstance(_info, dict) and _info.get("status") == "running":
            _info["status"] = "pending"
            _info["started_at"] = ""

### 4.2 A blocked exit is not completion
In the `if self._idle_loops > 2:` block (the `No runnable stages` message), insert BEFORE the `break`:

    self.execution.phase = PipelinePhase.FAILED
    self.execution.error = f"Blocked (dependencies unmet): {blocked}"

### 4.3 (verify) completion flag derives from phase, not completed_at
`_save_checkpoint` must compute `"pipeline_complete": self.execution.phase == PipelinePhase.COMPLETION`
(already changed in this session — confirm it is present).

Then run: `python -m compileall -q core scripts dashboard`

## 5. Already fixed earlier this session (do not redo)
- `stop` honoured mid-agent + during bridge waits: `core/orchestrator/stage_runner.py` (per-agent
  control check), `core/interactive.py` (control poll in the wait loop).
- live logs: `scripts/run_pipeline.py` `_setup_run_log(..., buffering=1)`.
- `pipeline_complete` from phase: `core/pipeline_executor.py:_save_checkpoint`.
- Stop/failed no longer stamps `completed_at`: finalizer guarded by `if phase != FAILED`.
- Resume iteration budget: on incomplete checkpoint, `iteration_count` reset to 0.
- New wiring (all verified, `invocation_audit` unwired=0): `discovery_engine` (0a ->
  `discovery-questions.json`), `product_design_spec` (1a), `design_tokens` (1c),
  `dashboard_archetypes` (1/2) — via `pipeline_executor._run_design_augmentations`.
- `invocation_audit` (reachability) added & wired into `wired_audit`; removed 3 dead modules
  (`forge_supervisor`, `human_controls`, `pipeline_engine`); agent-card validator fixed (53/53 valid).

## 6. IMMEDIATE NEXT STEPS
### 6.1 Repair the stuck state (run this first)
    python -c "import json;p='products/ProductForge-Dashboard/pipeline-state.json';d=json.load(open(p,encoding='utf-8'));st=d.get('stages',{});[st[s].update({'status':'pending','started_at':''}) for s in st if st[s].get('status')=='running'];d['pipeline_complete']=False;d['completed_at']='';d['current_stage']='1';json.dump(d,open(p,'w',encoding='utf-8'),indent=2,ensure_ascii=False);print('repaired')"

### 6.2 Clean transient stop/lock, then resume
    Remove-Item "products\ProductForge-Dashboard\control.json" -Force -EA SilentlyContinue
    Remove-Item "products\.locks\ProductForge-Dashboard.lock" -Force -EA SilentlyContinue
    $env:PYTHONUNBUFFERED="1"; $env:PIPELINE_STEP="0"; $env:PIPELINE_PROMPT_TIMEOUT="3600"
    python scripts/run_pipeline.py continue ProductForge-Dashboard --interactive --tier free-trial-fast

### 6.3 Drive it as the interactive interface
- Watch: `python -m core.progress --project ProductForge-Dashboard`
- Bridge prompts: `python -m core.interactive --project ProductForge-Dashboard --list`
  then `... --answer <id> "<value>"`  (or `--answer-file <id> <path>` for long text)
- Approval gates (stage 1 scope, 2 architecture, 5 security, 10/11 deploy) + per-agent approvals
  (mode=interactive): `python approve.py --project ProductForge-Dashboard --stage <s> --agent <a> --approve`
  (list: `python approve.py --project ProductForge-Dashboard --list`)

## 7. Key intent to preserve (from the user)
- The dashboard is the single UI for ALL pipeline operations: create project (idea + model tier
  select/custom/new from the model+provider catalog), monitor/track/control agents & orchestrator,
  portfolio (multi-project, run in parallel), all interactive inputs as proper dialogs,
  top-notch UI/UX components, voice-enabled global AI chat companion (TTS/STT, wake word,
  active only when enabled and dashboard focused), mobile app companion, tests via our test
  framework, UI pages for EVERY implemented pipeline feature/module, deployable (Vercel/public)
  with backend+dashboard co-located or split, API-first, and auto-mode orchestration with live logs.
- Refer to the `mymoney` project for voice: `C:\Users\ADMIN\Documents\Srinikc\AI Products\mymoney`
- Requirement: interactive must behave like the terminal (ask at every designed point);
  `auto` mode is the only mode where agents act without asking.

## 8. Backlog items already logged (product-forge)
BI-0026 prompt bridge · BI-0027 progress banner · BI-0028 discovery_engine wiring ·
BI-0029 invocation audit · BI-0030 zero-unwired · BI-0031 agent-card validator ·
BI-0032 remove deprecated modules · BI-0033 clear HIL prompt UX (dialogs in dashboard).
