"""
Agent execution mixin (extracted from pipeline_executor - 1A.11).

Mixin (not composition): execute_agent orchestrates the full per-agent flow and
operates on executor state (`self`). Moved verbatim to keep behavior identical.
"""
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.artifact_store import create_or_update_artifact
from core.budget_conservation import should_skip_agent
from core.context_manager import build_context_package, get_contract
from core.issue_tracker import add_issue
from core.orchestrator.types import AgentExecution


# Fields copied from an amended/regenerated re-run back onto the original execution.
_HIL_COPY_FIELDS = (
    "artifacts", "input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens",
    "total_tokens", "selected_model", "selected_provider", "model_cost_per_1k_input",
    "model_cost_per_1k_output", "cost", "tokens_used", "context_tokens",
)


def _merge_execution(target, source):
    """Copy usage/artifact fields from a re-run execution onto the original."""
    for field in _HIL_COPY_FIELDS:
        try:
            val = getattr(source, field, None)
            if val is not None:
                setattr(target, field, val)
        except Exception:
            pass



class AgentExecutionMixin:
    
    def execute_agent(self, agent_id: str, stage_id: str, task: str) -> AgentExecution:
        """Execute a single agent with full integration:
        Context Manager -> Budget Check -> Model Routing -> Skill Routing -> 
        Circuit Breaker Check -> Agent Execution -> Artifacts -> Compliance -> 
        Design Critic -> Visual QA -> Issue Tracking -> Memory
        """
        execution = AgentExecution(
            agent_id=agent_id,
            stage_id=stage_id,
            status="running",
            started_at=datetime.now().isoformat()
        )
        
        try:
            # 0. Check circuit breaker
            cb_name = f"{agent_id}_{stage_id}"
            if not self.circuit_breakers.can_execute(cb_name):
                execution.status = "blocked"
                execution.error = "Circuit breaker open - too many failures"
                execution.completed_at = datetime.now().isoformat()
                return execution
            
            # 1. Check conservation mode - skip if needed
            if should_skip_agent(agent_id, self.conservation_state):
                execution.status = "skipped"
                execution.error = f"Skipped due to budget conservation ({self.conservation_state.mode} mode)"
                execution.completed_at = datetime.now().isoformat()
                self.conservation_state.skipped_agents.append(agent_id)
                return execution
            
