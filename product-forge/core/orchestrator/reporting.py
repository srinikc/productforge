"""
Reporting (extracted from pipeline_executor - 1A.11).

Generates the final execution report (JSON) and prints the human-readable
summary. Holds the run's reporting inputs explicitly so it doesn't depend on
the executor.
"""
try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import json
import os
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from core.budget_conservation import conservation_state_to_dict


class Reporter:
    def __init__(self, execution, project_dir: str, *,
                 pipeline_start_time: float = 0.0,
                 iteration_count: int = 0,
                 stage_timings: Optional[Dict] = None,
                 agent_timings: Optional[List[Dict]] = None,
                 delegations: Optional[List[Dict]] = None,
                 conservation_state: Any = None,
                 quality_metrics: Any = None,
                 security_issues: Any = None,
                 nfr_issues: Any = None,
                 test_issues: Any = None,
                 budget_manager: Any = None,
                 audit_log: Any = None,
                 cost_kpi: Any = None,
                 feature_health: Any = None,
                 nfr_coverage: Any = None,
                 schema_validation: Any = None,
                 post_deploy: Any = None):
        self.execution = execution
        self.project_dir = project_dir
        self.pipeline_start_time = pipeline_start_time
        self.iteration_count = iteration_count
        self.stage_timings = stage_timings or {}
        self.agent_timings = agent_timings or []
        self.delegations = delegations or []
        self.conservation_state = conservation_state
        self.quality_metrics = quality_metrics
        self.security_issues = security_issues
        self.nfr_issues = nfr_issues
        self.test_issues = test_issues
        self.budget_manager = budget_manager
        self.audit_log = audit_log
        self.cost_kpi = cost_kpi
        self.feature_health = feature_health
        self.nfr_coverage = nfr_coverage
        self.schema_validation = schema_validation
        self.post_deploy = post_deploy

    def generate_final_report(self):
        """Generate final pipeline execution report with all integrated data."""
        if not self.execution:
            return

        total_duration = 0.0
        if self.pipeline_start_time:
            total_duration = round(time.time() - self.pipeline_start_time, 2)

        # Ensure per-agent / per-stage timings are populated (derive if not supplied).
        try:
            if not self.agent_timings and self.execution:
                for sid, execs in self.execution.stage_executions.items():
                    for e in execs:
                        if not getattr(e, "started_at", ""):
                            continue
                        dur = 0.0
                        try:
                            if e.completed_at:
                                dur = (datetime.fromisoformat(e.completed_at)
                                       - datetime.fromisoformat(e.started_at)).total_seconds()
                        except Exception:
                            dur = 0.0
                        self.agent_timings.append({
                            "stage_id": sid, "agent_id": e.agent_id,
                            "started_at": e.started_at, "completed_at": e.completed_at,
                            "duration_seconds": round(dur, 2),
                            "tokens": getattr(e, "total_tokens", 0),
                            "cost": getattr(e, "cost", 0.0),
                            "model": getattr(e, "selected_model", ""),
                        })
            if not self.stage_timings and self.execution:
                for sid, execs in self.execution.stage_executions.items():
                    starts = [e.started_at for e in execs if getattr(e, "started_at", "")]
                    ends = [e.completed_at for e in execs if getattr(e, "completed_at", "")]
                    if starts:
                        dur = 0.0
                        try:
                            dur = (datetime.fromisoformat(max(ends))
                                   - datetime.fromisoformat(min(starts))).total_seconds()
                        except Exception:
                            dur = 0.0
                        self.stage_timings[sid] = {"started_at": min(starts),
                                                   "completed_at": max(ends) if ends else "",
                                                   "duration_seconds": round(dur, 2)}
        except Exception:
            pass

        report = {
            "pipeline_id": self.execution.pipeline_id,
            "project": self.execution.project,
            "phase": self.execution.phase.value,
            "started_at": self.execution.started_at,
            "completed_at": self.execution.completed_at,
            "total_duration_seconds": total_duration,
            "iterations": self.iteration_count,
            "total_tokens": self.execution.total_tokens,
            "total_cost": self.execution.total_cost,
            "timings": {
                "pipeline": {
                    "started_at": self.execution.started_at,
                    "completed_at": self.execution.completed_at,
                    "duration_seconds": total_duration,
                },
                "stages": self.stage_timings,
                "agents": self.agent_timings,
            },
            "stage_summary": {},
            "compliance_summary": {},
            "artifacts": self.execution.artifacts_generated,
            "memory_stats": self.execution.memory_stats,
            "delegations": self.delegations,
            "conservation_state": conservation_state_to_dict(self.conservation_state),
            "quality_metrics": self.quality_metrics.to_dict(),
            "issues": {
                "security": self.security_issues.to_dict(),
                "nfr": self.nfr_issues.to_dict(),
                "test": self.test_issues.to_dict(),
            },
        }

        # Stage summary
        for stage_id, executions in self.execution.stage_executions.items():
            report["stage_summary"][stage_id] = {
                "total_agents": len(executions),
                "completed": sum(1 for e in executions if e.status == "completed"),
                "failed": sum(1 for e in executions if e.status == "failed"),
                "skipped": sum(1 for e in executions if e.status == "skipped"),
                "compliance_passed": sum(1 for e in executions if e.compliance_passed),
                "total_tokens": sum(e.total_tokens for e in executions),
                "total_cost": sum(e.cost for e in executions),
                "agents": [
                    {
                        "agent_id": e.agent_id,
                        "status": e.status,
                        "input_tokens": e.input_tokens,
                        "output_tokens": e.output_tokens,
                        "cached_tokens": e.cached_tokens,
                        "reasoning_tokens": e.reasoning_tokens,
                        "total_tokens": e.total_tokens,
                        "cost": e.cost,
                        "selected_model": e.selected_model,
                        "selected_provider": e.selected_provider,
                        "model_cost_per_1k_input": e.model_cost_per_1k_input,
                        "model_cost_per_1k_output": e.model_cost_per_1k_output,
                    }
                    for e in executions
                ]
            }

        # Compliance summary
        total_agents = sum(len(execs) for execs in self.execution.stage_executions.values())
        passed_agents = sum(
            1 for execs in self.execution.stage_executions.values()
            for e in execs if e.compliance_passed
        )

        report["compliance_summary"] = {
            "total_agents": total_agents,
            "passed": passed_agents,
            "failed": total_agents - passed_agents,
            "pass_rate": (passed_agents / total_agents * 100) if total_agents > 0 else 0
        }

        # Budget summary
        report["budget_summary"] = self.budget_manager.get_total_usage()
        report["budget_statuses"] = self.budget_manager.get_all_statuses()[:20]  # Top 20 budgets
        report["budget_alerts"] = [
            asdict(a) for a in self.budget_manager.get_alerts()
        ]

        # Audit log summary
        report["audit_summary"] = self.audit_log.get_summary()

        # Cost-per-successful-task KPI (if tracked)
        if self.cost_kpi is not None:
            try:
                report["cost_kpi"] = asdict(self.cost_kpi)
            except Exception:
                report["cost_kpi"] = self.cost_kpi

        # Feature-level health (ProductPlan)
        if self.feature_health is not None:
            report["feature_health"] = self.feature_health

        # NFR coverage
        if self.nfr_coverage is not None:
            report["nfr_coverage"] = self.nfr_coverage

        # Schema validation of state files (PART 6)
        if self.schema_validation is not None:
            report["schema_validation"] = self.schema_validation

        # Post-deploy smoke (8.3/8.4)
        if self.post_deploy is not None:
            report["post_deploy"] = self.post_deploy

        # Save report
        report_file = os.path.join(self.project_dir, "pipeline-execution-report.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\nFinal report saved to: {report_file}")

        # Per-agent brief summaries (written at each agent completion) + the canonical
        # final-report.json (same content as the execution report, so it is never empty).
        try:
            from core import agent_summaries as _asum
            report["agent_summaries"] = _asum.read_all(self.project_dir)
        except Exception:
            pass
        try:
            with open(os.path.join(self.project_dir, "final-report.json"), "w",
                      encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        except Exception:
            pass

    def print_summary(self):
        """Print execution summary with all integrated data."""
        if not self.execution:
            return

        print(f"\n{'='*70}")
        print(f"PIPELINE EXECUTION SUMMARY")
        print(f"{'='*70}")
        print(f"Pipeline ID: {self.execution.pipeline_id}")
        print(f"Project: {self.execution.project}")
        print(f"Phase: {self.execution.phase.value}")
        print(f"Started: {self.execution.started_at}")
        print(f"Completed: {self.execution.completed_at}")
        print(f"Iterations: {self.iteration_count}")
        print(f"Total Tokens: {self.execution.total_tokens}")
        print(f"Total Cost: ${self.execution.total_cost:.4f}")
        if self.pipeline_start_time:
            total_duration = time.time() - self.pipeline_start_time
            print(f"Pipeline duration: {total_duration:.1f}s ({total_duration/60:.2f} min)")

        # Stage summary with timings
        print(f"\nStage Summary:")
        for stage_id, executions in self.execution.stage_executions.items():
            completed = sum(1 for e in executions if e.status == "completed")
            skipped = sum(1 for e in executions if e.status == "skipped")
            total = len(executions)
            stage_tokens = sum(e.total_tokens for e in executions)
            stage_cost = sum(e.cost for e in executions)
            timing = self.stage_timings.get(stage_id, {}) if isinstance(self.stage_timings, dict) else {}
            dur = timing.get("duration_seconds", 0)
            print(f"  {stage_id}: {completed}/{total} agents completed, {skipped} skipped, "
                  f"{stage_tokens} tokens, ${stage_cost:.6f}, {dur:.1f}s")

        # Compliance summary (status-based counts, not compliance_passed).
        total_agents = sum(len(execs) for execs in self.execution.stage_executions.values())
        completed_agents = sum(
            1 for execs in self.execution.stage_executions.values()
            for e in execs if e.status in ("completed", "rejected")
        )
        failed_agents = sum(
            1 for execs in self.execution.stage_executions.values()
            for e in execs if e.status in ("failed", "escalated", "needs_retry", "blocked", "stale")
        )
        skipped_agents = sum(
            1 for execs in self.execution.stage_executions.values()
            for e in execs if e.status == "skipped"
        )

        print(f"\nCompliance Summary:")
        print(f"  Total agents: {total_agents}")
        print(f"  Completed: {completed_agents}")
        print(f"  Skipped: {skipped_agents}")
        print(f"  Failed: {failed_agents}")
        print(f"  Completion rate: {completed_agents/total_agents*100:.1f}%" if total_agents > 0 else "  Completion rate: N/A")

        # Artifacts
        print(f"\nArtifacts Generated: {len(self.execution.artifacts_generated)}")
        for artifact in self.execution.artifacts_generated[:10]:
            print(f"  - {artifact}")

        # Per-agent token/cost summary
        print(f"\nPer-Agent Token/Cost Summary:")
        for stage_id, executions in self.execution.stage_executions.items():
            for e in executions:
                if e.status == "completed" and e.total_tokens > 0:
                    print(f"  Stage {stage_id} - {e.agent_id}: {e.total_tokens} tokens, "
                          f"${e.cost:.6f}, {e.selected_model} ({e.selected_provider})")

        # Per-agent timing summary
        print(f"\nPer-Agent Timing Summary:")
        print(f"  {'Stage':<8} {'Agent':<22} {'Start':<26} {'End':<26} {'Time(s)':>8}")
        for t in self.agent_timings:
            print(f"  {t['stage_id']:<8} {t['agent_id']:<22} "
                  f"{str(t.get('started_at','')):<26} {str(t.get('completed_at','')):<26} "
                  f"{t.get('duration_seconds',0):>8.1f}")
        total_agent_time = sum(t.get('duration_seconds', 0) for t in self.agent_timings)
        print(f"  {'-'*90}")
        print(f"  Total agent time: {total_agent_time:.1f}s across {len(self.agent_timings)} agent runs")

        # Audit log summary
        audit_summary = self.audit_log.get_summary()
        print(f"\nAudit Log Summary:")
        print(f"  Total executions: {audit_summary['total_executions']}")
        print(f"  Total tokens: {audit_summary['total_tokens']}")
        print(f"  Total cost: ${audit_summary['total_cost']:.6f}")
        print(f"  Cache hits: {audit_summary['cache_hits']}")
        print(f"  Chunked calls: {audit_summary['chunked_calls']}")
        print(f"  Models used: {', '.join(audit_summary['models_used'])}")

        # Memory stats
        print(f"\nMemory Stats:")
        for key, value in self.execution.memory_stats.items():
            print(f"  {key}: {value}")

        # Budget stats
        budget_total = self.budget_manager.get_total_usage()
        print(f"\nBudget Summary:")
        print(f"  Total tokens used: {budget_total['total_used']}")
        print(f"  Total tokens max: {budget_total['total_max']}")
        print(f"  Total used %: {budget_total['used_percent']:.1f}%")
        print(f"  Active budgets: {budget_total['active_budgets']}")
        if budget_total['alerts'] > 0:
            print(f"  Budget alerts: {budget_total['alerts']}")

        # Conservation mode
        print(f"\nConservation Mode: {self.conservation_state.mode.upper()}")
        if self.conservation_state.skipped_agents:
            print(f"  Skipped Agents: {', '.join(self.conservation_state.skipped_agents)}")
        if self.conservation_state.model_downgrades:
            print(f"  Model Downgrades: {', '.join(self.conservation_state.model_downgrades)}")

        # Issues summary
        print(f"\nIssues Summary:")
        print(f"  Security: {self.security_issues.total_count} (Critical: {self.security_issues.critical_count}, High: {self.security_issues.high_count})")
        print(f"  NFR: {self.nfr_issues.total_count} (Critical: {self.nfr_issues.critical_count}, High: {self.nfr_issues.high_count})")
        print(f"  Tests: {self.test_issues.total_count} (Critical: {self.test_issues.critical_count}, High: {self.test_issues.high_count})")

        # Quality metrics
        print(f"\nQuality Score: {self.quality_metrics.quality_score:.1f}/100")

        # Cost-per-successful-task KPI
        if self.cost_kpi is not None:
            try:
                cp = self.cost_kpi
                print(f"\nCost KPI: ${cp.cost_per_successful_task:.6f}/successful task "
                      f"({cp.successful_tasks}/{cp.total_tasks} ok, total ${cp.total_cost:.6f})")
            except Exception:
                pass

        # Feature health (ProductPlan)
        if self.feature_health:
            try:
                fc = self.feature_health.get("feature_completion", {})
                print(f"Features: {fc.get('completed', 0)}/{fc.get('total', 0)} completed "
                      f"({fc.get('percent_complete', 0):.0f}%), "
                      f"{fc.get('blocked', 0)} blocked, status={self.feature_health.get('overall_status')}")
            except Exception:
                pass

        # NFR coverage
        if self.nfr_coverage:
            try:
                nc = self.nfr_coverage
                print(f"NFR coverage: {nc.get('covered', 0)}/{nc.get('total', 0)} "
                      f"({nc.get('percent', 0):.0f}%)"
                      + (f", missing: {', '.join(nc.get('missing', [])[:5])}" if nc.get('missing') else ""))
                if nc.get("fr_total") is not None:
                    print(f"FR traceability: {nc.get('fr_covered', 0)}/{nc.get('fr_total', 0)} "
                          f"requirements referenced by tests")
            except Exception:
                pass

        # Schema validation (informational)
        if self.schema_validation:
            try:
                bad = {k: v for k, v in self.schema_validation.items()
                       if isinstance(v, dict) and v.get("valid") is False}
                if bad:
                    print(f"Schema validation: {len(bad)} file(s) invalid "
                          f"({', '.join(bad.keys())})")
                else:
                    print("Schema validation: OK")
            except Exception:
                pass

        print(f"\n{'='*70}")

        # QA / Quality section: QIR + Go/No-Go + spec review + console link.
        try:
            from core.qa_manifest import build_manifest
            qa = build_manifest(self.execution.project, self.project_dir)
            try:
                report["qa"] = qa           # present only in generate_final_report
            except NameError:
                pass
            print(f"\nQA / Quality")
            print(f"  Go/No-Go: {qa['go_no_go'].get('decision')}  |  QIR: "
                  f"{qa['qir'].get('number')} ({qa['qir'].get('band')})")
            print(f"  Spec review: blocking={qa['spec_review'].get('blocking_open',0)} "
                  f"optional={qa['spec_review'].get('optional_open',0)}")
            print(f"  Coverage: FR {qa['coverage'].get('fr')} | NFR {qa['coverage'].get('nfr')}")
            print(f"  QA console: {qa['dashboard_url']}")
            print(f"  Static snapshot: {qa.get('snapshot')}")
        except Exception as e:
            print(f"[QA] {e}")

        # Detailed per-agent summary (+ the brief 'what was done' bullets + Decision)
        print(f"\n{'='*70}")
        print(f"PER-AGENT SUMMARY")
        print(f"{'='*70}")
        try:
            import json as _json
            _repo = str(_PF_ROOT)
            _pd = _json.load(open(os.path.join(_repo, "pipeline-definition.json"), encoding="utf-8-sig"))
        except Exception:
            _pd = {}
        try:
            from core.progress import stage_summary as _ss
        except Exception:
            _ss = None
        for stage_id, executions in self.execution.stage_executions.items():
            for e in executions:
                if e.status in ("completed", "skipped"):
                    print(f"  Stage {stage_id} - {e.agent_id}: {e.total_tokens} tokens, "
                          f"${e.cost:.6f} cost, {e.selected_model}, {e.selected_provider}")
                    if _ss is not None:
                        try:
                            for _ln in _ss(_pd, stage_id, e.agent_id, e.status,
                                           getattr(e, "artifacts", []), e.total_tokens, e.cost,
                                           0.0, project_dir=self.project_dir).splitlines():
                                print("    " + _ln)
                        except Exception:
                            pass

        print(f"\n{'='*70}")
