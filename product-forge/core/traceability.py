"""
Traceability Matrix
End-to-end mapping: Requirement → Design → Architecture → Implementation → Test → Security
Single source of truth: products/<name>/traceability.json
Human-readable view: products/<name>/architecture/traceability-report.md (auto-generated)
"""

import json
import os
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field
from datetime import datetime

from core import id_index


def _line_at(text: str, pos: int) -> str:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return text[start:end if end != -1 else len(text)]


def _line_title(text: str, pos: int, id_: str) -> str:
    """Best-effort title for an id from its line — format-independent.

    Handles table rows (`| FR-100 | name | … |`), headings/bullets
    (`### FR-100 - name`, `- **FR-100:** name`) and inline `FR-100: name`.
    """
    line = _line_at(text, pos)
    if line.strip().startswith("|"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) > 1 and cells[0].replace("*", "").strip().upper() == id_.upper():
            return cells[1].replace("**", "").strip()
    rest = re.sub(
        r"^[ \t]{0,6}(?:#{1,6}[ \t]+|[-*+][ \t]+|\d+\.[ \t]+)?\**\s*"
        + re.escape(id_) + r"\**\s*[:\-]?\s*",
        "", line, flags=re.IGNORECASE)
    return rest.replace("**", "").strip()


# ── Cross-agent id hub (single writer for traceability.json) ──────────────────
# Every agent may define ids from its DECLARED families (config/spec-id-families.json
# -> emits). This index records, for every declared-family id: which stage/agent/
# artifact defined or referenced it, the run id, and undeclared (invented) prefixes.
# Written as the "id_index" key of traceability.json (owner: this module).

def _hub_run_id(project_dir: str) -> str:
    try:
        from core.audit_trail import current_run_id
        return current_run_id(os.path.basename(project_dir))
    except Exception:
        return ""


def _iter_hub_artifacts(project_dir: str):
    """(stage_id, path, text) for every CANONICAL (.md/.txt) artifact.

    Derived formats (.html/.xlsx/.pdf) are skipped — they are rendered copies and
    would add noise (table chars parsed as ids).
    """
    from core import stage_paths as sp
    for sid, d in sp.iter_stages(project_dir):
        for fn in sorted(os.listdir(d)):
            if fn in ("_stage.json", "INDEX.md") or not fn.endswith((".md", ".txt")):
                continue
            p = os.path.join(d, fn)
            if os.path.isfile(p):
                try:
                    yield sid, p, open(p, encoding="utf-8", errors="ignore").read()
                except Exception:
                    continue


def index_project(project_dir: str, run_id: str = "") -> Dict:
    """(Re)build the cross-agent id hub from every canonical artifact. No LLM."""
    from core import stage_paths as sp
    rid = run_id or _hub_run_id(project_dir)
    ids: Dict[str, Dict] = {}
    by_stage: Dict[str, List[str]] = {}
    undeclared: Dict[str, List[str]] = {}
    declared = id_index.registered_prefixes()

    order = [sid for sid, _d in sp.iter_stages(project_dir)]
    seen = list(_iter_hub_artifacts(project_dir))
    seen.sort(key=lambda x: order.index(x[0]) if x[0] in order else 99)

    for sid, p, t in seen:
        rel = os.path.relpath(p, project_dir)
        for m in id_index.token_re(declared).finditer(t):
            iid = id_index.normalize(m.group(1), m.group(2))
            line = t[t.rfind("\n", 0, m.start()) + 1:t.find("\n", m.start())]
            is_def = line.lstrip().startswith(("|", "#", "-", "*", "1.", "2.", "3."))
            fam = m.group(1).upper()
            if not is_def and len(fam) == 1 and fam != "F":
                continue   # ignore single-letter tokens in prose (noise)
            rec = ids.setdefault(iid, {"family": fam, "stage": sid, "agent": "",
                                       "artifact": rel, "run_id": rid,
                                       "defined": False, "refs": 0})
            rec["refs"] += 1
            if is_def:
                rec["defined"] = True
            by_stage.setdefault(sid, [])
            if iid not in by_stage[sid]:
                by_stage[sid].append(iid)
        for u in id_index.undeclared_ids(t):
            undeclared.setdefault(sid, [])
            if u not in undeclared[sid]:
                undeclared[sid].append(u)

    return {
        "project": os.path.basename(project_dir),
        "generated_at": datetime.now().isoformat(),
        "run_id": rid,
        "ids": ids,
        "by_stage": {k: sorted(v) for k, v in by_stage.items()},
        "undeclared": undeclared,
        "coverage": _hub_coverage(ids),
    }


