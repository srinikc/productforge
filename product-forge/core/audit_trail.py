"""
Audit Trail - Tracks all agent actions
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

import os
import time
import json
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict, field
from enum import Enum


def current_run_id(project: str) -> str:
    """Best-effort run id for the project (pipeline-state, then lock), else ''."""
    try:
        base = _PF_ROOT / "products" / project
        p = base / "pipeline-state.json"
        if p.exists():
            d = json.load(open(p, encoding="utf-8"))
            rid = d.get("run_id") or d.get("pipeline_id")
            if rid:
                return str(rid)
        # fall back to the active lock's run_id
        try:
            from core.lock_manager import LockManager
            info = LockManager(str(base.parent)).get_lock_info(project)
            if info is not None and getattr(info, "run_id", ""):
                return str(info.run_id)
        except Exception:
            pass
    except Exception:
        pass
    return ""

class AuditAction(Enum):
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"
    AGENT_FAIL = "agent_fail"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    DEFECT_LOG = "defect_log"
    DEFECT_FIX = "defect_fix"
    DEFECT_RESOLVE = "defect_resolve"
    TEST_RUN = "test_run"
    TEST_PASS = "test_pass"
    TEST_FAIL = "test_fail"
    STAGE_START = "stage_start"
    STAGE_COMPLETE = "stage_complete"
    HUMAN_REVIEW = "human_review"
    HUMAN_APPROVE = "human_approve"
    CUSTOM = "custom"

@dataclass
class AuditEntry:
    entry_id: str
    action: str
    agent: str
    stage: int
    details: str
    timestamp: str
    metadata: Dict
    run_id: str = ""

class AuditTrail:
    """Audit trail for all pipeline actions"""
    
    def __init__(self, project: str):
        self.project = project
        self.audit_file = _PF_ROOT / "products" / project / "audit-trail.json"
        self.entries: List[AuditEntry] = self._load_entries()
    
    def _load_entries(self) -> List[AuditEntry]:
        if self.audit_file.exists():
            with open(self.audit_file) as f:
                data = json.load(f)
                out = []
                for e in data:
                    e.setdefault("run_id", "")   # back-compat for pre-linkage entries
                    out.append(AuditEntry(**e))
                return out
        return []
    
    def _save_entries(self):
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.audit_file, 'w') as f:
            json.dump([asdict(e) for e in self.entries], f, indent=2)
    
    def log_action(self, action: AuditAction, agent: str, stage: int, 
                   details: str, metadata: Dict = None) -> AuditEntry:
        """Log an action (stamped with the current run id for attribution)."""
        md = dict(metadata or {})
        rid = md.pop("run_id", "") or current_run_id(self.project)
        entry = AuditEntry(
            entry_id=f"AUD-{len(self.entries)+1:06d}",
            action=action.value,
            agent=agent,
            stage=stage,
            details=details,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            metadata=md,
            run_id=rid
        )
        self.entries.append(entry)
        self._save_entries()
        return entry
    
    def get_entries(self, agent: Optional[str] = None, stage: Optional[int] = None,
                    action: Optional[AuditAction] = None) -> List[AuditEntry]:
        """Get entries with optional filters"""
        filtered = self.entries
        if agent:
            filtered = [e for e in filtered if e.agent == agent]
        if stage is not None:
            filtered = [e for e in filtered if e.stage == stage]
        if action:
            filtered = [e for e in filtered if e.action == action.value]
        return filtered
    
    def get_agent_actions(self, agent: str) -> List[AuditEntry]:
        """Get all actions for an agent"""
        return [e for e in self.entries if e.agent == agent]
    
    def get_stage_actions(self, stage: int) -> List[AuditEntry]:
        """Get all actions for a stage"""
        return [e for e in self.entries if e.stage == stage]
    
    def get_recent(self, count: int = 10) -> List[AuditEntry]:
        """Get recent entries"""
        return self.entries[-count:]
    
    def get_stats(self) -> Dict[str, int]:
        """Get audit statistics"""
        stats = {}
        for entry in self.entries:
            stats[entry.action] = stats.get(entry.action, 0) + 1
        return stats
    
    def get_agent_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics per agent"""
        agent_stats = {}
        for entry in self.entries:
            if entry.agent not in agent_stats:
                agent_stats[entry.agent] = {}
            agent_stats[entry.agent][entry.action] = agent_stats[entry.agent].get(entry.action, 0) + 1
        return agent_stats
