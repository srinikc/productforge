"""
Agent Ledger - Tracks all agent work, contributions, and outcomes.

Provides:
- Per-agent work history (what they did, when, outcome)
- Cross-agent activity timeline
- Summary statistics per agent
- Per-project agent activity view
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentWork:
    """Single work item from an agent"""
    id: str
    agent: str
    project: str
    stage: int
    action: str
    files_written: list[str]
    files_read: list[str]
    inputs_used: dict
    output_produced: dict
    status: str  # in_progress, completed, failed, rollback
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    stage_name: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    source: str = "core"          # core | test-framework | ...
    item_id: str = ""             # work attribution: backlog item (BI-####)
    feature_id: str = ""          # technical attribution (F-x)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent": self.agent,
            "project": self.project,
            "stage": self.stage,
            "stage_name": self.stage_name,
            "action": self.action,
            "files_written": self.files_written,
            "files_read": self.files_read,
            "inputs_used": self.inputs_used,
            "output_produced": self.output_produced,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "metadata": self.metadata,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
            "source": self.source,
            "item_id": self.item_id,
            "feature_id": self.feature_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentWork":
        return cls(
            id=data.get("id", ""),
            agent=data.get("agent", ""),
            project=data.get("project", ""),
            stage=data.get("stage", 0),
            action=data.get("action", ""),
            files_written=data.get("files_written", []),
            files_read=data.get("files_read", []),
            inputs_used=data.get("inputs_used", {}),
            output_produced=data.get("output_produced", {}),
            status=data.get("status", "completed"),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at"),
            duration_seconds=data.get("duration_seconds"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            stage_name=data.get("stage_name", ""),
            tokens_used=data.get("tokens_used", 0),
            cost_usd=data.get("cost_usd", 0.0),
            source=data.get("source", "core"),
            item_id=data.get("item_id", ""),
            feature_id=data.get("feature_id", ""),
        )


class AgentLedger:
    """Tracks all agent work across all projects"""

    def __init__(self, products_dir: str):
        self.products_dir = Path(products_dir)
        self.ledger_dir = self.products_dir / "ledger"
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_file = self.ledger_dir / "agent_ledger.json"

        # Load or create ledger
        if self.ledger_file.exists():
            with open(self.ledger_file) as f:
                self.ledger = json.load(f)
        else:
            self.ledger = {
                "$schema": "agent-ledger-v1",
                "version": "1.0.0",
                "work_items": [],
                "summary": {
                    "total_agents": 0,
                    "total_work_items": 0,
                    "total_files_written": 0,
                    "total_projects": 0,
                },
            }

    def record_work(
        self,
        agent: str,
        project: str,
        stage: int,
        action: str,
        files_written: list[str],
        files_read: list[str] = None,
        inputs_used: dict = None,
        output_produced: dict = None,
        status: str = "completed",
        error: str = None,
        metadata: dict = None,
        stage_name: str = "",
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        source: str = "core",
        item_id: str = "",
        feature_id: str = "",
    ) -> AgentWork:
        """Record a work item from an agent (single canonical ledger)."""
        now = datetime.now(timezone.utc).isoformat()
        work_id = f"{agent}-{project}-{len(self.ledger['work_items']) + 1}"

        work = AgentWork(
            id=work_id,
            agent=agent,
            project=project,
            stage=stage,
            action=action,
            files_written=files_written,
            files_read=files_read or [],
            inputs_used=inputs_used or {},
            output_produced=output_produced or {},
            status=status,
            started_at=now,
            completed_at=now if status in ("completed", "failed") else None,
            error=error,
            metadata=metadata or {},
            stage_name=stage_name,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            source=source,
            item_id=item_id,
            feature_id=feature_id,
        )

        self.ledger["work_items"].append(work.to_dict())
        self._update_summary()
        self._save()

        return work

    def update_work(
        self,
        work_id: str,
        status: str = None,
        error: str = None,
        output_produced: dict = None,
    ):
        """Update an existing work item"""
        for item in self.ledger["work_items"]:
            if item["id"] == work_id:
                if status:
                    item["status"] = status
                if error:
                    item["error"] = error
                if output_produced:
                    item["output_produced"] = output_produced
                if status in ("completed", "failed"):
                    item["completed_at"] = datetime.now(timezone.utc).isoformat()
                    if item["started_at"]:
                        start = datetime.fromisoformat(item["started_at"])
                        end = datetime.fromisoformat(item["completed_at"])
                        item["duration_seconds"] = (end - start).total_seconds()
                break

        self._save()

    def get_work_by_agent(self, agent: str) -> list[dict]:
        """Get all work items for a specific agent"""
        return [w for w in self.ledger["work_items"] if w["agent"] == agent]

    def get_work_by_project(self, project: str) -> list[dict]:
        """Get all work items for a specific project"""
        return [w for w in self.ledger["work_items"] if w["project"] == project]

    def get_work_by_stage(self, stage: int) -> list[dict]:
        """Get all work items for a specific stage"""
        return [w for w in self.ledger["work_items"] if w["stage"] == stage]

    def get_work_by_status(self, status: str) -> list[dict]:
        """Get all work items with a specific status"""
        return [w for w in self.ledger["work_items"] if w["status"] == status]

    def get_agent_summary(self, agent: str) -> dict:
        """Get summary statistics for a specific agent"""
        work = self.get_work_by_agent(agent)
        if not work:
            return {"agent": agent, "total": 0}

        completed = sum(1 for w in work if w["status"] == "completed")
        failed = sum(1 for w in work if w["status"] == "failed")
        in_progress = sum(1 for w in work if w["status"] == "in_progress")

        files_written = set()
        projects = set()
        for w in work:
            files_written.update(w.get("files_written", []))
            projects.add(w.get("project", ""))

        return {
            "agent": agent,
            "total": len(work),
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "files_written": len(files_written),
            "projects": list(projects),
            "success_rate": completed / len(work) if work else 0,
        }

    def get_project_summary(self, project: str) -> dict:
        """Get summary statistics for a specific project"""
        work = self.get_work_by_project(project)
        if not work:
            return {"project": project, "total": 0}

        agents = {}
        for w in work:
            agent = w["agent"]
            if agent not in agents:
                agents[agent] = {"completed": 0, "failed": 0, "total": 0}
            agents[agent]["total"] += 1
            if w["status"] == "completed":
                agents[agent]["completed"] += 1
            elif w["status"] == "failed":
                agents[agent]["failed"] += 1

        return {
            "project": project,
            "total": len(work),
            "agents": agents,
            "stages_completed": len(set(w["stage"] for w in work if w["status"] == "completed")),
        }

    def get_all_agents(self) -> list[str]:
        """Get list of all agents that have done work"""
        return list(set(w["agent"] for w in self.ledger["work_items"]))

    def get_all_projects(self) -> list[str]:
        """Get list of all projects with work"""
        return list(set(w["project"] for w in self.ledger["work_items"]))

    def get_recent_work(self, limit: int = 10) -> list[dict]:
        """Get most recent work items"""
        return self.ledger["work_items"][-limit:]

    def get_failed_work(self) -> list[dict]:
        """Get all failed work items"""
        return self.get_work_by_status("failed")

    def _update_summary(self):
        """Update ledger summary"""
        work = self.ledger["work_items"]
        agents = set(w["agent"] for w in work)
        projects = set(w["project"] for w in work)
        files = set()
        for w in work:
            files.update(w.get("files_written", []))

        self.ledger["summary"] = {
            "total_agents": len(agents),
            "total_work_items": len(work),
            "total_files_written": len(files),
            "total_projects": len(projects),
        }

    def _save(self):
        """Save ledger to disk"""
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ledger_file, "w") as f:
            json.dump(self.ledger, f, indent=2)

    def generate_markdown(self) -> str:
        """Generate markdown view of the agent ledger"""
        summary = self.ledger.get("summary", {})
        work_items = self.ledger.get("work_items", [])

        md = []
        md.append("# Agent Ledger")
        md.append("")
        md.append("> Auto-generated from `ledger/agent_ledger.json`")
        md.append("")

        # Summary
        md.append("## Summary")
        md.append("")
        md.append(f"- **Total Agents**: {summary.get('total_agents', 0)}")
        md.append(f"- **Total Work Items**: {summary.get('total_work_items', 0)}")
        md.append(f"- **Total Files Written**: {summary.get('total_files_written', 0)}")
        md.append(f"- **Total Projects**: {summary.get('total_projects', 0)}")
        md.append("")

        # Per-agent summary
        md.append("## Agent Activity")
        md.append("")
        md.append("| Agent | Total | Completed | Failed | Success Rate | Projects |")
        md.append("|-------|-------|-----------|--------|--------------|----------|")

        for agent in sorted(self.get_all_agents()):
            s = self.get_agent_summary(agent)
            rate = f"{s['success_rate'] * 100:.0f}%" if s['success_rate'] else "0%"
            projects = ", ".join(s['projects'][:3]) if s['projects'] else "-"
            md.append(f"| {agent} | {s['total']} | {s['completed']} | {s['failed']} | {rate} | {projects} |")

        md.append("")

        # Recent work
        md.append("## Recent Work")
        md.append("")
        md.append("| Time | Agent | Project | Action | Status |")
        md.append("|------|-------|---------|--------|--------|")

        for item in work_items[-20:]:
            time_str = item["started_at"][:19] if item.get("started_at") else "-"
            status_icon = {"completed": "✅", "failed": "❌", "in_progress": "🔄"}.get(item["status"], "❓")
            md.append(f"| {time_str} | {item['agent']} | {item['project']} | {item['action']} | {status_icon} |")

        md.append("")

        # Failed work
        failed = self.get_failed_work()
        if failed:
            md.append("## Failed Work")
            md.append("")
            for item in failed:
                md.append(f"- **{item['agent']}** on `{item['project']}`: {item['action']}")
                if item.get("error"):
                    md.append(f"  - Error: {item['error'][:100]}")
            md.append("")

        # File ownership
        md.append("## File Ownership")
        md.append("")
        md.append("| File | Agent | Last Action | Project |")
        md.append("|------|-------|-------------|---------|")

        file_agents = {}
        for item in work_items:
            for f in item.get("files_written", []):
                file_agents[f] = {
                    "agent": item["agent"],
                    "action": item["action"],
                    "project": item["project"],
                }

        for f, info in sorted(file_agents.items()):
            md.append(f"| {f} | {info['agent']} | {info['action'][:40]} | {info['project']} |")

        md.append("")

        return "\n".join(md)