def _hub_coverage(ids: Dict[str, Dict]) -> Dict:
    def fam(prefixes):
        return {k for k, v in ids.items() if v.get("family") in prefixes}
    must = fam({"M", "KF"})
    feats = fam({"F"})
    reqs = fam({"FR", "NFR", "US"})
    tests = fam({"T", "TC", "V", "OQ"})
    return {
        "counts": {"must_or_kf": len(must), "features": len(feats),
                   "requirements": len(reqs), "tests": len(tests)},
        "must_have_without_feature": sorted(must) if not feats else [],
        "requirements_without_test": sorted(reqs) if not tests else [],
        "features_without_requirement": sorted(feats) if not reqs else [],
    }


def refresh_hub(project_dir: str, run_id: str = "") -> Dict:
    """Write the id hub into traceability.json (preserving the legacy matrix)."""
    hub = index_project(project_dir, run_id=run_id)
    path = os.path.join(project_dir, "traceability.json")
    data = _rj(path, None)
    if not isinstance(data, dict):
        data = {"$schema": "traceability-v1", "project": hub.get("project", ""),
                "matrix": []}
    data["id_index"] = hub
    data["last_updated"] = datetime.now().isoformat()
    _wj(path, data)
    return hub


def get_hub(project_dir: str) -> Optional[Dict]:
    d = _rj(os.path.join(project_dir, "traceability.json"), None)
    return (d or {}).get("id_index") if isinstance(d, dict) else None


def _rj(path: str, default):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def _wj(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@dataclass
class TraceImplementation:
    """Implementation link for a requirement"""
    file: str
    lines: Optional[str] = None
    feature: Optional[str] = None
    agent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TraceImplementation':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TraceTest:
    """Test link for a requirement"""
    name: str
    file: str
    status: str  # passing, failing, pending
    count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TraceTest':
        # Handle both formats: {name, file, status} and {test_file, status, count}
        name = data.get("name", data.get("test_file", ""))
        file = data.get("file", data.get("test_file", ""))
        status = data.get("status", "pending")
        count = data.get("count")
        return cls(name=name, file=file, status=status, count=count)


@dataclass
class TraceCoverage:
    """Coverage status for a requirement"""
    implemented: bool = False
    tested: bool = False
    secured: bool = False
    reviewed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TraceCoverage':
        return cls(**data)


@dataclass
class TraceEntry:
    """Single requirement trace entry"""
    requirement_id: str
    requirement_title: str
    design_sections: List[str] = field(default_factory=list)
    architecture_decisions: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)
    implementations: List[TraceImplementation] = field(default_factory=list)
    tests: List[TraceTest] = field(default_factory=list)
    security_issues: List[str] = field(default_factory=list)
    coverage: TraceCoverage = field(default_factory=TraceCoverage)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "requirement_title": self.requirement_title,
            "design_sections": self.design_sections,
            "architecture_decisions": self.architecture_decisions,
            "features": self.features,
            "implementations": [i.to_dict() for i in self.implementations],
            "tests": [t.to_dict() for t in self.tests],
            "security_issues": self.security_issues,
            "coverage": self.coverage.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TraceEntry':
        impls = [TraceImplementation.from_dict(i) for i in data.get("implementations", [])]
        tests = [TraceTest.from_dict(t) for t in data.get("tests", [])]
        coverage = TraceCoverage.from_dict(data.get("coverage", {}))

        return cls(
            requirement_id=data["requirement_id"],
            requirement_title=data["requirement_title"],
            design_sections=data.get("design_sections", []),
            architecture_decisions=data.get("architecture_decisions", []),
            features=data.get("features", []),
            implementations=impls,
            tests=tests,
            security_issues=data.get("security_issues", []),
            coverage=coverage
        )


@dataclass
class QualityMetric:
    """Quality metrics for a feature"""
    feature_id: str
    test_pass_rate: float = 0.0
    test_count: int = 0
    defect_count: int = 0
    security_findings: int = 0
    code_review_status: str = "pending"
    last_verified: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QualityMetric':
        return cls(**data)


