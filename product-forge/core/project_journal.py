"""
Project Journal / Live State

Maintains a project-level "done / pending / current state" view during and
after a pipeline run, wiring together:
  - StateMachine  (project lifecycle: idle/running/paused/completed/error)
  - AgentLedger   (what each agent did, with status)
and emitting a human-readable PROJECT-STATUS.md plus a machine-readable
project-status.json.

All operations are best-effort (never raise into the pipeline).
"""
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Any


def _compact_text(text: str, max_chars: int = 0) -> str:
    """Compact markdown: keep all headings + bullets + id-bearing lines; drop prose.

    No hard slice. When ``max_chars`` > 0 and the result is still too long, prose is
    dropped first (then long bullets shortened), so headings/ids/signals survive.
    """
    text = text or ""
    if max_chars and len(text) <= max_chars:
        return text
    lines = text.splitlines()
    keep_head = re.compile(r"^#{1,6}\s")
    keep_bullet = re.compile(r"^\s*[-*+]\s")
    keep_id = re.compile(r"\b(FR|NFR|US|F|KF|M|N|G|ADR|CMP|DM|AC|BR|EC|API|T|V|OQ|IN|BI)-?\d+\b")
    struct = [ln for ln in lines if keep_head.match(ln) or keep_bullet.match(ln) or keep_id.search(ln)]
    out = "\n".join(struct) if struct else text
    if max_chars and len(out) > max_chars:
        # proportional shorten of bullets, never a blind slice of the whole doc
        ratio = max_chars / max(1, len(out))
        out = "\n".join(ln[:max(40, int(len(ln) * ratio))] for ln in out.splitlines())
    if max_chars and len(out) > max_chars:
        out = out[:max_chars].rsplit("\n", 1)[0] + "\n...[compacted]"
    return out


def _read_json(path: str) -> Optional[Any]:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _pipeline_stage_order() -> List[str]:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data = _read_json(os.path.join(root, "pipeline-definition.json")) or {}
    return list((data.get("stages", {}) or {}).keys())