# 2. Build minimum context package (Context Manager)
            context_pkg = build_context_package(
                agent_name=agent_id,
                project=self.project,
                stage=stage_id,
                artifacts=self._collect_stage_artifacts(stage_id),
            )
            execution.context_tokens = context_pkg.get("tokens_used", 0)
            
            # 3. Budget check before execution
            contract = get_contract(agent_id)
            estimated_cost = (execution.context_tokens / 1000) * 0.002  # rough estimate
            stage_budget_id = f"stage_{stage_id}"
            can_proceed = self.budget_manager.request_tokens(
                stage_budget_id, execution.context_tokens
            )
            
            if not can_proceed:
                execution.status = "blocked"
                execution.error = "Budget exceeded for stage"
                execution.completed_at = datetime.now().isoformat()
                return execution
            
            # 4. Model routing - resolve from tier config (single source of truth)
            #    The same resolver is used by _call_llm so the reported model
            #    always matches the model actually invoked. No model names are
            #    hardcoded here.
            try:
                model_cfg = self._get_agent_model_config(agent_id, stage_id)
                selected_model = model_cfg.get("model")
            except Exception as e:
                print(f"[WARNING] Model resolution failed: {e}")
                selected_model = None
            
            # Check for conservation mode model downgrade
            from core.budget_conservation import get_model_downgrade
            downgrade = get_model_downgrade(agent_id, self.conservation_state)
            if downgrade:
                selected_model = downgrade
                self.conservation_state.model_downgrades.append(f"{agent_id}: {downgrade}")
            
            # 5. Get knowledge for this agent (Skill Routing)
            knowledge = self.get_knowledge_for_agent(agent_id, stage_id, task)
            execution.knowledge_used = knowledge.selected_resources
            
            # 6. Use reasoning if needed
            if agent_id in ["design", "architect", "ideation", "design_critic"]:
                reasoning_result = self.use_reasoning(
                    "problem_restatement",
                    task,
                    {"agent": agent_id, "stage": stage_id, "context_tokens": execution.tokens_used}
                )
                execution.reasoning_used = reasoning_result.skill
            
            # 7. Store episodic memory
            self.store_memory(
                memory_type="episodic",
                content=f"Agent {agent_id} started stage {stage_id}: {task} | Context: {execution.tokens_used} tokens | Skills: {len(knowledge.selected_resources)} | Model: {selected_model}",
                source=agent_id,
                confidence=0.95,
                tags=[stage_id, agent_id]
            )
            
            # 8. Generate structured artifacts with token tracking
            self._audit_trail_log("agent_start", agent_id, stage_id)
            artifacts, agent_execution = self._generate_agent_artifacts(agent_id, stage_id, task)

            # Transient LLM failure (fallback): retry a couple of times before failing.
            _llm_attempts = 0
            while (agent_execution.status == "failed"
                   and "LLM unavailable" in (agent_execution.error or "")
                   and _llm_attempts < 2):
                _llm_attempts += 1
                print(f"    [LLM RETRY {_llm_attempts}/2] {agent_id}: transient failure, retrying")
                time.sleep(3)
                artifacts, agent_execution = self._generate_agent_artifacts(agent_id, stage_id, task)

            # Hard failure (e.g. LLM unavailable): do not continue as success.
            if agent_execution.status == "failed":
                execution.status = "failed"
                execution.error = agent_execution.error or "agent generation failed"
                execution.completed_at = datetime.now().isoformat()
                self.circuit_breakers.record_failure(cb_name)
                self.store_memory(
                    memory_type="failure",
                    content=f"Agent {agent_id} failed in stage {stage_id}: {execution.error}",
                    source=agent_id, confidence=0.95,
                    tags=[stage_id, agent_id, "failed"])
                print(f"    Status: failed ({execution.error})")
                return execution

            # Truncated / incomplete output: surface needs_retry (stage loop will retry),
            # never silently accept it as "completed" (no completed artifact was written).
            if getattr(agent_execution, "status", "") == "needs_retry":
                execution.status = "needs_retry"
                execution.error = agent_execution.error or "output truncated (incomplete artifact)"
                execution.completed_at = datetime.now().isoformat()
                self.store_memory(
                    memory_type="failure",
                    content=f"Agent {agent_id} needs_retry in stage {stage_id}: {execution.error}",
                    source=agent_id, confidence=0.9,
                    tags=[stage_id, agent_id, "needs_retry"])
                print(f"    Status: needs_retry ({execution.error})")
                return execution

            execution.artifacts = artifacts
            
            # Copy token info from agent_execution to execution
            execution.input_tokens = agent_execution.input_tokens
            execution.output_tokens = agent_execution.output_tokens
            execution.cached_tokens = agent_execution.cached_tokens
            execution.reasoning_tokens = agent_execution.reasoning_tokens
            execution.total_tokens = agent_execution.total_tokens
            execution.selected_model = agent_execution.selected_model
            execution.selected_provider = agent_execution.selected_provider
            execution.model_cost_per_1k_input = agent_execution.model_cost_per_1k_input
            execution.model_cost_per_1k_output = agent_execution.model_cost_per_1k_output
            execution.cost = agent_execution.cost
            execution.tokens_used = agent_execution.total_tokens  # For backward compatibility
            
            # Log to audit log (with explicit start/end timings)
            audit_end = execution.completed_at or datetime.now().isoformat()
            execution.duration_ms = int((datetime.fromisoformat(audit_end) -
                                        datetime.fromisoformat(execution.started_at)).total_seconds() * 1000)
            audit_entry = {
                "entry_id": f"audit-{int(time.time()*1000)}-{agent_id}",
                "agent": agent_id,
                "stage": stage_id,
                "action": "execute",
                "agent_id": agent_id,
                "stage_id": stage_id,
                "model": execution.selected_model or selected_model,
                "provider": execution.selected_provider,
                "input_tokens": execution.input_tokens,
                "output_tokens": execution.output_tokens,
                "cached_tokens": execution.cached_tokens,
                "total_tokens": execution.total_tokens,
                "cost": execution.cost,
                "cache_hit": agent_execution.cache_hit if hasattr(agent_execution, 'cache_hit') else False,
                "chunking_used": agent_execution.chunking_used if hasattr(agent_execution, 'chunking_used') else False,
                "chunks_count": agent_execution.chunks_count if hasattr(agent_execution, 'chunks_count') else 1,
                "model_context_window": agent_execution.model_context_window if hasattr(agent_execution, 'model_context_window') else 0,
                "prompt_chars": agent_execution.prompt_chars if hasattr(agent_execution, 'prompt_chars') else 0,
                "output_chars": agent_execution.output_chars if hasattr(agent_execution, 'output_chars') else 0,
                "artifacts_used": agent_execution.artifacts_used if hasattr(agent_execution, 'artifacts_used') else [],
                "started_at": execution.started_at,
                "completed_at": audit_end,
                "duration_ms": execution.duration_ms,
                "duration_seconds": round(execution.duration_ms / 1000.0, 2),
                "finish_reason": execution.finish_reason,
                "truncated": execution.truncated,
                "retries": execution.retries,
                "compaction_used": execution.compaction_used,
                "compaction_saved_chars": execution.compaction_saved_chars,
                "continuations": execution.continuations,
                "timestamp": datetime.now().isoformat(),
                "status": execution.status
            }
            self.audit_log.log_agent_execution(audit_entry)
            
            # 9. Store artifacts in artifact store
            for artifact_path in artifacts:
                try:
                    create_or_update_artifact(
                        project=self.project,
                        artifact_path=artifact_path,
                        agent=agent_id,
                        stage=stage_id,
                    )
                except Exception:
                    pass

            # 9b. Diagram renderer (best-effort, stages 1/1a): extract ```mermaid
            #     blocks -> .mmd (+ .svg/.pdf when a CLI exists). Never fabricates
            #     files; reports "renderer unavailable" so a BI can be logged.
            if stage_id in ("1", "1a") and artifacts:
                for _ap in artifacts:
                    if not str(_ap).endswith(".md"):
                        continue
                    try:
                        from core.diagram_render import render as _render_diagrams
                        _rep = _render_diagrams(getattr(self, "project_dir", ""), stage_id, _ap)
                        if not _rep.get("count"):
                            print(f"  [DIAGRAMS] {os.path.basename(_ap)}: no mermaid blocks")
                        elif _rep.get("renderer") == "unavailable":
                            print(f"  [DIAGRAMS] {os.path.basename(_ap)}: renderer unavailable "
                                  f"({_rep.get('reason')}); {len(_rep.get('mmd') or [])} .mmd written")
                        else:
                            print(f"  [DIAGRAMS] {os.path.basename(_ap)}: {_rep.get('count')} block(s), "
                                  f"{len(_rep.get('rendered') or [])} rendered via {_rep.get('renderer')}")
                    except Exception as _de:
                        print(f"  [DIAGRAMS] render skipped: {_de}")
            
            # 10. Record spend in budget tracker
            self.budget_tracker.record_spend(
                project=self.project,
                agent=agent_id,
                model=execution.selected_model or selected_model,
                tokens_input=execution.input_tokens,
                tokens_output=execution.output_tokens,
                cost=execution.cost
            )
            
            # 10b. Materialize canonical artifacts for compliance + audit trail
            #      (docs/*.md, project-config.json, agent-audit.md)
            self._materialize_canonical_artifacts(agent_id, stage_id, artifacts)
            self._append_agent_audit_md(agent_id, stage_id, execution.status)
            
            # 11. Run compliance suite (rule, knowledge, gate, stack, verification)
            compliance_outcome = self.compliance_orchestrator.run(
                agent_id=agent_id,
                stage_id=stage_id,
                artifacts=artifacts,
                auto_approve=self.auto_approve,
                tech_stack_hints=getattr(self, "tech_stack_hints", []),
            )
            execution.compliance_report = compliance_outcome["execution_report"]
            execution.compliance_passed = compliance_outcome["passed"]

            # 11c. Handle compliance actions (retry, approve, escalate)
            if compliance_outcome["action"] is not None:
                execution.compliance_report["compliance_action"] = compliance_outcome["action"]

            blocking = compliance_outcome["blocking_action"]
            if blocking == "retry":
                print(f"  [COMPLIANCE] Retrying {agent_id}: {compliance_outcome['reason']}")
                execution.compliance_report["retry_feedback"] = compliance_outcome["feedback"]
                execution.status = "needs_retry"
                execution.error = compliance_outcome["reason"]
                execution.completed_at = datetime.now().isoformat()
                return execution
            elif blocking == "escalate":
                print(f"  [COMPLIANCE] Escalating {agent_id}: {compliance_outcome['reason']}")
                execution.status = "escalated"
                execution.error = compliance_outcome["reason"]
                execution.completed_at = datetime.now().isoformat()
                return execution
            elif blocking == "approve":
                print(f"  [COMPLIANCE] Requires approval for {agent_id}: {compliance_outcome['reason']}")

            # 11d. Fix review gate: the reviewer (code-review) agent must approve a fix.
            if agent_id == "fix" and self._fix_review_enabled():
                self._review_fix(execution, stage_id, artifacts)
                if execution.status == "needs_retry":
                    execution.completed_at = datetime.now().isoformat()
                    return execution

            # 12. Run design critic for design stage
            if stage_id == "design":
                try:
                    from core.design_critic import critique_design, critique_to_dict
                    for art_path in artifacts:
                        if art_path.endswith(".md"):
                            with open(art_path, "r", encoding="utf-8") as f:
                                art_content = f.read()
                            critique = critique_design(art_content, art_path)
                            if not critique.passed:
                                execution.compliance_report["design_critic"] = critique_to_dict(critique)
                except Exception:
                    pass
            
            # 13. Run visual QA for implement stage
            if stage_id == "implement":
                try:
                    from core.visual_qa import run_visual_qa, qa_to_dict
                    for art_path in artifacts:
                        if art_path.endswith(".html"):
                            with open(art_path, "r", encoding="utf-8") as f:
                                html_content = f.read()
                            qa = run_visual_qa(html_content, art_path)
                            if not qa.passed:
                                execution.compliance_report["visual_qa"] = qa_to_dict(qa)
                except Exception:
                    pass
            
            # 14. Track issues for security/NFR/test stages
            if stage_id == "security":
                self._track_security_issues(agent_id, artifacts)
            elif stage_id in ["nfr", "tests"]:
                self._track_test_issues(agent_id, stage_id, artifacts)
            
            # 15. Record circuit breaker success
            self.circuit_breakers.record_success(cb_name)
            
            # 16. Store completion memory
            self.store_memory(
                memory_type="episodic",
                content=f"Agent {agent_id} completed stage {stage_id}. Artifacts: {len(artifacts)} | Cost: ${estimated_cost:.4f} | Model: {selected_model}",
                source=agent_id,
                confidence=0.9,
                tags=[stage_id, agent_id, "completed"]
            )
            
            # 17. Human-in-the-Loop approval check (full decision model, BI-0093)
            if int(getattr(self, "_hil_rerun_depth", 0)) > 0:
                # Nested amend/regenerate re-run: the parent loop owns the approval ask.
                hil = {"outcome": "approved", "notes": "", "conditions": ""}
            else:
                hil = self._apply_hil_decision(agent_id, stage_id, task, artifacts, execution)

            hil_outcome = hil.get("outcome")
            if hil_outcome == "rejected":
                execution.status = "rejected"
                execution.error = "Human rejected agent output"
                execution.completed_at = datetime.now().isoformat()
                self._log_decision("agent_rejected", f"{agent_id} in stage {stage_id}", "human rejection")
                return execution
            if hil_outcome == "abort":
                self._stop_requested = True
                execution.status = "failed"
                execution.error = "Human aborted the pipeline"
                execution.completed_at = datetime.now().isoformat()
                self._log_decision("agent_aborted", f"{agent_id} in stage {stage_id}", "human abort")
                return execution
            if hil_outcome == "skip":
                execution.status = "skipped"
                execution.error = "Skipped by human"
                execution.completed_at = datetime.now().isoformat()
                self._log_decision("agent_skipped", f"{agent_id} in stage {stage_id}", "human skip")
                return execution
            if hil_outcome == "failed":
                execution.status = "needs_retry"
                execution.error = hil.get("notes") or "not approved after bounded amendments"
                execution.completed_at = datetime.now().isoformat()
                self._log_decision("agent_not_approved", f"{agent_id} in stage {stage_id}",
                                   execution.error)
                return execution
            if hil.get("conditions"):
                if not isinstance(getattr(execution, "compliance_report", None), dict):
                    execution.compliance_report = {}
                execution.compliance_report["approval_conditions"] = hil["conditions"]
                conds = getattr(self, "_approval_conditions", None) or {}
                conds[f"{agent_id}@{stage_id}"] = hil["conditions"]
                self._approval_conditions = conds
            if hil.get("notes"):
                if not isinstance(getattr(execution, "compliance_report", None), dict):
                    execution.compliance_report = {}
                execution.compliance_report.setdefault("approval_notes", hil["notes"])

            execution.status = "completed"
            execution.completed_at = datetime.now().isoformat()
            self._audit_trail_log("agent_complete", agent_id, stage_id)
            # Preserve the real API cost captured from token usage; only fall back
            # to the rough estimate when no usage data was returned.
            if not execution.cost:
                execution.cost = estimated_cost
            
        except Exception as e:
            execution.status = "failed"
            execution.error = str(e)
            execution.completed_at = datetime.now().isoformat()
            self._audit_trail_log("agent_fail", agent_id, stage_id)
            
            # Record circuit breaker failure
            self.circuit_breakers.record_failure(cb_name)
            
            self.store_memory(
                memory_type="failure",
                content=f"Agent {agent_id} failed in stage {stage_id}: {str(e)}",
                source=agent_id,
                confidence=0.95,
                tags=[stage_id, agent_id, "failed"]
            )
        
        return execution
    
    _HIL_MAX_AMENDMENTS = 2

    def _apply_hil_decision(self, agent_id: str, stage_id: str, task: str,
                            artifacts: List[str], execution: "AgentExecution") -> Dict:
        """Drive the HIL decision loop (BI-0093).

        wait -> handle -> (changes/regenerate: re-run with feedback, bounded, re-ask).

        Returns {"outcome": approved|rejected|abort|skip|failed, "notes", "conditions"}.
        Never raises into the stage.
        """
        try:
            amendments = 0
            while True:
                res = self._wait_for_approval_ex(agent_id, stage_id, artifacts)
                decision = str(res.get("decision") or "rejected")
                notes = res.get("notes") or ""
                conditions = res.get("conditions") or ""

                if decision in ("approved", "approved_with_conditions"):
                    return {"outcome": "approved", "notes": notes, "conditions": conditions}
                if decision == "skip":
                    return {"outcome": "skip", "notes": notes}
                if decision == "abort":
                    return {"outcome": "abort", "notes": notes}
                if decision in ("changes", "regenerate"):
                    if amendments >= self._HIL_MAX_AMENDMENTS:
                        return {"outcome": "failed",
                                "notes": f"not approved after {amendments} amendment(s)"}
                    amendments += 1
                    new_task = task
                    if decision == "changes" and notes:
                        new_task = (f"{task}\n\n[HUMAN REVIEW FEEDBACK] {notes}\n"
                                    "Address this feedback and regenerate the output.")
                    self._log_decision("hil_amendment", f"{agent_id} in stage {stage_id}",
                                       f"{decision} (attempt {amendments}): {(notes or '(no notes)')[:120]}")
                    # Layer 1: a HIL amend/regenerate invalidates this agent's cached
                    # INPUT entries so a deliberate regenerate recomputes inputs too.
                    try:
                        ic = getattr(self, "input_cache", None)
                        if ic is not None:
                            ic.clear(agents=[agent_id])
                    except Exception:
                        pass
                    rerun = self._rerun_agent_with_feedback(agent_id, stage_id, new_task)
                    if rerun is None or getattr(rerun, "status", None) != "completed":
                        return {"outcome": "failed",
                                "notes": f"re-run did not complete ({getattr(rerun, 'status', 'error')})"}
                    _merge_execution(execution, rerun)
                    artifacts = rerun.artifacts or artifacts
                    continue
                # rejected / expired / unknown -> rejected
                return {"outcome": "rejected", "notes": notes}
        except Exception as e:
            return {"outcome": "failed", "notes": f"HIL handling error: {e}"}

    def _rerun_agent_with_feedback(self, agent_id: str, stage_id: str, task: str):
        """Re-invoke the agent execution path for an amend/regenerate, depth-guarded
        so the nested run does not itself block on approval."""
        depth = int(getattr(self, "_hil_rerun_depth", 0))
        self._hil_rerun_depth = depth + 1
        try:
            return self.execute_agent(agent_id, stage_id, task)
        finally:
            self._hil_rerun_depth = depth

    def _delegation_signals(self, execution: "AgentExecution") -> List[str]:
        """Delegates to core/orchestrator/delegation_coord (1A.11)."""
        return self.delegation_coord.signals(execution)

    def _maybe_delegate(self, stage_id: str, from_agent: str, execution: "AgentExecution"):
        """Delegates to core/orchestrator/delegation_coord (1A.11)."""
        self.delegation_coord.maybe_delegate(
            stage_id, from_agent, execution, self.execute_agent, self._log_decision)

    def _track_security_issues(self, agent_id: str, artifacts: List[str]):
        """Track security issues from security agent artifacts."""
        for artifact_path in artifacts:
            if artifact_path.endswith(".md"):
                try:
                    with open(artifact_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Parse security issues from content (simplified)
                    issue_id = f"SEC-{len(self.security_issues.issues) + 1:03d}"
                    from core.issue_tracker import create_security_issue
                    issue = create_security_issue(
                        issue_id=issue_id,
                        title=f"Security finding from {agent_id}",
                        description=content[:500] if len(content) > 500 else content,
                        severity="medium",
                        file=artifact_path,
                    )
                    add_issue(self.security_issues, issue)
                except Exception:
                    pass
    
    def _track_test_issues(self, agent_id: str, stage_id: str, artifacts: List[str]):
        """Track test/NFR issues from validate agent artifacts."""
        for artifact_path in artifacts:
            if artifact_path.endswith(".md"):
                try:
                    with open(artifact_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Parse test issues from content (simplified)
                    issue_id = f"TEST-{len(self.test_issues.issues) + 1:03d}"
                    from core.issue_tracker import create_test_issue
                    issue = create_test_issue(
                        issue_id=issue_id,
                        title=f"Test finding from {stage_id}",
                        description=content[:500] if len(content) > 500 else content,
                        severity="medium",
                        test_type=stage_id,
                        file=artifact_path,
                    )
                    add_issue(self.test_issues, issue)
                except Exception:
                    pass