@dataclass
class ImpactAnalysis:
    """Impact analysis for a requirement change"""
    requirement_id: str
    affected_features: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    affected_tests: List[str] = field(default_factory=list)
    dependent_requirements: List[str] = field(default_factory=list)
    risk_level: str = "low"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImpactAnalysis':
        return cls(**data)


@dataclass
class ChangeLog:
    """Change log entry"""
    timestamp: str
    agent: str
    requirement_id: str
    change_type: str
    details: str = ""
    files_added: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChangeLog':
        return cls(**data)


class TraceabilityMatrix:
    """
    End-to-end traceability across requirements, design, architecture,
    implementation, testing, and security.

    Manages products/<name>/traceability.json.
    """

    def __init__(self, project: str, products_dir: str = "products"):
        """
        Initialize for a specific project.

        Args:
            project: Project name
            products_dir: Path to products directory
        """
        self.project = project
        self.products_dir = Path(products_dir)
        self.project_dir = self.products_dir / project
        self.trace_path = self.project_dir / "traceability.json"
        self.trace: Dict[str, Any] = {}
        self._load_or_create()

    def _load_or_create(self):
        """Load existing traceability or create new one"""
        if self.trace_path.exists():
            with open(self.trace_path, 'r', encoding='utf-8') as f:
                self.trace = json.load(f)
        else:
            self.trace = self._create_empty_trace()

    def _create_empty_trace(self) -> Dict[str, Any]:
        """Create empty traceability structure"""
        return {
            "$schema": "traceability-v1",
            "version": "1.0.0",
            "project": self.project,
            "last_updated": datetime.now().isoformat(),
            "matrix": [],
            "coverage_metrics": {
                "total_requirements": 0,
                "implemented": 0,
                "tested": 0,
                "secured": 0,
                "reviewed": 0,
                "percent_implemented": 0.0,
                "percent_tested": 0.0,
                "percent_secured": 0.0,
                "percent_fully_covered": 0.0
            },
            "quality_metrics": {},
            "impact_analysis": {},
            "change_log": []
        }

    def save(self):
        """Atomic write to traceability.json"""
        self.trace["last_updated"] = datetime.now().isoformat()
        self._compute_coverage()

        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.trace_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.trace, f, indent=2, ensure_ascii=False)
            if self.trace_path.exists():
                self.trace_path.unlink()
            temp_path.rename(self.trace_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise Exception(f"Failed to save traceability: {e}")

    def exists(self) -> bool:
        """Check if traceability matrix exists"""
        return self.trace_path.exists()

    # --- Matrix Management ---

    def add_trace(self, requirement_id: str, requirement_title: str) -> TraceEntry:
        """Add a new requirement trace entry"""
        entry = TraceEntry(
            requirement_id=requirement_id,
            requirement_title=requirement_title
        )
        self.trace["matrix"].append(entry.to_dict())
        return entry

    def get_trace(self, requirement_id: str) -> Optional[TraceEntry]:
        """Get trace entry by requirement ID"""
        for entry_data in self.trace["matrix"]:
            if entry_data["requirement_id"] == requirement_id:
                return TraceEntry.from_dict(entry_data)
        return None

    def update_trace(self, requirement_id: str, **kwargs) -> Optional[TraceEntry]:
        """Update trace entry fields"""
        for entry_data in self.trace["matrix"]:
            if entry_data["requirement_id"] == requirement_id:
                for key, value in kwargs.items():
                    if key in entry_data:
                        entry_data[key] = value
                return TraceEntry.from_dict(entry_data)
        return None

    def link_feature(self, requirement_id: str, feature_id: str):
        """Link a feature to a requirement"""
        for entry_data in self.trace["matrix"]:
            if entry_data["requirement_id"] == requirement_id:
                if feature_id not in entry_data["features"]:
                    entry_data["features"].append(feature_id)
                return
        # If no entry exists, create one
        self.add_trace(requirement_id, requirement_id)
        self.link_feature(requirement_id, feature_id)

    def link_architecture(self, requirement_id: str, adr_id: str):
        """Link an architecture decision to a requirement"""
        for entry_data in self.trace["matrix"]:
            if entry_data["requirement_id"] == requirement_id:
                if adr_id not in entry_data["architecture_decisions"]:
                    entry_data["architecture_decisions"].append(adr_id)
                return
        self.add_trace(requirement_id, requirement_id)
        self.link_architecture(requirement_id, adr_id)

    def link_design_section(self, requirement_id: str, section: str):
        """Link a design section to a requirement"""
        for entry_data in self.trace["matrix"]:
            if entry_data["requirement_id"] == requirement_id:
                if section not in entry_data["design_sections"]:
                    entry_data["design_sections"].append(section)
                return
        self.add_trace(requirement_id, requirement_id)
        self.link_design_section(requirement_id, section)

    def link_implementation(self, requirement_id: str, file_path: str,
                            lines: str = None):
        """Link an implementation file to a requirement"""
        impl = TraceImplementation(file=file_path, lines=lines)
        for entry_data in self.trace["matrix"]:
            if entry_data["requirement_id"] == requirement_id:
                # Check if file already linked
                existing = [i["file"] for i in entry_data["implementations"]]
                if file_path not in existing:
                    entry_data["implementations"].append(impl.to_dict())
                return
        self.add_trace(requirement_id, requirement_id)
        self.link_implementation(requirement_id, file_path, lines)

    def link_test(self, requirement_id: str, test_name: str,
                  test_file: str, status: str = "pending"):
        """Link a test to a requirement"""
        test = TraceTest(name=test_name, file=test_file, status=status)
        for entry_data in self.trace["matrix"]:
            if entry_data["requirement_id"] == requirement_id:
                # Check if test already linked
                existing = [t["name"] for t in entry_data["tests"]]
                if test_name not in existing:
                    entry_data["tests"].append(test.to_dict())
                else:
                    # Update status
                    for t in entry_data["tests"]:
                        if t["name"] == test_name:
                            t["status"] = status
                return
        self.add_trace(requirement_id, requirement_id)
        self.link_test(requirement_id, test_name, test_file, status)

    def link_security_issue(self, requirement_id: str, issue_id: str):
        """Link a security issue to a requirement"""
        for entry_data in self.trace["matrix"]:
            if entry_data["requirement_id"] == requirement_id:
                if issue_id not in entry_data["security_issues"]:
                    entry_data["security_issues"].append(issue_id)
                return
        self.add_trace(requirement_id, requirement_id)
        self.link_security_issue(requirement_id, issue_id)

    # --- Coverage Metrics ---

    def _compute_coverage(self):
        """Compute coverage metrics"""
        matrix = self.trace.get("matrix", [])
        total = len(matrix)

        if total == 0:
            self.trace["coverage_metrics"] = {
                "total_requirements": 0,
                "implemented": 0,
                "tested": 0,
                "secured": 0,
                "reviewed": 0,
                "percent_implemented": 0.0,
                "percent_tested": 0.0,
                "percent_secured": 0.0,
                "percent_fully_covered": 0.0
            }
            return

        implemented = 0
        tested = 0
        secured = 0
        reviewed = 0
        fully_covered = 0

        for entry_data in matrix:
            entry = TraceEntry.from_dict(entry_data)
            if entry.implementations:
                implemented += 1
            if entry.tests and all(t.status == "passing" for t in entry.tests):
                tested += 1
            if not entry.security_issues:
                secured += 1
            if entry.coverage.reviewed:
                reviewed += 1
            if (entry.implementations and
                entry.tests and
                all(t.status == "passing" for t in entry.tests) and
                not entry.security_issues):
                fully_covered += 1

        self.trace["coverage_metrics"] = {
            "total_requirements": total,
            "implemented": implemented,
            "tested": tested,
            "secured": secured,
            "reviewed": reviewed,
            "percent_implemented": round(implemented / total * 100, 1),
            "percent_tested": round(tested / total * 100, 1),
            "percent_secured": round(secured / total * 100, 1),
            "percent_fully_covered": round(fully_covered / total * 100, 1)
        }

    def get_coverage(self) -> Dict[str, Any]:
        """Get coverage metrics"""
        self._compute_coverage()
        return self.trace["coverage_metrics"]

    def get_coverage_by_module(self, module_features: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
        """
        Get coverage for a specific module.

        Args:
            module_features: Dict mapping module_id to list of feature_ids
        """
        result = {}
        for module_id, feature_ids in module_features.items():
            total = len(feature_ids)
            if total == 0:
                result[module_id] = {"total": 0, "implemented": 0, "tested": 0, "secured": 0}
                continue

            implemented = 0
            tested = 0
            secured = 0

            for entry_data in self.trace.get("matrix", []):
                entry_features = entry_data.get("features", [])
                if any(f in feature_ids for f in entry_features):
                    if entry_data.get("implementations"):
                        implemented += 1
                    if entry_data.get("tests") and all(
                        t["status"] == "passing" for t in entry_data["tests"]
                    ):
                        tested += 1
                    if not entry_data.get("security_issues"):
                        secured += 1

            result[module_id] = {
                "total": total,
                "implemented": implemented,
                "tested": tested,
                "secured": secured,
                "percent_implemented": round(implemented / total * 100, 1),
                "percent_tested": round(tested / total * 100, 1),
                "percent_secured": round(secured / total * 100, 1)
            }

        return result

    def get_untested_requirements(self) -> List[TraceEntry]:
        """Get requirements with no tests linked"""
        untested = []
        for entry_data in self.trace.get("matrix", []):
            entry = TraceEntry.from_dict(entry_data)
            if not entry.tests:
                untested.append(entry)
        return untested

    def get_unsecured_requirements(self) -> List[TraceEntry]:
        """Get requirements with no security review"""
        unsecured = []
        for entry_data in self.trace.get("matrix", []):
            entry = TraceEntry.from_dict(entry_data)
            if entry.security_issues:
                unsecured.append(entry)
        return unsecured

    # --- Quality Metrics ---

    def update_quality_metric(self, feature_id: str, **metrics):
        """Update quality metrics for a feature"""
        if feature_id not in self.trace["quality_metrics"]:
            self.trace["quality_metrics"][feature_id] = QualityMetric(
                feature_id=feature_id
            ).to_dict()

        for key, value in metrics.items():
            if key in self.trace["quality_metrics"][feature_id]:
                self.trace["quality_metrics"][feature_id][key] = value

        self.trace["quality_metrics"][feature_id]["last_verified"] = datetime.now().isoformat()

    def get_quality_metrics(self, feature_id: str) -> Optional[QualityMetric]:
        """Get quality metrics for a feature"""
        if feature_id in self.trace["quality_metrics"]:
            return QualityMetric.from_dict(self.trace["quality_metrics"][feature_id])
        return None

    def get_quality_summary(self) -> Dict[str, Any]:
        """Get overall quality summary"""
        metrics = self.trace.get("quality_metrics", {})
        if not metrics:
            return {
                "total_features": 0,
                "avg_pass_rate": 0.0,
                "total_defects": 0,
                "total_security_findings": 0,
                "reviewed_count": 0
            }

        total = len(metrics)
        avg_pass_rate = sum(m.get("test_pass_rate", 0) for m in metrics.values()) / total
        total_defects = sum(m.get("defect_count", 0) for m in metrics.values())
        total_security = sum(m.get("security_findings", 0) for m in metrics.values())
        reviewed = sum(1 for m in metrics.values() if m.get("code_review_status") == "approved")

        return {
            "total_features": total,
            "avg_pass_rate": round(avg_pass_rate, 2),
            "total_defects": total_defects,
            "total_security_findings": total_security,
            "reviewed_count": reviewed,
            "review_percent": round(reviewed / total * 100, 1)
        }

    # --- Impact Analysis ---

    def impact_analysis(self, requirement_id: str,
                        requirement_features: Dict[str, List[str]] = None) -> ImpactAnalysis:
        """
        Analyze impact of changing a requirement.

        Args:
            requirement_id: Requirement to analyze
            requirement_features: Optional mapping of requirement to features
        """
        entry = self.get_trace(requirement_id)
        if not entry:
            return ImpactAnalysis(requirement_id=requirement_id)

        affected_features = entry.features.copy()
        affected_files = [i.file for i in entry.implementations]
        affected_tests = [t.name for t in entry.tests]

        # Determine risk level
        risk = "low"
        if len(affected_features) > 3 or len(affected_files) > 5:
            risk = "high"
        elif len(affected_features) > 1 or len(affected_files) > 2:
            risk = "medium"

        # Find dependent requirements (requirements that share features)
        dependent = []
        if requirement_features:
            shared_features = set(affected_features)
            for req_id, features in requirement_features.items():
                if req_id != requirement_id and set(features) & shared_features:
                    dependent.append(req_id)

        analysis = ImpactAnalysis(
            requirement_id=requirement_id,
            affected_features=affected_features,
            affected_files=affected_files,
            affected_tests=affected_tests,
            dependent_requirements=dependent,
            risk_level=risk
        )

        self.trace["impact_analysis"][requirement_id] = analysis.to_dict()
        return analysis

    def get_impact_analysis(self, requirement_id: str) -> Optional[ImpactAnalysis]:
        """Get cached impact analysis"""
        if requirement_id in self.trace["impact_analysis"]:
            return ImpactAnalysis.from_dict(self.trace["impact_analysis"][requirement_id])
        return None

    # --- Change Log ---

    def record_change(self, agent: str, requirement_id: str, change_type: str,
                      details: str = "", files_added: List[str] = None,
                      files_modified: List[str] = None):
        """Record a change"""
        entry = ChangeLog(
            timestamp=datetime.now().isoformat(),
            agent=agent,
            requirement_id=requirement_id,
            change_type=change_type,
            details=details,
            files_added=files_added or [],
            files_modified=files_modified or []
        )
        self.trace["change_log"].append(entry.to_dict())

    def get_change_log(self, requirement_id: str = None,
                       limit: int = 50) -> List[ChangeLog]:
        """Get change log, optionally filtered by requirement"""
        log = self.trace.get("change_log", [])
        if requirement_id:
            log = [e for e in log if e.get("requirement_id") == requirement_id]
        return [ChangeLog.from_dict(e) for e in log[-limit:]]

    # --- Markdown Generation ---

    def generate_markdown(self) -> str:
        """Generate human-readable traceability report as markdown"""
        md = []
        md.append(f"# Traceability Report: {self.project}")
        md.append("")
        md.append("> ⚠️ AUTO-GENERATED — Do not edit directly.")
        md.append("> Source of truth: `traceability.json`")
        md.append("> Regenerated after each pipeline run. Edit the JSON, not this file.")
        md.append("")

        # Coverage Summary
        coverage = self.get_coverage()
        md.append("## Coverage Summary")
        md.append("")
        md.append(f"| Metric | Count | Percent |")
        md.append(f"|--------|-------|---------|")
        md.append(f"| Total Requirements | {coverage['total_requirements']} | - |")
        md.append(f"| Implemented | {coverage['implemented']} | {coverage['percent_implemented']}% |")
        md.append(f"| Tested | {coverage['tested']} | {coverage['percent_tested']}% |")
        md.append(f"| Secured | {coverage['secured']} | {coverage['percent_secured']}% |")
        md.append(f"| Fully Covered | {coverage['implemented']} | {coverage['percent_fully_covered']}% |")
        md.append("")

        # Coverage Bars
        md.append("### Coverage Visual")
        md.append("")
        impl_bar = "█" * int(coverage["percent_implemented"] / 10) + "░" * (10 - int(coverage["percent_implemented"] / 10))
        test_bar = "█" * int(coverage["percent_tested"] / 10) + "░" * (10 - int(coverage["percent_tested"] / 10))
        sec_bar = "█" * int(coverage["percent_secured"] / 10) + "░" * (10 - int(coverage["percent_secured"] / 10))
        md.append(f"- Implemented: {impl_bar} {coverage['percent_implemented']}%")
        md.append(f"- Tested: {test_bar} {coverage['percent_tested']}%")
        md.append(f"- Secured: {sec_bar} {coverage['percent_secured']}%")
        md.append("")

        # Traceability Matrix
        md.append("## Traceability Matrix")
        md.append("")
        md.append("| Requirement | Design | ADR | Feature | Implementation | Tests | Security |")
        md.append("|-------------|--------|-----|---------|----------------|-------|----------|")

        for entry_data in self.trace.get("matrix", []):
            entry = TraceEntry.from_dict(entry_data)
            req = f"{entry.requirement_id}: {entry.requirement_title}"
            design = ", ".join(entry.design_sections) if entry.design_sections else "-"
            adr = ", ".join(entry.architecture_decisions) if entry.architecture_decisions else "-"
            features = ", ".join(entry.features) if entry.features else "-"

            if entry.implementations:
                # Use Path.name to get filename cross-platform
                impl_files = [Path(i.file).name for i in entry.implementations]
                impl = ", ".join(impl_files[:2])
                if len(entry.implementations) > 2:
                    impl += f" (+{len(entry.implementations) - 2})"
            else:
                impl = "-"

            if entry.tests:
                passing = sum(1 for t in entry.tests if t.status == "passing")
                tests = f"{passing}/{len(entry.tests)} ✅" if passing == len(entry.tests) else f"{passing}/{len(entry.tests)}"
            else:
                tests = "-"

            sec = "Clean ✅" if not entry.security_issues else f"{len(entry.security_issues)} issues ⚠️"

            md.append(f"| {req} | {design} | {adr} | {features} | {impl} | {tests} | {sec} |")

        md.append("")

        # Quality Metrics
        quality = self.get_quality_summary()
        if quality["total_features"] > 0:
            md.append("## Quality Metrics")
            md.append("")
            md.append(f"| Metric | Value |")
            md.append(f"|--------|-------|")
            md.append(f"| Features Tracked | {quality['total_features']} |")
            md.append(f"| Avg Test Pass Rate | {quality['avg_pass_rate'] * 100}% |")
            md.append(f"| Total Defects | {quality['total_defects']} |")
            md.append(f"| Security Findings | {quality['total_security_findings']} |")
            md.append(f"| Code Reviews Approved | {quality['reviewed_count']}/{quality['total_features']} |")
            md.append("")

        # Untested Requirements
        untested = self.get_untested_requirements()
        if untested:
            md.append("## ⚠️ Untested Requirements")
            md.append("")
            for entry in untested:
                md.append(f"- {entry.requirement_id}: {entry.requirement_title}")
            md.append("")

        # Change Log
        changes = self.get_change_log(limit=10)
        if changes:
            md.append("## Recent Changes")
            md.append("")
            md.append("| Timestamp | Agent | Requirement | Change Type | Details |")
            md.append("|-----------|-------|-------------|-------------|---------|")
            for change in changes:
                md.append(f"| {change.timestamp} | {change.agent} | {change.requirement_id} | {change.change_type} | {change.details} |")
            md.append("")

        return "\n".join(md)

    def save_markdown(self):
        """Save generated markdown to architecture directory"""
        arch_dir = self.project_dir / "architecture"
        arch_dir.mkdir(parents=True, exist_ok=True)

        md_content = self.generate_markdown()
        md_path = arch_dir / "traceability-report.md"

        temp_path = md_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            if md_path.exists():
                md_path.unlink()
            temp_path.rename(md_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise Exception(f"Failed to save traceability report: {e}")

    # --- Migration ---

    @classmethod
    def migrate_from_markdown(cls, project: str, products_dir: str = "products") -> 'TraceabilityMatrix':
        """Parse existing docs to build initial traceability"""
        trace = cls(project, products_dir)

        project_dir = Path(products_dir) / project
        docs_dir = project_dir / "docs"

        # Parse requirements.md for FR entries — format-independent detection.
        req_path = docs_dir / "requirements.md"
        if req_path.exists():
            content = req_path.read_text(encoding="utf-8", errors="ignore")
            seen: set = set()
            for rid, _p, _n, pos in id_index.iter_ids(content, ["FR"]):
                if rid in seen:
                    continue
                seen.add(rid)
                trace.add_trace(rid, _line_title(content, pos, rid) or rid)

        # Parse architecture.md for ADR entries and link to requirements
        arch_path = docs_dir / "architecture.md"
        if arch_path.exists():
            content = arch_path.read_text(encoding="utf-8", errors="ignore")
            seen_adr: set = set()
            for aid, _p, _n, _pos in id_index.iter_ids(content, ["ADR"]):
                if aid in seen_adr:
                    continue
                seen_adr.add(aid)
                # Link to all existing requirements (basic heuristic)
                for entry_data in trace.trace["matrix"]:
                    trace.link_architecture(entry_data["requirement_id"], aid)

        trace.save()
        return trace