class ProjectJournal:
    def __init__(self, products_dir: str = "products", project: str = "default"):
        self.products_dir = products_dir
        self.project = project
        self.project_dir = os.path.join(products_dir, project)
        self.status_file = os.path.join(self.project_dir, "project-status.json")
        self.status_md = os.path.join(self.project_dir, "PROJECT-STATUS.md")
        self._stage_order = _pipeline_stage_order()
        self._state_machine = None
        self._ledger = None
        try:
            from core.state_machine import StateMachine
            self._state_machine = StateMachine(products_dir)
        except Exception:
            self._state_machine = None
        try:
            from core.agent_ledger import AgentLedger
            self._ledger = AgentLedger(products_dir)
        except Exception:
            self._ledger = None

    # ── lifecycle ────────────────────────────────────────────────
    def start(self, run_id: str = ""):
        try:
            from core.state_machine import ProjectState
            if self._state_machine:
                self._state_machine.transition(self.project, ProjectState.RUNNING,
                                               reason="pipeline start", run_id=run_id)
        except Exception:
            pass

    def finish(self, phase: str = "completed"):
        try:
            from core.state_machine import ProjectState
            target = ProjectState.COMPLETED if phase in ("completed", "completion") else ProjectState.ERROR
            if self._state_machine:
                self._state_machine.transition(self.project, target, reason=f"pipeline {phase}")
        except Exception:
            pass

    # ── work log ─────────────────────────────────────────────────
    def record_agent(self, agent: str, stage: str, status: str, artifacts: List[str],
                     tokens: int = 0, cost: float = 0.0, duration_s: float = 0.0):
        try:
            if not self._ledger:
                return
            idx = self._stage_order.index(stage) if stage in self._stage_order else 0
            self._ledger.record_work(
                agent=agent, project=self.project, stage=idx,
                action=f"execute stage {stage}", files_written=list(artifacts or []),
                output_produced={"tokens": tokens, "cost": cost, "duration_s": duration_s},
                status="completed" if status == "completed" else "failed",
                metadata={"stage_id": stage},
            )
        except Exception:
            pass

    # ── status doc ───────────────────────────────────────────────
    def write_status(self, execution=None):
        try:
            status = self.build_status(execution)
            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump(status, f, indent=2, ensure_ascii=False)
            with open(self.status_md, "w", encoding="utf-8") as f:
                f.write(self.render_markdown(status))
            return status
        except Exception:
            return None

    def build_status(self, execution=None) -> Dict:
        report = _read_json(os.path.join(self.project_dir, "pipeline-execution-report.json")) or {}
        stage_summary = report.get("stage_summary", {}) or {}
        stage_timings = (report.get("timings", {}) or {}).get("stages", {}) or {}

        state = "unknown"
        try:
            if self._state_machine:
                info = self._state_machine.get_state(self.project)
                state = getattr(info, "current_state", None) or getattr(info, "state", "unknown")
                if hasattr(state, "value"):
                    state = state.value
        except Exception:
            pass

        completed = set(stage_summary.keys())
        current = ""
        if execution is not None and getattr(execution, "current_stage", ""):
            current = execution.current_stage
        elif completed:
            # last completed in pipeline order
            done_in_order = [s for s in self._stage_order if s in completed]
            current = done_in_order[-1] if done_in_order else ""

        stages = []
        for sid in self._stage_order:
            sdata = stage_summary.get(sid)
            timing = stage_timings.get(sid, {})
            if sdata:
                st = "completed"
            elif sid == current:
                st = "in_progress"
            else:
                st = "pending"
            stages.append({
                "stage": sid,
                "status": st,
                "agents": [a.get("agent_id") for a in (sdata or {}).get("agents", [])],
                "tokens": (sdata or {}).get("total_tokens", 0),
                "cost": round((sdata or {}).get("total_cost", 0.0), 6),
                "duration_seconds": timing.get("duration_seconds", 0),
            })

        budget = {}
        try:
            from core.pipeline_telemetry import build_telemetry
            tel = build_telemetry(self.project, self.products_dir)
            budget = {
                "used_tokens": tel["totals"]["total_tokens"],
                "used_cost": tel["totals"]["cost"],
                "status": tel["budget"]["status"],
                "soft_cost": tel["budget"]["soft_cost"],
                "hard_cost": tel["budget"]["hard_cost"],
                "variance_percent": tel["budget"]["tolerance_percent"],
                "alerts": tel["alerts"],
            }
        except Exception:
            pass

        done = [s["stage"] for s in stages if s["status"] == "completed"]
        pending = [s["stage"] for s in stages if s["status"] == "pending"]

        return {
            "project": self.project,
            "state": state,
            "pipeline_id": report.get("pipeline_id", ""),
            "phase": report.get("phase", ""),
            "current_stage": current,
            "done_stages": done,
            "pending_stages": pending,
            "total_stages": len(stages),
            "stages": stages,
            "budget": budget,
            "updated_at": datetime.now().isoformat(),
        }

    def render_markdown(self, status: Dict) -> str:
        lines = [f"# PROJECT STATUS — {status['project']}", ""]
        lines.append(f"- **State:** {status['state']}")
        lines.append(f"- **Phase:** {status['phase']}")
        lines.append(f"- **Current stage:** {status['current_stage'] or '-'}")
        lines.append(f"- **Progress:** {len(status['done_stages'])}/{status['total_stages']} stages complete")
        lines.append(f"- **Updated:** {status['updated_at']}")
        lines.append("")
        b = status.get("budget", {})
        if b:
            lines.append("## Budget")
            lines.append(f"- Used tokens: {b.get('used_tokens')}")
            lines.append(f"- Used cost: ${b.get('used_cost')}")
            lines.append(f"- Soft / Hard: ${b.get('soft_cost')} / ${b.get('hard_cost')} (variance {b.get('variance_percent')}%)")
            lines.append(f"- Status: {b.get('status')}")
            lines.append("")
        lines.append("## Stages")
        lines.append("")
        lines.append("| Stage | Status | Agents | Tokens | Cost $ | Time s |")
        lines.append("|---|---|---|---:|---:|---:|")
        icon = {"completed": "done", "in_progress": "in progress", "pending": "pending"}
        for s in status["stages"]:
            lines.append("| {stage} | {status} | {agents} | {tokens} | {cost:.6f} | {dur} |".format(
                stage=s["stage"], status=icon.get(s["status"], s["status"]),
                agents=", ".join(s["agents"]) or "-", tokens=s["tokens"],
                cost=s["cost"], dur=s["duration_seconds"]))
        lines.append("")
        if status.get("pending_stages"):
            lines.append("## Pending")
            lines.append("")
            lines.append("- " + ", ".join(status["pending_stages"]))
            lines.append("")
        return "\n".join(lines)


    def write_agent_context(self, current_stage="", current_agent="", tokens=0,
                            pending=None, files=None):
        """Write docs/agent-context.md (standard checkpoint)."""
        try:
            lines = [
                "# Agent Context",
                "",
                f"- **Current Stage:** {current_stage or '-'}",
                f"- **Current Agent:** {current_agent or '-'}",
                f"- **Tokens Used:** {tokens}",
                f"- **Updated:** {datetime.now().isoformat()}",
                f"- **Pending Tasks:** {', '.join(pending or []) or 'none'}",
                "",
            ]
            if files:
                lines.append("- **Files In Progress:**")
                lines += [f"  - {f}" for f in files]
            path = os.path.join(self.project_dir, "docs", "agent-context.md")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass

    def write_feature_status(self, features, status_map=None):
        """Write docs/feature-status.md (per-feature status)."""
        try:
            status_map = status_map or {}
            lines = ["# Feature Status", "",
                     "| Feature ID | Name | Priority | Status |", "|---|---|---|---|"]
            for f in features or []:
                fid = f.get("id", "")
                lines.append("| {id} | {name} | {prio} | {st} |".format(
                    id=fid, name=f.get("title", ""), prio=f.get("priority", ""),
                    st=status_map.get(fid, "pending")))
            path = os.path.join(self.project_dir, "docs", "feature-status.md")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass

    def write_compact_summary(self, stage_id, text, max_chars=0):
        """Write docs/compact/<stage>-summary.md — a compact (structured) summary.

        No hard cap by default (``max_chars=0`` keeps the full compact). When a budget
        IS given, content is COMPACTED (all headings + key bullets + id lines), never
        blindly sliced, so the essence survives.
        """
        try:
            summary = _compact_text(text or "", max_chars)
            path = os.path.join(self.project_dir, "docs", "compact", f"{stage_id}-summary.md")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(summary)
        except Exception:
            pass

    def get_project_status_placeholder(self):
        return None


def get_project_status(project: str, products_dir: str = "products") -> Dict:
    j = ProjectJournal(products_dir, project)
    # Prefer persisted status if present and fresh; else compute.
    persisted = _read_json(j.status_file)
    if persisted:
        return persisted
    return j.build_status(None)
