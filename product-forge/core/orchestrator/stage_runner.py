"""
Stage runner mixin (extracted from pipeline_executor - 1A.11).

Mixin (not composition) because these methods operate on executor state
(`self`): parallel/sequential stage execution, per-stage timing and gating.
Moving them verbatim keeps behavior identical while shrinking
pipeline_executor.py.
"""
import os
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.budget_protection import BudgetType
from core.context_manager import get_contract
from core.forge_constitution import check_rule
from core.forced_convergence import ConvergenceState, check_convergence
from core.orchestrator.types import AgentExecution, PipelinePhase
from core.iteration_planner import ITERATION_STAGES as PHASE_STAGES


class StageRunnerMixin:
    def _emit_lifecycle(self, event_type: str, *, stage: str = "", agent: str = "", **fields):
        """Emit one canonical lifecycle event (run/stage/agent). Best-effort."""
        try:
            from core import events as _ev
            _rid = ""
            try:
                _rid = str(getattr(getattr(self, "execution", None), "pipeline_id", "") or "")
            except Exception:
                _rid = ""
            _ev.emit(getattr(self, "project_dir", ""), event_type,
                     run_id=_rid, stage=stage, agent=agent, **fields)
        except Exception:
            pass
        try:
            from core import run_status as _rs
            _rs.update(getattr(self, "project_dir", ""), event_type, run_id=_rid,
                       stage=stage, agent=agent, status=str(fields.get("status", "") or ""))
        except Exception:
            pass

    def _start_heartbeat(self, agent_id: str, stage_id: str, stop_event):
        """Background ping: a long agent stays visibly 'alive' (>2min -> every 60s)."""
        def _hb():
            t0 = time.time()
            while not stop_event.wait(60):
                el = int(time.time() - t0)
                if el >= 120:
                    print(f"    [HEARTBEAT] {agent_id}@{stage_id} alive {el}s (still working)")
                    self._emit_lifecycle("agent_heartbeat", stage=stage_id, agent=agent_id,
                                         elapsed=el)
        t = threading.Thread(target=_hb, daemon=True)
        t.start()
        return t

    def _stage_is_parallel_safe(self, stage_id: str) -> bool:
        """Return True if a stage is explicitly marked safe to run concurrently."""
        if not self.pipeline_def:
            return False
        sdef = self.pipeline_def.get("stages", {}).get(stage_id, {})
        return bool(sdef.get("parallel_safe", False))

    def _execute_stages_parallel(self, stage_ids: List[str]):
        """Execute multiple independent stages in parallel."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        print(f"\n[Orchestrator] Executing {len(stage_ids)} stages in parallel: {stage_ids}")
        
        # Limit concurrent stages
        stages_to_run = stage_ids[:self.max_parallel_stages]
        
        with ThreadPoolExecutor(max_workers=len(stages_to_run)) as executor:
            futures = {
                executor.submit(self._execute_stage_sequential, stage_id): stage_id
                for stage_id in stages_to_run
            }
            
            for future in as_completed(futures):
                stage_id = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"[Orchestrator] Parallel stage {stage_id} failed: {e}")
                    self._log_decision("parallel_failure", f"stage {stage_id}", str(e))
    
    def _execute_stage_sequential(self, stage_id: str):
        """Execute a single stage sequentially."""
        stage_start = time.time()
        
        stage_name = ""
        try:
            stage_name = (self.pipeline_def.get("stages", {}).get(stage_id, {}) or {}).get("name", "")
        except Exception:
            pass
        try:
            from core.banner import stage_line, rule
            print("\n" + rule("-") + "\n" +
                  stage_line(stage_id, stage_name, f"project={self.project}") + "\n" + rule("-"))
        except Exception:
            print(f"\n--- Stage: {stage_id} (iteration {self.iteration_count}) ---")

        # Optional integrations: applied automatically (no prompt) at DESIGN ENTRY (1)
        # and RE-EVALUATED after ARCHITECT (2) - once the stack is chosen, stack-specific
        # guidance becomes relevant. Default = recommended subset; adjust later via flags.
        if stage_id in ("1", "2"):
            try:
                self._recommend_integrations()
            except Exception as e:
                print(f"[Integrations] {e}")

        # One-time: extended capabilities (git/cost/finops/release/maintenance/...).
        if not getattr(self, "_extended_caps_done", False):
            self._extended_caps_done = True
            try:
                self._run_extended_capabilities()
            except Exception as e:
                print(f"[Capabilities] {e}")

        # One-time: plugin registry (BI-0200) — validate/resolve enabled plugins (ports & adapters).
        if not getattr(self, "_plugins_done", False):
            self._plugins_done = True
            try:
                from core import plugins as _pl
                _v = _pl.validate()
                if _v.get("enabled"):
                    print(f"  [Plugins] {_v['resolved']}/{_v['enabled']} resolved; "
                          f"warnings={_v.get('warnings')}")
            except Exception as e:
                print(f"[Plugins] {e}")

        # One-time: deployment target selection (declared, or HIL prompt; default local).
        if not getattr(self, "_target_selected", False):
            self._target_selected = True
            try:
                self._select_target()
            except Exception as e:
                print(f"[Target] {e}")

        # Design-phase augmentations: discovery questions / design spec / archetype / tokens.
        try:
            self._run_design_augmentations(stage_id)
        except Exception as e:
            print(f"[Design] {e}")

        # BI-0124..0137: run the capability-bridge hooks bound to this stage
        # (research/cost/compose/git/byot/release/build/...). Best-effort, never fatal.
        try:
            from core import capability_bridge as _cb
            _hooks = _cb.run_stage_hooks(self.project_dir, stage_id)
            if _hooks:
                _ok = sum(1 for v in _hooks.values() if isinstance(v, dict) and "error" not in v)
                print(f"[CapBridge] {stage_id}: {_ok}/{len(_hooks)} capability hook(s) ok")
        except Exception as e:
            print(f"[CapBridge] {e}")

        # BI-0092: instantiate the dashboard+API blueprint for this project (idempotent).
        try:
            from core import dashboard_blueprint as _bp
            _bp.instantiate(self.project, kind="project", project_dir=self.project_dir)
        except Exception:
            pass

        # VCS: start a feature branch for implementation/fix stages (orchestrator-owned).
        if stage_id in ("4-0", "4a", "4b", "4c", "4d", "4e", "4f"):
            try:
                self._vcs_stage_branch(stage_id)
            except Exception as e:
                print(f"[VCS] {e}")
        
        # Check stop conditions before each stage
        should_stop, triggered = self.check_stop_conditions(stage_id)
        if should_stop:
            print(f"[Orchestrator] Stop conditions triggered: {[c.name for c in triggered]}")
            self.execution.phase = PipelinePhase.FAILED
            self.execution.error = f"Stop conditions: {[c.name for c in triggered]}"
            self._log_decision("stop_condition", f"stage {stage_id}", str([c.name for c in triggered]))
            return
        
        # Check max iterations
        if self.iteration_count >= self.max_iterations:
            print(f"[Orchestrator] Max iterations ({self.max_iterations}) reached")
            self.execution.phase = PipelinePhase.FAILED
            self.execution.error = f"Max iterations {self.max_iterations} reached"
            return
        
        # Check forced convergence
        convergence_state = ConvergenceState(project=self.project)
        convergence_result = check_convergence(convergence_state, stage_id)
        if convergence_result and convergence_result.action == "terminate":
            print(f"[Orchestrator] Forced convergence: terminating pipeline")
            self.execution.phase = PipelinePhase.FAILED
            self.execution.error = "Forced convergence: too many idle cycles"
            self._log_decision("convergence_terminate", f"stage {stage_id}", "too many idle cycles")
            return
        elif convergence_result and convergence_result.action == "skip":
            print(f"[Orchestrator] Forced convergence: skipping stage {stage_id}")
            self.dag_executor.mark_completed(stage_id, {"skipped": True, "reason": "forced_convergence"})
            self._log_decision("convergence_skip", f"stage {stage_id}", "forced convergence")
            return
        
        # Check Product Forge constitution rules
        from core.forge_constitution import Constitution, DEFAULT_RULES
        constitution = Constitution(version="1.0", rules=DEFAULT_RULES)
        for rule_id in ["R001", "R002", "R003", "R004", "R005"]:
            rule_check = check_rule(constitution, rule_id, {"stage": stage_id, "project": self.project})
            if not rule_check.get("passed", True):
                print(f"[Orchestrator] Constitution rule {rule_id} violated: {rule_check.get('reason', 'unknown')}")
                self._log_decision("rule_violation", f"stage {stage_id} rule {rule_id}", rule_check.get('reason', 'unknown'))
        
        # Get stage definition
        stage_def = self.pipeline_def.get("stages", {}).get(stage_id, {})
        stage_name = stage_def.get("name", stage_id)
        stage_type = stage_def.get("type", "sequential")
        agents = stage_def.get("ideal_flow", [])

        # Agent-level scope: run only the selected agents in this stage.
        only_agents = getattr(self, "only_agents", None)
        if only_agents:
            agents = [a for a in agents if a in only_agents]
            if not agents:
                print(f"  Stage {stage_id}: SKIPPED (no selected agents)")
                self.dag_executor.mark_skipped(stage_id)
                self._log_decision("agent_scope_skip", f"stage {stage_id}", "no selected agents")
                return

        # Dynamic implementation iterations: plan once, then skip any iteration
        # stage (or its VQA) beyond the computed plan.
        if stage_id in PHASE_STAGES or any(stage_id == s + "-vqa" for s in PHASE_STAGES):
            if not self.phasing.phases_planned:
                self.phasing.plan()
            if self.phasing.is_inactive_stage(stage_id):
                print(f"  Stage {stage_id}: SKIPPED (beyond planned iterations)")
                self.dag_executor.mark_completed(stage_id, {"skipped": True, "reason": "iteration_plan"})
                self._log_decision("iteration_skip", f"stage {stage_id}", "beyond planned iterations")
                return
        
        # Create stage budget derived from the agents' contracts (reconciled)
        budget_limit = stage_def.get("budget_limit", 3.0)
        try:
            stage_token_cap = sum(
                (get_contract(a).get("max_input_tokens", 0) + get_contract(a).get("max_output_tokens", 0))
                for a in agents) or 30000
            stage_token_cap = int(stage_token_cap * 1.5)
        except Exception:
            stage_token_cap = 30000
        self.budget_manager.create_budget(
            f"stage_{stage_id}",
            BudgetType.STAGE_TOTAL,
            max_tokens=stage_token_cap,
            scope=stage_id
        )
        
        # Mark stage as running
        self.dag_executor.mark_running(stage_id)
        self.execution.current_stage = stage_id
        self._emit_lifecycle("stage_started", stage=stage_id, agents=len(agents))
        stage_started_at = datetime.now().isoformat()
        # Per-stage timing for stop conditions: measure THIS stage, and exclude
        # time spent waiting on a human (approvals/prompts). Human-wait is tracked
        # PER STAGE (dict) so parallel stages never clobber each other.
        try:
            if not isinstance(getattr(self, "_stage_human_wait", None), dict):
                self._stage_human_wait = {}
            self._stage_human_wait[stage_id] = 0.0
        except Exception:
            pass
        self._stage_started_at = stage_started_at

        print(f"  Stage: {stage_name} ({stage_type})")
        print(f"  Stage depends_on: {self.dag_executor.stages.get(stage_id).depends_on if self.dag_executor.stages.get(stage_id) else []}")
        print(f"  Agents: {len(agents)}")
        print(f"  Budget: ${budget_limit}")
        print(f"  Stage start: {stage_started_at}")
        agent_deps = stage_def.get("agent_dependencies", {})
        if agent_deps:
            chain = " -> ".join(agents)
            print(f"  Agent order: {chain}")
            for a, preds in agent_deps.items():
                if preds:
                    print(f"    {a} runs after {preds}")

        # Execute agents for this stage
        stage_executions = []
        # Checkpoint at stage start so an interrupted run has a resume record.
        try:
            self._save_checkpoint()
        except Exception as e:
            print(f"  [checkpoint] {e}")
        # Feature subsets only apply to implementation-iteration stages; planning
        # is triggered lazily (after ideation/design) so it sees the features.
        phase_features = self.phasing.features_for_stage(stage_id) if stage_id in PHASE_STAGES else []
        if phase_features:
            print(f"  Phase features ({stage_id}): {phase_features}")
        for agent_id in agents:
            # Honour cross-process stop/pause between agents (not only between stages).
            ctrl = ""
            try:
                ctrl = str((self._read_control().get("action") or "")).lower()
            except Exception:
                ctrl = ""
            if ctrl == "stop" or getattr(self, "_stop_requested", False):
                print("  [Orchestrator] Stop requested (between agents); halting stage.")
                self._stop_requested = True
                self._write_control("stop")
                try:
                    self._save_checkpoint()
                except Exception:
                    pass
                return
            while ctrl == "pause" and not getattr(self, "_stop_requested", False):
                time.sleep(1)
                try:
                    ctrl = str((self._read_control().get("action") or "")).lower()
                except Exception:
                    ctrl = ""
                if ctrl == "stop":
                    self._stop_requested = True
                    self._write_control("stop")
                    try:
                        self._save_checkpoint()
                    except Exception:
                        pass
                    return
            agent_task = f"Execute {stage_name}"
            if agent_id == "implement" and phase_features:
                agent_task = (
                    f"Implement ONLY the following features for {stage_name}: "
                    + "; ".join(phase_features)
                    + ". Do NOT implement features assigned to other phases. "
                    "Produce concise, complete output for these features only."
                )
            elif stage_id == "0" and self.project_idea:
                agent_task = (
                    "Product brief (build THIS product, do not invent a different one):\n"
                    f"{self.project_idea}\n\nProduce the ideation document for this product."
                )
            elif stage_id == "0a" and getattr(self, "_discovery_refined", ""):
                agent_task = (
                    "360-degree discovery clarifications (already answered by the product "
                    "owner — treat as authoritative; do NOT re-ask them):\n"
                    f"{self._discovery_refined}\n\n"
                    "Produce the discovery document (domain analysis, stakeholders, personas, "
                    "clarified goal) for this product."
                )

            # Per-agent control (BI-0046): pause / stop / cancel a single agent.
            _op = self._agent_control_op(agent_id)
            if _op in ("stop", "cancel"):
                print(f"    [AGENT CONTROL] {agent_id}: {_op} requested - skipping")
                self._clear_agent_control(agent_id)
                self._show_progress(stage_id, agent_id, "skipped")
                continue
            while _op == "pause" and not getattr(self, "_stop_requested", False):
                print(f"    [AGENT CONTROL] {agent_id}: paused; waiting for resume...")
                time.sleep(2)
                _op = self._agent_control_op(agent_id)
                if _op in ("", "resume"):
                    break
                if _op in ("stop", "cancel"):
                    self._clear_agent_control(agent_id)
                    self._show_progress(stage_id, agent_id, "skipped")
                    break
            if _op in ("stop", "cancel"):
                continue

            model_cfg = self._get_agent_model_config(agent_id, stage_id)
            print(f"    Executing agent: {agent_id} [model={model_cfg.get('model')}]")
            try:
                from core import work_estimate as _we
                _e = _we.estimate_agent(self.project_dir, agent_id, stage_id,
                                        model=model_cfg.get("model", ""))
                print(f"    [Estimate] {agent_id}: strategy={_e['strategy']} "
                      f"llm~{_e['llm_typical']} ({_e['llm_min']}-{_e['llm_max']}) "
                      f"tools~{_e['tools_typical']} ~{_e['est_minutes']}min ({_e['basis']})")
            except Exception:
                pass
            if agent_id == "orchestrator":
                try:
                    print(f"    [Coordinator] judgment-plane invoked @ stage {stage_id} "
                          f"(runtime is the control plane)")
                except Exception:
                    pass

            if agent_id == "implement":
                try:
                    self._ensure_test_scaffolds(stage_id)
                except Exception as e:
                    print(f"  [TestGen] {e}")

            self._show_progress(stage_id, agent_id, "running")
            self._live_set(agent_id, stage_id, "running")
            self._emit_lifecycle("agent_started", stage=stage_id, agent=agent_id,
                                 model=model_cfg.get("model"))
            _hb_stop = threading.Event()
            self._start_heartbeat(agent_id, stage_id, _hb_stop)
            try:
                execution = self.execute_agent(agent_id, stage_id, agent_task)
            finally:
                _hb_stop.set()
            self._live_clear(agent_id, stage_id)
            _est = str(getattr(execution, "status", "completed"))
            self._emit_lifecycle(
                "agent_completed" if _est in ("completed", "skipped") else
                ("agent_failed" if _est == "failed" else "agent_stage_changed"),
                stage=stage_id, agent=agent_id, status=_est,
                model=getattr(execution, "selected_model", "") or model_cfg.get("model"),
                tokens=getattr(execution, "tokens_used", 0),
                cost=getattr(execution, "cost", 0.0),
                artifacts=len(getattr(execution, "artifacts", []) or []))
            try:
                self._show_progress(stage_id, agent_id, str(getattr(execution, "status", "completed")))
            except Exception:
                pass

            # 1.3 HIL step mode: pause after each agent (terminal, or interactive bridge).
            if getattr(self, "step_pause", False):
                from core import interactive as _interactive
                if _interactive.enabled():
                    _interactive.ask(
                        f"  [STEP] {agent_id} done ({execution.status}). "
                        f"Press Enter to continue... ", "",
                        project_dir=getattr(self, "project_dir", None), kind="step")
                elif sys.stdin.isatty():
                    try:
                        input(f"  [STEP] {agent_id} done ({execution.status}). "
                              f"Press Enter to continue, Ctrl+C to abort... ")
                    except (EOFError, KeyboardInterrupt):
                        self._stop_requested = True
                        self._write_control("stop")
                        return

            # Compliance-driven bounded retry: re-run the agent with the
            # violation feedback until it passes or the retry cap is hit.
            attempts = 0
            while execution.status == "needs_retry" and attempts < self.max_compliance_retries:
                attempts += 1
                feedback = ""
                try:
                    feedback = (execution.compliance_report or {}).get("retry_feedback", "")
                except Exception:
                    feedback = ""
                print(f"    [COMPLIANCE RETRY {attempts}/{self.max_compliance_retries}] "
                      f"{agent_id} re-running with feedback")
                retry_task = agent_task + (
                    "\n\nCOMPLIANCE FEEDBACK — fix these issues in this output:\n"
                    + (feedback or "(see compliance report)"))
                self._live_set(agent_id, stage_id, "running")
                self._emit_lifecycle("agent_started", stage=stage_id, agent=agent_id,
                                     retry=attempts)
                _hb_stop2 = threading.Event()
                self._start_heartbeat(agent_id, stage_id, _hb_stop2)
                try:
                    execution = self.execute_agent(agent_id, stage_id, retry_task)
                finally:
                    _hb_stop2.set()
                self._live_clear(agent_id, stage_id)
                _rst = str(getattr(execution, "status", "completed"))
                self._emit_lifecycle(
                    "agent_completed" if _rst in ("completed", "skipped") else
                    ("agent_failed" if _rst == "failed" else "agent_stage_changed"),
                    stage=stage_id, agent=agent_id, status=_rst, retry=attempts)
            stage_executions.append(execution)
            self._record_cost_kpi(agent_id, stage_id, execution)
            if execution.status not in ("completed", "skipped"):
                self._handle_agent_failure(agent_id, stage_id, execution)

            # Accumulate totals + record timing under lock (parallel-safe)
            # Per-agent timing
            try:
                a_start = datetime.fromisoformat(execution.started_at)
                a_end = datetime.fromisoformat(execution.completed_at) if execution.completed_at else datetime.now()
                a_dur = (a_end - a_start).total_seconds()
            except Exception:
                a_start = a_end = None
                a_dur = 0.0
            timing = {
                "stage_id": stage_id,
                "agent_id": agent_id,
                "model": execution.selected_model or model_cfg.get("model"),
                "status": execution.status,
                "started_at": execution.started_at,
                "completed_at": execution.completed_at,
                "duration_seconds": round(a_dur, 2),
            }
            with self._state_lock:
                self.execution.total_tokens += execution.tokens_used
                self.execution.total_cost += execution.cost
                self.agent_timings.append(timing)

            # Live journal: record what this agent did
            if self.journal:
                try:
                    self.journal.record_agent(
                        agent_id, stage_id, execution.status,
                        getattr(execution, "artifacts", []),
                        execution.total_tokens, execution.cost, a_dur)
                except Exception:
                    pass

            # Run breaker: enforce hard wall + rate/loop detection
            if self.run_breaker:
                try:
                    dec = self.run_breaker.add_usage(execution.total_tokens, execution.cost)
                    if dec.action == "stop":
                        print(f"  [BREAKER] STOP: {dec.reason}")
                        self._log_decision("breaker_stop", f"{agent_id}@{stage_id}", dec.reason)
                        self.execution.phase = PipelinePhase.FAILED
                        self.execution.error = f"Run breaker: {dec.reason}"
                        break
                    elif dec.action == "throttle":
                        print(f"  [BREAKER] THROTTLE: {dec.reason} -> using cheapest capable model next")
                        self._force_cheap = True
                        self._log_decision("breaker_throttle", f"{agent_id}@{stage_id}", dec.reason)
                except Exception:
                    pass

            _amodel = getattr(execution, "selected_model", "") or model_cfg.get("model")
            _aarts = len(getattr(execution, "artifacts", []) or [])
            print(f"    Status: {execution.status}")
            print(f"    Model: {_amodel} | provider: {getattr(execution, 'selected_provider', '')}")
            print(f"    Started: {execution.started_at}")
            print(f"    Ended:   {execution.completed_at}")
            print(f"    Duration: {a_dur:.1f}s | Artifacts: {_aarts} | "
                  f"Tokens: {execution.tokens_used} | Cost: ${execution.cost:.4f}")
            try:
                from core import call_ledger as _cl
                # Agent-scoped totals (the LLM client has no run_id, so filter by agent).
                _cs = _cl.summary(self.project_dir, agent=agent_id).get("totals", {})
                print(f"    Calls: llm={_cs.get('llm_calls', 0)} tools={_cs.get('tool_calls', 0)} "
                      f"| prompt_tokens={_cs.get('prompt_tokens', 0)} "
                      f"output_tokens={_cs.get('output_tokens', 0)} "
                      f"reasoning={_cs.get('reasoning_tokens', 0)}")
            except Exception:
                pass
            print(f"    Knowledge: {len(execution.knowledge_used)} resources")
            print(f"    Compliance: {'PASS' if execution.compliance_passed else 'FAIL'}")
            print(f"    Time: {execution.started_at} -> {execution.completed_at} "
                  f"({a_dur:.1f}s)")

            # Brief after-agent summary: what was done, artifacts produced, what's next.
            try:
                from core.progress import stage_summary as _ss
                print(_ss(self.pipeline_def, stage_id, agent_id, execution.status,
                          getattr(execution, "artifacts", []), execution.total_tokens,
                          execution.cost, a_dur, project_dir=self.project_dir))
            except Exception:
                pass

            # Orchestrator-routed delegation (opt-in)
            self._maybe_delegate(stage_id, agent_id, execution)

            # If agent rejected, stop stage
            if execution.status == "rejected":
                print(f"  Stage {stage_id}: ABORTED (agent {agent_id} rejected)")
                break
        
        # Store stage executions (merge prior agents when running a subset)
        if getattr(self, "only_agents", None) and stage_id in self.execution.stage_executions:
            new_ids = {e.agent_id for e in stage_executions}
            prior = [e for e in self.execution.stage_executions[stage_id]
                     if e.agent_id not in new_ids]
            stage_executions = prior + stage_executions
        with self._state_lock:
            self.execution.stage_executions[stage_id] = stage_executions
            # Totals derived from the authoritative per-agent executions (idempotent;
            # prevents double-counting/drift on subset or resume reruns).
            try:
                self.execution.total_tokens = sum(
                    e.tokens_used for execs in self.execution.stage_executions.values()
                    for e in execs)
                self.execution.total_cost = sum(
                    e.cost for execs in self.execution.stage_executions.values()
                    for e in execs)
            except Exception:
                pass

        # Architect decides the tech stack -> persist + gate on change
        if stage_id == "2":
            try:
                self._finalize_tech_stack(stage_executions)
            except Exception as e:
                print(f"[TechStack] {e}")
        
        # Check if all agents completed
        all_passed = all(e.status in ["completed", "skipped"] for e in stage_executions)
        # Compliance is judged over ALL agents (a failed/blocked agent must NOT be
        # excluded, else a stage could report compliance=true while its agent failed).
        compliance_passed = bool(stage_executions) and all(e.compliance_passed for e in stage_executions)
        
        if all_passed:
            self.dag_executor.mark_completed(stage_id, {
                "agents": len(stage_executions),
                "artifacts": [a for e in stage_executions for a in e.artifacts],
                "compliance_passed": compliance_passed,
                "total_tokens": sum(e.tokens_used for e in stage_executions),
                "total_cost": sum(e.cost for e in stage_executions),
            })
            if compliance_passed:
                print(f"  Stage {stage_id}: COMPLETED (compliance PASS)")
            else:
                print(f"  Stage {stage_id}: COMPLETED (compliance warnings)")
            # 3a: refresh the human-readable artifact index (stage meta + INDEX.md).
            try:
                from core import stage_paths as _sp
                _sp.refresh(self.project_dir, stage_id)
            except Exception:
                pass
            # Traceability hub: index this stage's ids (declared families only).
            try:
                from core import traceability as _th
                _hub = _th.refresh_hub(self.project_dir)
                _un = (_hub.get("undeclared") or {}).get(stage_id)
                if _un:
                    print(f"  [Trace] undeclared id prefixes in stage {stage_id}: {_un}")
            except Exception:
                pass
            # Refresh the run's log index (logs/<run_id>/INDEX.json).
            try:
                from core import log_router as _lr
                _run_id = ""
                try:
                    _run_id = getattr(getattr(self, "execution", None), "pipeline_id", "") or ""
                except Exception:
                    _run_id = ""
                _lr.update_index(self.project_dir, _run_id)
                _lr.log_event(_lr.run_log_path(self.project_dir, _run_id),
                              run_id=_run_id, stage=stage_id, event="stage_complete",
                              message=f"agents={len(stage_executions)} compliance={compliance_passed}")
                # Refresh the static centralized views (logs index + traceability).
                try:
                    from core import views as _views
                    _views.write_all(self.project_dir)
                except Exception:
                    pass
            except Exception:
                pass
        else:
            failed_agents = [e.agent_id for e in stage_executions if e.status not in ["completed", "skipped"]]
            self.dag_executor.mark_failed(stage_id, f"Failed agents: {failed_agents}")
            print(f"  Stage {stage_id}: FAILED (agents failed)")
            self._emit_lifecycle("stage_failed", stage=stage_id,
                                 failed_agents=",".join(failed_agents))
        
        # Record stage duration for time estimation. Exclude human-wait so the
        # time budget reflects WORK, not the time a person took to answer.
        _wall = time.time() - stage_start
        _human = self._stage_wait(stage_id)
        stage_duration = max(0.0, _wall - _human)
        stage_completed_at = datetime.now().isoformat()
        with self._state_lock:
            self.stage_timings[stage_id] = {
                "name": stage_name,
                "started_at": stage_started_at,
                "completed_at": stage_completed_at,
                "duration_seconds": round(stage_duration, 2),
                "human_wait_seconds": round(_human, 2),
                "agents": [e.agent_id for e in stage_executions],
            }
        print(f"  Stage {stage_id} end: {stage_completed_at} "
              f"(work {stage_duration:.1f}s, human-wait {_human:.1f}s)")
        self._record_stage_duration(stage_duration)

        # Auto mode: ideation partner (product-owner) distills the idea (stage 0 only).
        # SKIP when a dedicated business stage (0b) owns product-owner, else the agent
        # runs twice (wasted calls + duplicate compliance churn).
        if stage_id == "0":
            try:
                from core.human_proxy import is_auto, ideation_partner
                _has_0b = bool((self.pipeline_def or {}).get("stages", {}).get("0b"))
                if is_auto(self.project_dir) and not _has_0b:
                    print("  [AUTO] ideation partner (product-owner) distilling the idea …")
                    ideation_partner(self, "0")
                elif is_auto(self.project_dir) and _has_0b:
                    print("  [AUTO] ideation partner skipped (product-owner runs in stage 0b)")
            except Exception as e:
                print(f"[HumanProxy] {e}")

        # Post-discovery: evaluate + confirm the optional-capability plan from the
        # discovery output and apply it (skip unneeded optional stages). Dependency
        # warnings are surfaced; a confirmed plan is never re-planned on resume.
        if stage_id == "0a" and not getattr(self, "_plan_done", False):
            try:
                from core import run_plan as _rp
                _plan = _rp.ensure_plan(self.project_dir, self.project, force=True)
                if _plan.get("confirmed"):
                    _skipped = _rp.apply_to_dag(self.dag_executor, _plan)
                    self._plan_done = True
                    print(f"[RunPlan] kind={_plan.get('kind')} "
                          f"include={_plan.get('include_optional')} skip={_skipped}")
                    for _w in (_plan.get("warnings") or []):
                        print(f"  [RunPlan] WARN {_w}")
                    self._emit_lifecycle("plan_confirmed", stage="0a",
                                         include=",".join(_plan.get("include_optional") or []),
                                         skip=",".join(_plan.get("skip_optional") or []))
            except Exception as _pe:
                print(f"[RunPlan] post-discovery failed: {_pe}")

        # BI-0210 Gate A: post-ideation model & capability strategy. Enables packs + recomposes
        # the DAG (so pack stages like 4m exist for stage 1+). No-op for plain-text projects.
        if stage_id == "0a" and not getattr(self, "_strategy_a_done", False):
            try:
                from core import model_strategy as _ms
                _sa = _ms.gate_a(self.project_dir)
                self._strategy_a_done = True
                if not _sa.get("noop"):
                    _packs = (_sa.get("gate_a") or {}).get("enabled_packs") or []
                    print(f"[ModelStrategy] gate A: packs={_packs} "
                          f"feasibility={(_sa.get('gate_a') or {}).get('feasibility_verdict')}")
                    # re-compose the effective definition and reconcile the running DAG
                    try:
                        from core import pipeline_composition as _pc
                        _st = self.dag_executor.export_state() if hasattr(self.dag_executor, "export_state") else None
                        self.pipeline_def = _pc.effective_definition(self.pipeline_def, self.project_dir)
                        if getattr(self, "model_router", None):
                            self.model_router.pipeline_def = self.pipeline_def
                        from core.dag_executor import DAGExecutor as _DAG
                        self.dag_executor = _DAG(self.pipeline_def)
                        if _st is not None and hasattr(self.dag_executor, "restore_states"):
                            try:
                                self.dag_executor.restore_states(_st)
                            except Exception:
                                pass
                        print(f"  [ModelStrategy] recomposed stages={len(self.pipeline_def.get('stages') or {})}")
                    except Exception as _ce:
                        print(f"  [ModelStrategy] recompose skipped: {_ce}")
                    self._emit_lifecycle("model_strategy_a", stage="0a", packs=",".join(_packs))
            except Exception as _se:
                print(f"[ModelStrategy] gate A failed: {_se}")

        # Live journal + standardized checkpoint docs (agent-context, compact, feature-status)
        self._write_stage_checkpoints(stage_id, stage_executions)
        # Refresh the final report after every stage -> it is always current (even before the
        # pipeline ends), and it now includes the per-agent brief summaries.
        try:
            self._generate_final_report()
        except Exception:
            pass
        # Canonical run-lifecycle event (taxonomy) for analytics.
        try:
            from core import events as _ev
            _ev.emit(self.project_dir, "stage_completed", stage=stage_id,
                     run_id=str(getattr(getattr(self, "execution", None), "pipeline_id", "") or ""),
                     agents=len(stage_executions), compliance=compliance_passed)
        except Exception:
            pass
        # Architecture diagram (5.5) + sizing/footprint after the architect stage.
        if stage_id == "2":
            try:
                from core.architecture_diagram import generate as gen_diagram
                gen_diagram(self.project_dir)
            except Exception as e:
                print(f"[Diagram] {e}")
            try:
                from core.sizing import compute as compute_sizing
                s = compute_sizing(self.project_dir, self.project)
                print(f"  [SIZING] {s['deployment_model']} · prod="
                      f"{s['environments'].get('prod')}")
            except Exception as e:
                print(f"[Sizing] {e}")
            try:
                from core.target_advisor import recommend as recommend_targets
                r = recommend_targets(self.project_dir, self.project)
                print(f"  [TARGETS] surface={r['delivery_surface']} default={r['default']} "
                      f"recommended={[c['key'] for c in r['recommended']]}")
            except Exception as e:
                print(f"[Targets] {e}")
            # BI-0192 Gate B: post-architect model & capability strategy refinement (no-op for text).
            if not getattr(self, "_strategy_b_done", False):
                try:
                    from core import model_strategy as _ms
                    _sb = _ms.gate_b(self.project_dir)
                    if not _sb.get("noop"):
                        _ms.apply(self.project_dir, self)
                        _asm = (_sb.get("gate_b") or {}).get("assignments") or []
                        _ov = (_sb.get("applied") or {}).get("overrides") or {}
                        print(f"[ModelStrategy] gate B: {len(_asm)} assignment(s), "
                              f"applied={len(_ov or {})}")
                        self._emit_lifecycle("model_strategy_b", stage="2",
                                             assignments=str(len(_asm)))
                    self._strategy_b_done = True
                except Exception as _be:
                    print(f"[ModelStrategy] gate B failed: {_be}")
        # Feature-level status tracking (ProductPlan)
        self._track_features_for_stage(stage_id, stage_executions)

        # BI-0217: the package stage emits the product BOM/footprint artifact.
        if stage_id == "9":
            # BI-0219: emit governance report (model/data cards + provenance + checkpoints) before BOM.
            try:
                from core import guardrails as _gr
                _models = []
                try:
                    from core import model_router as _mr
                except Exception:
                    _mr = None
                _rep = _gr.build_report(self.project_dir, models=_models)
                _gr.write_report(self.project_dir, _rep)
                _blocked = int(_rep.get("blocked") or 0)
                if _blocked:
                    print(f"  [Guardrails] {_blocked} blocked finding(s) recorded")
            except Exception as e:
                print(f"[Guardrails] {e}")
            try:
                from core import bom as _bom
                _p = _bom.write(self.project_dir)
                if _p:
                    print(f"  [BOM] wrote {os.path.relpath(_p, self.project_dir)}")
            except Exception as e:
                print(f"[BOM] {e}")
            # BI-0214: feasibility Phase 2 (DESTINATION) at packaging.
            try:
                from core import feasibility as _fs
                _fd = _fs.evaluate(self.project_dir, phase="destination").get("phase2_destination", {})
                if _fd:
                    print(f"  [Feasibility] destination verdict={_fd.get('verdict')} "
                          f"shipping={_fd.get('shipping_mode')} sku={_fd.get('sku')}")
            except Exception:
                pass

        # BI-0191: media QA — validate media outputs when media exists (no-op otherwise).
        if any(getattr(e, "agent_id", "") == "validate" for e in stage_executions):
            try:
                from core import media_qa as _mqa
                _r = _mqa.validate_project(self.project_dir)
                if not _r.get("noop"):
                    print(f"  [MediaQA] ok={_r.get('ok')} findings={len(_r.get('findings') or [])} "
                          f"degraded={_r.get('degraded')}")
                    self._emit_lifecycle("media_qa", stage=stage_id,
                                         ok=str(_r.get("ok")),
                                         findings=str(len(_r.get("findings") or [])))
            except Exception as _qe:
                print(f"[MediaQA] {_qe}")

        # Post-deploy validation (8.3/8.4) after a deployment agent runs
        if any(getattr(e, "agent_id", "") == "production-deploy" for e in stage_executions):
            try:
                self._run_post_deploy()
                self._vcs_rc_tag()   # tag the staging (most stable) build
            except Exception as e:
                print(f"[PostDeploy] {e}")

        # VCS: commit stage output and merge the feature branch into develop
        if stage_id in ("4-0", "4a", "4b", "4c", "4d", "4e", "4f"):
            try:
                self._vcs_stage_finalize(stage_id)
            except Exception as e:
                print(f"[VCS] {e}")
            try:
                self._vcs_wip()
            except Exception:
                pass

        # VCS release: develop -> main + release tag (only on GO, and only with HIL/auto approval)
        if stage_id == "10a":
            # QA Go/No-Go enforcement: NO-GO blocks Deploy (stage 11) unless HIL override.
            try:
                import json as _json
                from core.qa_report import load as _gng_load
                decision = (_gng_load(self.project) or {}).get("decision")
                override = False
                pj = os.path.join(self.project_dir, "project.json")
                if os.path.exists(pj):
                    with open(pj, encoding="utf-8") as f:
                        override = bool(((_json.load(f) or {}).get("qa") or {}).get("override_gonogo"))
                if decision == "NO-GO" and not override:
                    self.dag_executor.mark_failed(stage_id, "QA Go/No-Go = NO-GO (deploy blocked)")
                    print("  [QA-GATE] NO-GO -> deploy blocked (stage 11 will not run). "
                          "Request HIL override (qa.override_gonogo) to proceed.")
                elif decision == "NO-GO":
                    print("  [QA-GATE] NO-GO overridden by HIL -> deploy allowed")
            except Exception as e:
                print(f"[QA-GATE] {e}")
            try:
                self._vcs_release()
            except Exception as e:
                print(f"[VCS] {e}")
        
        # Check for anomalies
        self._detect_anomaly(stage_id, stage_duration)
        
        # Check for approval gate after stage completes
        if not self._check_approval_gate(stage_id):
            print(f"  Stage {stage_id}: PAUSED (approval gate pending)")
            self.execution.phase = PipelinePhase.PAUSED
