"""
DAG Executor
Handles DAG-based pipeline execution with parallel, conditional, and swarm patterns.
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime
from enum import Enum
from collections import defaultdict

class StageType(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    SWARM = "swarm"

class StageStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    STALE = "stale"

@dataclass
class StageDefinition:
    stage_id: str
    name: str
    stage_type: StageType
    depends_on: List[str]
    agent: str = ""
    agents: List[Dict] = None  # for swarm
    condition: Dict = None  # for conditional
    config: Dict = None

@dataclass
class StageState:
    stage_id: str
    status: StageStatus
    started_at: str = ""
    completed_at: str = ""
    result: Dict = None
    error: str = ""

class DAGExecutor:
    def __init__(self, pipeline_definition: Dict):
        self.stages: Dict[str, StageDefinition] = {}
        self.states: Dict[str, StageState] = {}
        self._parse_definition(pipeline_definition)
    
    def _parse_definition(self, definition: Dict):
        """Parse pipeline definition into stages."""
        stages = definition.get("stages", {})
        for stage_id, stage_data in stages.items():
            stage_type = StageType(stage_data.get("type", "sequential"))
            # Dependencies may be declared via "depends_on" (canonical) or
            # "runs_after" (used by pipeline-definition.json). Normalise both so
            # the DAG actually sequences dependent stages instead of running all
            # stages in parallel.
            deps = list(stage_data.get("depends_on", []) or [])
            runs_after = stage_data.get("runs_after")
            if runs_after:
                if isinstance(runs_after, str):
                    deps.append(runs_after)
                elif isinstance(runs_after, (list, tuple)):
                    deps.extend(runs_after)
            # De-duplicate while preserving order, and drop self-references
            seen = set()
            depends_on = []
            for dep in deps:
                if dep and dep != stage_id and dep not in seen:
                    seen.add(dep)
                    depends_on.append(dep)

            stage = StageDefinition(
                stage_id=stage_id,
                name=stage_data.get("name", f"Stage {stage_id}"),
                stage_type=stage_type,
                depends_on=depends_on,
                agent=stage_data.get("agent", ""),
                agents=stage_data.get("agents"),
                condition=stage_data.get("condition"),
                config=stage_data.get("config")
            )
            self.stages[stage_id] = stage
            self.states[stage_id] = StageState(
                stage_id=stage_id,
                status=StageStatus.PENDING
            )
    
    def get_ready_stages(self) -> List[str]:
        """Stages ready to run: PENDING/STALE with all dependencies satisfied."""
        ready = []
        for stage_id, stage in self.stages.items():
            if self.states[stage_id].status not in (StageStatus.PENDING, StageStatus.STALE):
                continue
            deps_ok = all(
                self.states[d].status in (StageStatus.COMPLETED, StageStatus.SKIPPED)
                for d in stage.depends_on if d in self.states
            )
            if deps_ok:
                ready.append(stage_id)
        return ready

    def blocked_reasons(self, stage_id: str) -> List[str]:
        """Dependencies preventing this stage from running."""
        st = self.states.get(stage_id)
        if not st or st.status.value not in ("pending", "blocked", "stale"):
            return []
        return [d for d in self.stages[stage_id].depends_on
                if d in self.states and self.states[d].status not in
                (StageStatus.COMPLETED, StageStatus.SKIPPED)]

    def reset_stage(self, stage_id: str):
        """Reset a stage to PENDING (for selective rerun)."""
        if stage_id in self.states:
            s = self.states[stage_id]
            s.status = StageStatus.PENDING
            s.started_at = s.completed_at = ""
            s.result = None
            s.error = ""

    def mark_stale(self, stage_id: str):
        if stage_id in self.states:
            self.states[stage_id].status = StageStatus.STALE

    def _dependents_map(self) -> Dict[str, Set[str]]:
        rev: Dict[str, Set[str]] = defaultdict(set)
        for sid, stage in self.stages.items():
            for dep in stage.depends_on:
                rev[dep].add(sid)
        return rev

    def downstream_of(self, stage_ids: List[str]) -> List[str]:
        """All transitive dependents of the given stages (excludes the seeds)."""
        rev = self._dependents_map()
        seen, queue = set(), list(stage_ids)
        while queue:
            cur = queue.pop()
            for nxt in rev.get(cur, ()):
                if nxt not in seen and nxt not in stage_ids:
                    seen.add(nxt)
                    queue.append(nxt)
        return sorted(seen)

    def invalidate_downstream(self, seed_stages: List[str]) -> List[str]:
        """Mark transitive dependents of the seeds STALE; return their ids."""
        downstream = self.downstream_of(seed_stages)
        for sid in downstream:
            self.mark_stale(sid)
        return downstream

    def restore_states(self, stages: Dict[str, Dict]):
        """Apply persisted stage states (from a checkpoint)."""
        valid = {s.value for s in StageStatus}
        for sid, info in (stages or {}).items():
            if sid not in self.states:
                continue
            st = self.states[sid]
            raw = (info or {}).get("status", "pending")
            if raw == "ready":
                raw = "pending"
            if raw == "blocked":
                raw = "pending"
            if raw in valid:
                st.status = StageStatus(raw)
            st.started_at = (info or {}).get("started_at", "") or ""
            st.completed_at = (info or {}).get("completed_at", "") or ""
            st.error = (info or {}).get("error", "") or ""
    
    def get_parallel_groups(self) -> List[List[str]]:
        """Get groups of stages that can execute in parallel."""
        ready = self.get_ready_stages()
        groups = []
        # Group by dependency level
        for stage_id in ready:
            level = len(self.stages[stage_id].depends_on)
            while len(groups) <= level:
                groups.append([])
            groups[level].append(stage_id)
        return [g for g in groups if g]
    
    def mark_running(self, stage_id: str):
        """Mark a stage as running."""
        self.states[stage_id].status = StageStatus.RUNNING
        self.states[stage_id].started_at = datetime.now().isoformat()
    
    def mark_completed(self, stage_id: str, result: Dict = None):
        """Mark a stage as completed."""
        self.states[stage_id].status = StageStatus.COMPLETED
        self.states[stage_id].completed_at = datetime.now().isoformat()
        self.states[stage_id].result = result
    
    def mark_failed(self, stage_id: str, error: str):
        """Mark a stage as failed."""
        self.states[stage_id].status = StageStatus.FAILED
        self.states[stage_id].error = error
    
    def mark_skipped(self, stage_id: str):
        """Mark a stage as skipped."""
        self.states[stage_id].status = StageStatus.SKIPPED
    
    def evaluate_condition(self, stage_id: str, context: Dict) -> bool:
        """Evaluate conditional stage condition."""
        stage = self.stages.get(stage_id)
        if not stage or not stage.condition:
            return True
        condition_type = stage.condition.get("type", "")
        target = stage.condition.get("target", "")
        value = stage.condition.get("value", "")
        
        if condition_type == "file_exists":
            return os.path.exists(target)
        elif condition_type == "stage_status":
            return self.states.get(target, StageState("", StageStatus.PENDING)).status.value == value
        return True
    
    def get_progress(self) -> Dict:
        """Get pipeline execution progress."""
        total = len(self.states)
        completed = sum(1 for s in self.states.values() if s.status == StageStatus.COMPLETED)
        failed = sum(1 for s in self.states.values() if s.status == StageStatus.FAILED)
        running = sum(1 for s in self.states.values() if s.status == StageStatus.RUNNING)
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": total - completed - failed - running,
            "percent": (completed / total * 100) if total > 0 else 0
        }
    
    def export_state(self) -> Dict:
        """Export current pipeline state."""
        return {
            "stages": {
                sid: {
                    "status": s.status.value,
                    "started_at": s.started_at,
                    "completed_at": s.completed_at,
                    "error": s.error
                }
                for sid, s in self.states.items()
            },
            "progress": self.get_progress()
        }
