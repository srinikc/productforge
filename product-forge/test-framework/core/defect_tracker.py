"""
Defect Tracker - Tracks and manages test defects
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum

class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Status(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    FIXED = "fixed"
    VERIFIED = "verified"
    CLOSED = "closed"
    WONTFIX = "wontfix"

@dataclass
class Defect:
    defect_id: str
    title: str
    description: str
    severity: Severity
    status: Status
    project: str
    test_id: str
    test_name: str
    suite_name: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    fix_agent: Optional[str] = None
    root_cause: Optional[str] = None
    rcca_stage: Optional[str] = None
    rcca_recommendation: Optional[str] = None
    screenshots: Optional[List[str]] = None
    stack_trace: Optional[str] = None
    affected_features: Optional[List[str]] = None
    fix_commit: Optional[str] = None
    verified_at: Optional[datetime] = None
    # Resolution details
    resolution_notes: Optional[str] = None
    fixed_by: Optional[str] = None
    fix_description: Optional[str] = None
    fix_files: Optional[List[str]] = None
    verification_notes: Optional[str] = None
    time_to_fix_minutes: Optional[float] = None
    phase: Optional[str] = None
    stage: Optional[str] = None

class DefectTracker:
    """Tracks and manages test defects"""
    
    def __init__(self, project: str, defects_path: Optional[str] = None):
        self.project = project
        self.defects_path = Path(defects_path or Path(__file__).parent.parent / "defects" / project)
        self.defects_path.mkdir(parents=True, exist_ok=True)
        self.defects_file = self.defects_path / "defects.json"
        self.defects = self._load_defects()
        
    def _load_defects(self) -> List[Defect]:
        """Load defects from file"""
        if not self.defects_file.exists():
            return []
        
        with open(self.defects_file) as f:
            data = json.load(f)
        
        defects = []
        for item in data:
            defects.append(Defect(
                defect_id=item["defect_id"],
                title=item["title"],
                description=item["description"],
                severity=Severity(item["severity"]),
                status=Status(item["status"]),
                project=item["project"],
                test_id=item["test_id"],
                test_name=item["test_name"],
                suite_name=item["suite_name"],
                created_at=datetime.fromisoformat(item["created_at"]),
                updated_at=datetime.fromisoformat(item["updated_at"]) if item.get("updated_at") else None,
                assigned_to=item.get("assigned_to"),
                fix_agent=item.get("fix_agent"),
                root_cause=item.get("root_cause"),
                rcca_stage=item.get("rcca_stage"),
                rcca_recommendation=item.get("rcca_recommendation"),
                screenshots=item.get("screenshots"),
                stack_trace=item.get("stack_trace"),
                affected_features=item.get("affected_features"),
                fix_commit=item.get("fix_commit"),
                verified_at=datetime.fromisoformat(item["verified_at"]) if item.get("verified_at") else None
            ))
        
        return defects
    
    def _save_defects(self):
        """Save defects to file"""
        data = []
        for defect in self.defects:
            item = asdict(defect)
            item["severity"] = defect.severity.value
            item["status"] = defect.status.value
            item["created_at"] = defect.created_at.isoformat()
            if defect.updated_at:
                item["updated_at"] = defect.updated_at.isoformat()
            if defect.verified_at:
                item["verified_at"] = defect.verified_at.isoformat()
            data.append(item)
        
        with open(self.defects_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def log_defect(self, title: str, description: str, severity: Severity,
                   test_id: str, test_name: str, suite_name: str,
                   stack_trace: Optional[str] = None, screenshots: Optional[List[str]] = None,
                   affected_features: Optional[List[str]] = None) -> Defect:
        """Log a new defect"""
        defect_id = f"DEF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(self.defects) + 1:04d}"
        
        defect = Defect(
            defect_id=defect_id,
            title=title,
            description=description,
            severity=severity,
            status=Status.OPEN,
            project=self.project,
            test_id=test_id,
            test_name=test_name,
            suite_name=suite_name,
            created_at=datetime.now(),
            screenshots=screenshots,
            stack_trace=stack_trace,
            affected_features=affected_features
        )
        
        self.defects.append(defect)
        self._save_defects()
        
        return defect
    
    def update_defect(self, defect_id: str, **kwargs) -> Optional[Defect]:
        """Update a defect"""
        defect = self.get_defect(defect_id)
        if not defect:
            return None
        
        for key, value in kwargs.items():
            if hasattr(defect, key):
                if key == "severity":
                    defect.severity = Severity(value)
                elif key == "status":
                    defect.status = Status(value)
                elif key == "updated_at":
                    defect.updated_at = datetime.now()
                else:
                    setattr(defect, key, value)
        
        defect.updated_at = datetime.now()
        self._save_defects()
        
        return defect
    
    def get_defect(self, defect_id: str) -> Optional[Defect]:
        """Get a defect by ID"""
        for defect in self.defects:
            if defect.defect_id == defect_id:
                return defect
        return None
    
    def get_open_defects(self) -> List[Defect]:
        """Get all open defects"""
        return [d for d in self.defects if d.status in [Status.OPEN, Status.IN_PROGRESS]]
    
    def get_defects_by_severity(self, severity: Severity) -> List[Defect]:
        """Get defects by severity"""
        return [d for d in self.defects if d.severity == severity]
    
    def get_defects_for_fix_agent(self) -> List[Defect]:
        """Get defects ordered by severity for fix agent"""
        open_defects = self.get_open_defects()
        
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3
        }
        
        return sorted(open_defects, key=lambda d: severity_order[d.severity])
    
    def get_summary(self) -> Dict[str, Any]:
        """Get defect summary"""
        by_severity = {}
        for severity in Severity:
            by_severity[severity.value] = sum(1 for d in self.defects if d.severity == severity)
        
        by_status = {}
        for status in Status:
            by_status[status.value] = sum(1 for d in self.defects if d.status == status)
        
        return {
            "total": len(self.defects),
            "open": len(self.get_open_defects()),
            "by_severity": by_severity,
            "by_status": by_status
        }
    
    def resolve_defect(self, defect_id: str, fixed_by: str, fix_description: str,
                       resolution_notes: str, fix_files: Optional[List[str]] = None,
                       fix_commit: Optional[str] = None) -> Optional[Defect]:
        """Mark a defect as fixed with resolution details"""
        defect = self.get_defect(defect_id)
        if not defect:
            return None
        
        defect.status = Status.FIXED
        defect.fixed_by = fixed_by
        defect.fix_description = fix_description
        defect.resolution_notes = resolution_notes
        defect.fix_files = fix_files or []
        defect.fix_commit = fix_commit
        defect.updated_at = datetime.now()
        
        # Calculate time to fix
        if defect.created_at:
            delta = datetime.now() - defect.created_at
            defect.time_to_fix_minutes = delta.total_seconds() / 60
        
        self._save_defects()
        return defect
    
    def verify_defect(self, defect_id: str, verification_notes: str) -> Optional[Defect]:
        """Verify a fixed defect"""
        defect = self.get_defect(defect_id)
        if not defect:
            return None
        
        defect.status = Status.VERIFIED
        defect.verification_notes = verification_notes
        defect.verified_at = datetime.now()
        defect.updated_at = datetime.now()
        
        self._save_defects()
        return defect
    
    def close_defect(self, defect_id: str) -> Optional[Defect]:
        """Close a verified defect"""
        defect = self.get_defect(defect_id)
        if not defect:
            return None
        
        defect.status = Status.CLOSED
        defect.updated_at = datetime.now()
        
        self._save_defects()
        return defect
    
    def get_resolved_defects(self) -> List[Defect]:
        """Get all resolved defects (fixed, verified, closed)"""
        return [d for d in self.defects if d.status in [Status.FIXED, Status.VERIFIED, Status.CLOSED]]
    
    def get_resolution_report(self) -> List[Dict[str, Any]]:
        """Get resolution report for all defects"""
        report = []
        for defect in self.defects:
            report.append({
                "defect_id": defect.defect_id,
                "title": defect.title,
                "severity": defect.severity.value,
                "status": defect.status.value,
                "created_at": defect.created_at.isoformat(),
                "fixed_by": defect.fixed_by,
                "fix_description": defect.fix_description,
                "resolution_notes": defect.resolution_notes,
                "fix_files": defect.fix_files,
                "verification_notes": defect.verification_notes,
                "time_to_fix_minutes": defect.time_to_fix_minutes,
                "phase": defect.phase,
                "stage": defect.stage
            })
        return report
