"""
Agent Ledger - Records all agent work for traceability.

Phase 1.4 (CRITICAL): Audit trail of agent actions.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict, field
from enum import Enum


class WorkStatus(str, Enum):
    """Status of agent work."""
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentWork:
    """A single piece of work done by an agent."""
    id: str
    project: str
    agent: str
    stage: int
    stage_name: str
    action: str
    started_at: str
    completed_at: Optional[str] = None
    status: str = WorkStatus.STARTED.value
    input: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    duration_seconds: Optional[float] = None
    tokens_used: int = 0
    cost_usd: float = 0.0


class AgentLedger:
    """Maintains an immutable record of all agent work."""
    
    LEDGER_FILE = "agent_ledger.jsonl"
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.ledger_file = self.products_dir / ".pipeline" / self.LEDGER_FILE
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        self._work_id_counter = 0
        self._load_existing_ids()
    
    def _load_existing_ids(self) -> None:
        """Load existing work IDs to avoid collisions."""
        if not self.ledger_file.exists():
            return
        
        with open(self.ledger_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    self._work_id_counter += 1
                except json.JSONDecodeError:
                    continue
    
    def _generate_work_id(self, agent: str) -> str:
        """Generate a unique work ID."""
        self._work_id_counter += 1
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"work_{agent}_{timestamp}_{self._work_id_counter:06d}"
    
    def record_work(
        self,
        project: str,
        agent: str,
        stage: int,
        stage_name: str,
        action: str,
        input: Optional[dict] = None,
        output: Optional[dict] = None,
        status: str = WorkStatus.COMPLETED.value,
        error: Optional[str] = None,
        metadata: Optional[dict] = None,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
    ) -> AgentWork:
        """Record a piece of work done by an agent.

        Canonical store: core.agent_ledger (products/ledger/agent_ledger.json) with
        `source="test-framework"`. Falls back to the local JSONL when core is unavailable
        (standalone use).
        """
        work_id = self._generate_work_id(agent)
        now = datetime.utcnow()

        work = AgentWork(
            id=work_id,
            project=project,
            agent=agent,
            stage=stage,
            stage_name=stage_name,
            action=action,
            started_at=now.isoformat(),
            completed_at=now.isoformat(),
            status=status,
            input=input or {},
            output=output or {},
            error=error,
            metadata=metadata or {},
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        )

        # Delegate to the single canonical ledger when available.
        # NB: load core/agent_ledger.py by explicit path -- adding `test-framework` to
        # sys.path makes `core` resolve to THIS package (shadowing), which would recurse.
        try:
            import importlib.util
            from pathlib import Path as _P
            _core_file = _P(__file__).resolve().parents[2] / "core" / "agent_ledger.py"
            if not _core_file.exists():
                raise FileNotFoundError(str(_core_file))
            _spec = importlib.util.spec_from_file_location("_pf_core_agent_ledger", _core_file)
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            core = _mod.AgentLedger(str(self.products_dir))
            core.record_work(
                agent=agent, project=project, stage=stage, action=action,
                files_written=(metadata or {}).get("files_written", []),
                output_produced=output or {}, inputs_used=input or {},
                status=status, error=error, metadata=metadata or {},
                stage_name=stage_name, tokens_used=tokens_used, cost_usd=cost_usd,
                source="test-framework",
                item_id=(metadata or {}).get("item_id", ""),
                feature_id=(metadata or {}).get("feature_id", ""),
            )
            return work
        except Exception:
            pass

        # Fallback (standalone test-framework without core on path): local JSONL.
        with open(self.ledger_file, "a") as f:
            f.write(json.dumps(asdict(work)) + "\n")

        return work
    
    def get_work_by_id(self, work_id: str) -> Optional[AgentWork]:
        """Get a work entry by ID."""
        if not self.ledger_file.exists():
            return None
        
        with open(self.ledger_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("id") == work_id:
                        return AgentWork(**entry)
                except (json.JSONDecodeError, OSError, TypeError):
                    continue
        
        return None
    
    def get_work_by_agent(self, agent: str, limit: Optional[int] = None) -> list[AgentWork]:
        """Get all work for a specific agent."""
        works = []
        
        if not self.ledger_file.exists():
            return works
        
        with open(self.ledger_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("agent") == agent:
                        works.append(AgentWork(**entry))
                except (json.JSONDecodeError, OSError, TypeError):
                    continue
        
        if limit:
            works = works[-limit:]
        
        return works
    
    def get_work_by_project(self, project: str, limit: Optional[int] = None) -> list[AgentWork]:
        """Get all work for a specific project."""
        works = []
        
        if not self.ledger_file.exists():
            return works
        
        with open(self.ledger_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("project") == project:
                        works.append(AgentWork(**entry))
                except (json.JSONDecodeError, OSError, TypeError):
                    continue
        
        if limit:
            works = works[-limit:]
        
        return works
    
    def get_work_by_stage(self, project: str, stage: int) -> list[AgentWork]:
        """Get all work for a specific stage of a project."""
        works = []
        
        if not self.ledger_file.exists():
            return works
        
        with open(self.ledger_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("project") == project and entry.get("stage") == stage:
                        works.append(AgentWork(**entry))
                except (json.JSONDecodeError, OSError, TypeError):
                    continue
        
        return works
    
    def get_work_by_status(self, status: str) -> list[AgentWork]:
        """Get all work with a specific status."""
        works = []
        
        if not self.ledger_file.exists():
            return works
        
        with open(self.ledger_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("status") == status:
                        works.append(AgentWork(**entry))
                except (json.JSONDecodeError, OSError, TypeError):
                    continue
        
        return works
    
    def get_agent_summary(self, agent: str) -> dict:
        """Get summary statistics for an agent."""
        works = self.get_work_by_agent(agent)
        
        if not works:
            return {"agent": agent, "total_work": 0}
        
        completed = sum(1 for w in works if w.status == WorkStatus.COMPLETED.value)
        failed = sum(1 for w in works if w.status == WorkStatus.FAILED.value)
        total_cost = sum(w.cost_usd for w in works)
        total_tokens = sum(w.tokens_used for w in works)
        
        return {
            "agent": agent,
            "total_work": len(works),
            "completed": completed,
            "failed": failed,
            "success_rate": round(completed / len(works) * 100, 1) if works else 0,
            "total_cost": round(total_cost, 4),
            "total_tokens": total_tokens,
        }
    
    def get_project_summary(self, project: str) -> dict:
        """Get summary statistics for a project."""
        works = self.get_work_by_project(project)
        
        if not works:
            return {"project": project, "total_work": 0}
        
        completed = sum(1 for w in works if w.status == WorkStatus.COMPLETED.value)
        failed = sum(1 for w in works if w.status == WorkStatus.FAILED.value)
        total_cost = sum(w.cost_usd for w in works)
        total_tokens = sum(w.tokens_used for w in works)
        
        stages = sorted({w.stage for w in works})
        agents = sorted({w.agent for w in works})
        
        return {
            "project": project,
            "total_work": len(works),
            "completed": completed,
            "failed": failed,
            "success_rate": round(completed / len(works) * 100, 1) if works else 0,
            "total_cost": round(total_cost, 4),
            "total_tokens": total_tokens,
            "stages_completed": stages,
            "agents_used": agents,
        }
    
    def get_all_agents(self) -> list[str]:
        """Get list of all agents that have done work."""
        agents = set()
        
        if not self.ledger_file.exists():
            return []
        
        with open(self.ledger_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    agents.add(entry.get("agent", "unknown"))
                except json.JSONDecodeError:
                    continue
        
        return sorted(agents)
    
    def get_all_projects(self) -> list[str]:
        """Get list of all projects with work recorded."""
        projects = set()
        
        if not self.ledger_file.exists():
            return []
        
        with open(self.ledger_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    projects.add(entry.get("project", "unknown"))
                except json.JSONDecodeError:
                    continue
        
        return sorted(projects)
    
    def get_recent_work(self, limit: int = 50) -> list[AgentWork]:
        """Get the most recent work entries."""
        works = []
        
        if not self.ledger_file.exists():
            return works
        
        with open(self.ledger_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    works.append(AgentWork(**entry))
                except (json.JSONDecodeError, OSError, TypeError):
                    continue
        
        return works[-limit:]
    
    def get_failed_work(self, limit: Optional[int] = None) -> list[AgentWork]:
        """Get all failed work entries."""
        return self.get_work_by_status(WorkStatus.FAILED.value)[:limit] if limit else self.get_work_by_status(WorkStatus.FAILED.value)
    
    def generate_markdown(self, project: Optional[str] = None) -> str:
        """Generate a markdown report of work."""
        works = self.get_work_by_project(project) if project else self.get_recent_work(1000)
        
        md = f"# Agent Ledger Report\n\n"
        if project:
            md += f"**Project:** {project}\n\n"
        md += f"**Total Entries:** {len(works)}\n\n"
        md += "## Recent Work\n\n"
        md += "| Timestamp | Agent | Stage | Action | Status |\n"
        md += "|-----------|-------|-------|--------|--------|\n"
        
        for work in works[-50:]:
            md += f"| {work.started_at[:19]} | {work.agent} | {work.stage} | {work.action[:40]} | {work.status} |\n"
        
        return md
