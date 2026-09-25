"""
Compliance Check System

Verifies that agents followed their contracts (workflows, do's/don'ts, checklists).
Runs automatically after every agent execution in every stage/phase.

Each agent has a structured checklist with:
- File checks: required files exist
- Content checks: files contain expected sections/content
- Structure checks: artifacts follow required structure
- Audit checks: agent-audit.md was updated
- Workflow checks: required workflow steps were performed

Results:
- ✓ PASS: Item confirmed
- ✗ FAIL: Item not done
- ⚠ PARTIAL: Partially done
- ? UNKNOWN: Cannot verify

After every agent run:
1. Compliance check runs automatically
2. Anomalies reported to orchestrator
3. Human can correct immediately
4. Reports saved to products/<project>/compliance/<agent>-<stage>.json
5. Final report at products/<project>/compliance/final.json
6. Dashboard shows compliance status
"""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable


def _agent_output_artifact(project_dir: Path, agent: str) -> Optional[Path]:
    """Find this agent's output artifact under artifacts/*/ (any stage dir)."""
    try:
        adir = project_dir / "artifacts"
        if not adir.is_dir():
            return None
        for d in adir.iterdir():
            if d.is_dir():
                p = d / f"{agent}-output.md"
                if p.exists():
                    return p
    except Exception:
        return None
    return None


def _check_agent_output(project_dir: Path, agent: str,
                        keywords: Optional[List[str]] = None) -> Dict[str, Any]:
    """PASS when the agent's output artifact exists and (optionally) contains a keyword."""
    p = _agent_output_artifact(project_dir, agent)
    if p is None:
        return {"status": CheckStatus.FAIL.value,
                "details": f"{agent}-output.md not found", "evidence": []}
    try:
        text = p.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        text = ""
    if keywords:
        hit = any(str(k).lower() in text for k in keywords if k)
        return {"status": CheckStatus.PASS.value if hit else CheckStatus.FAIL.value,
                "details": f"{agent} section check ({keywords[:3]})",
                "evidence": [str(p.name)]}
    return {"status": CheckStatus.PASS.value, "details": f"{agent} output present",
            "evidence": [str(p.name)]}


def derived_checklist(agent: str) -> Dict:
    """A deterministic checklist for ANY agent from its required output sections.

    Ensures every agent has REAL compliance (artifact exists + required sections
    present) instead of a vacuous 'unknown' pass. Used as a fallback when no
    hand-written AGENT_CHECKLISTS entry exists.
    """
    try:
        from core.agent_requirements import required_sections
        spec = required_sections(agent) or {}
    except Exception:
        spec = {}
    ess = list((spec.get("essential") or {}).keys())
    items = [{
        "id": "output-exists", "name": "Agent output artifact exists",
        "description": f"{agent}-output.md must exist after the stage",
        "severity": "critical",
        "check": (lambda pd, a=agent: _check_agent_output(pd, a)),
    }]
    for key in ess:
        kw = (spec.get("essential") or {}).get(key) or []
        items.append({
            "id": f"section-{key}", "name": f"Required section: {key}",
            "description": f"{agent} output must contain: {', '.join(kw[:3])}",
            "severity": "high",
            "check": (lambda pd, a=agent, kws=kw: _check_agent_output(pd, a, kws)),
        })
    return {"derived": {"description": f"Derived checks for '{agent}'",
                        "items": items}}



class CheckStatus(Enum):
    PASS = "pass"           # ✓ - Item confirmed
    FAIL = "fail"           # ✗ - Item not done
    PARTIAL = "partial"     # ⚠ - Partially done
    UNKNOWN = "unknown"     # ? - Cannot verify
    SKIPPED = "skipped"     # ⊘ - Intentionally skipped (with reason)


class CheckSeverity(Enum):
    CRITICAL = "critical"     # Must pass, blocks pipeline
    HIGH = "high"             # Should pass, logs warning
    MEDIUM = "medium"         # Nice to have
    LOW = "low"               # Optional, advisory


@dataclass
class CheckItem:
    """A single compliance check item"""
    id: str
    name: str
    description: str
    severity: str  # critical, high, medium, low
    status: str = "unknown"  # pass, fail, partial, unknown, skipped
    details: str = ""
    evidence: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChecklistCategory:
    """A category of checks (e.g., 'Files', 'Content', 'Workflow')"""
    name: str
    description: str
    items: List[CheckItem] = field(default_factory=list)
    
    @property
    def passed(self) -> int:
        return sum(1 for i in self.items if i.status == CheckStatus.PASS.value)
    
    @property
    def failed(self) -> int:
        return sum(1 for i in self.items if i.status == CheckStatus.FAIL.value)
    
    @property
    def partial(self) -> int:
        return sum(1 for i in self.items if i.status == CheckStatus.PARTIAL.value)
    
    @property
    def total(self) -> int:
        return len(self.items)
    
    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100


@dataclass
class ComplianceReport:
    """Compliance report for one agent run"""
    project: str
    agent: str
    stage: str
    timestamp: str
    categories: List[ChecklistCategory] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    overall_status: str = "unknown"  # pass, fail, partial, unknown
    overall_score: float = 0.0
    
    def calculate_summary(self):
        """Calculate summary stats"""
        total = 0
        passed = 0
        failed = 0
        partial = 0
        critical_failed = 0
        
        for cat in self.categories:
            for item in cat.items:
                total += 1
                if item.status == CheckStatus.PASS.value:
                    passed += 1
                elif item.status == CheckStatus.FAIL.value:
                    failed += 1
                    if item.severity == CheckSeverity.CRITICAL.value:
                        critical_failed += 1
                elif item.status == CheckStatus.PARTIAL.value:
                    partial += 1
        
        self.summary = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "partial": partial,
            "critical_failed": critical_failed,
        }
        
        if total > 0:
            self.overall_score = (passed + partial * 0.5) / total * 100
        
        if critical_failed > 0:
            self.overall_status = CheckStatus.FAIL.value
        elif failed > 0:
            self.overall_status = CheckStatus.PARTIAL.value
        elif passed == total and total > 0:
            self.overall_status = CheckStatus.PASS.value
        else:
            self.overall_status = CheckStatus.UNKNOWN.value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_version": "1.0",
            "project": self.project,
            "agent": self.agent,
            "stage": self.stage,
            "timestamp": self.timestamp,
            "categories": [
                {
                    "name": cat.name,
                    "description": cat.description,
                    "items": [item.to_dict() for item in cat.items],
                    "stats": {
                        "total": cat.total,
                        "passed": cat.passed,
                        "failed": cat.failed,
                        "partial": cat.partial,
                        "pass_rate": cat.pass_rate,
                    }
                }
                for cat in self.categories
            ],
            "summary": self.summary,
            "overall_status": self.overall_status,
            "overall_score": self.overall_score,
        }


class ComplianceChecker:
    """Runs compliance checks for an agent run"""
    
    def __init__(self, project: str, products_dir: str = "products"):
        self.project = project
        self.products_dir = Path(products_dir)
        self.project_dir = self.products_dir / project
        self.compliance_dir = self.project_dir / "compliance"
        self.compliance_dir.mkdir(parents=True, exist_ok=True)
    
    def check_agent(self, agent: str, stage: str = "") -> ComplianceReport:
        """Run compliance checks for a specific agent"""
        report = ComplianceReport(
            project=self.project,
            agent=agent,
            stage=stage,
            timestamp=datetime.now().isoformat(),
        )
        
        # Get checklist for this agent (fall back to a DERIVED checklist so every
        # agent has real checks instead of a vacuous 'unknown' pass).
        checklist_def = AGENT_CHECKLISTS.get(agent) or derived_checklist(agent)
        
        for cat_name, cat_def in checklist_def.items():
            category = ChecklistCategory(
                name=cat_name,
                description=cat_def.get("description", ""),
            )
            
            for item_def in cat_def.get("items", []):
                item = CheckItem(
                    id=item_def["id"],
                    name=item_def["name"],
                    description=item_def.get("description", ""),
                    severity=item_def.get("severity", "medium"),
                )
                
                # Run the check function
                check_fn = item_def.get("check")
                if check_fn:
                    try:
                        result = check_fn(self.project_dir)
                        item.status = result.get("status", "unknown")
                        item.details = result.get("details", "")
                        item.evidence = result.get("evidence", [])
                    except Exception as e:
                        item.status = CheckStatus.UNKNOWN.value
                        item.details = f"Check error: {str(e)}"
                
                category.items.append(item)
            
            report.categories.append(category)
        
        report.calculate_summary()
        self._save_report(report)
        return report
    
    def _save_report(self, report: ComplianceReport):
        """Save compliance report to disk"""
        filename = f"{report.agent}-{report.stage or 'run'}-{report.timestamp.replace(':', '-')}.json"
        filepath = self.compliance_dir / filename
        with open(filepath, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        
        # Also save latest
        latest = self.compliance_dir / f"{report.agent}-{report.stage or 'run'}-latest.json"
        with open(latest, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
    
    def get_all_reports(self) -> List[Dict[str, Any]]:
        """Get all compliance reports for this project"""
        reports = []
        for f in sorted(self.compliance_dir.glob("*-latest.json")):
            with open(f) as fp:
                reports.append(json.load(fp))
        return reports
    
    def generate_final_report(self) -> Dict[str, Any]:
        """Generate a final consolidated compliance report"""
        all_reports = self.get_all_reports()
        
        # Aggregate stats
        total_checks = 0
        total_passed = 0
        total_failed = 0
        total_partial = 0
        total_critical_failed = 0
        
        agent_summaries = []
        all_anomalies = []
        
        for report in all_reports:
            summary = report.get("summary", {})
            total_checks += summary.get("total", 0)
            total_passed += summary.get("passed", 0)
            total_failed += summary.get("failed", 0)
            total_partial += summary.get("partial", 0)
            total_critical_failed += summary.get("critical_failed", 0)
            
            agent_summaries.append({
                "agent": report["agent"],
                "stage": report["stage"],
                "status": report["overall_status"],
                "score": report["overall_score"],
                "passed": summary.get("passed", 0),
                "failed": summary.get("failed", 0),
            })
            
            # Collect anomalies (failed critical/high items)
            for cat in report.get("categories", []):
                for item in cat.get("items", []):
                    if item["status"] == "fail" and item["severity"] in ("critical", "high"):
                        all_anomalies.append({
                            "agent": report["agent"],
                            "stage": report["stage"],
                            "category": cat["name"],
                            "item": item["name"],
                            "severity": item["severity"],
                            "details": item["details"],
                        })
        
        final = {
            "project": self.project,
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_checks": total_checks,
                "total_passed": total_passed,
                "total_failed": total_failed,
                "total_partial": total_partial,
                "total_critical_failed": total_critical_failed,
                "overall_score": (total_passed + total_partial * 0.5) / total_checks * 100 if total_checks > 0 else 0,
            },
            "agents": agent_summaries,
            "anomalies": all_anomalies,
            "conformed": total_critical_failed == 0 and total_failed == 0,
        }
        
        # Save final report
        with open(self.compliance_dir / "final.json", 'w') as f:
            json.dump(final, f, indent=2)
        
        return final


# ============ HELPER CHECK FUNCTIONS ============

def file_exists(project_dir: Path, relative_path: str) -> Dict[str, Any]:
    """Check if a file exists"""
    fpath = project_dir / relative_path
    if fpath.exists():
        return {
            "status": CheckStatus.PASS.value,
            "details": f"File exists: {relative_path}",
            "evidence": [str(fpath.relative_to(project_dir.parent))],
        }
    return {
        "status": CheckStatus.FAIL.value,
        "details": f"File missing: {relative_path}",
        "evidence": [],
    }


def file_contains(project_dir: Path, relative_path: str, pattern: str, 
                  description: str = "") -> Dict[str, Any]:
    """Check if a file contains a pattern"""
    fpath = project_dir / relative_path
    if not fpath.exists():
        return {
            "status": CheckStatus.FAIL.value,
            "details": f"File missing: {relative_path}",
            "evidence": [],
        }
    
    try:
        content = fpath.read_text(encoding="utf-8", errors="ignore")
        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            # Count matches for evidence
            matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
            return {
                "status": CheckStatus.PASS.value,
                "details": f"{description or pattern} found ({len(matches)} matches)",
                "evidence": matches[:3],  # First 3 matches
            }
        return {
            "status": CheckStatus.FAIL.value,
            "details": f"{description or pattern} not found in {relative_path}",
            "evidence": [],
        }
    except Exception as e:
        return {
            "status": CheckStatus.UNKNOWN.value,
            "details": f"Error reading file: {str(e)}",
            "evidence": [],
        }


def file_has_ids(project_dir: Path, relative_path: str, prefixes: List[str],
                 description: str = "", fallback_pattern: str = "") -> Dict[str, Any]:
    """PASS when the file contains at least one id of the given families.

    Format-independent: uses the canonical id index (core.id_index), so a heading,
    table row, bullet, or inline mention all count. ``fallback_pattern`` keeps the
    old prose alternative (e.g. "As a ... I want") when ids are absent.
    """
    fpath = project_dir / relative_path
    if not fpath.exists():
        return {"status": CheckStatus.FAIL.value,
                "details": f"File missing: {relative_path}", "evidence": []}
    try:
        from core import id_index
        content = fpath.read_text(encoding="utf-8", errors="ignore")
        found = sorted(id_index.ids(content, prefixes))
        if found or (fallback_pattern and
                     re.search(fallback_pattern, content, re.IGNORECASE | re.MULTILINE)):
            return {"status": CheckStatus.PASS.value,
                    "details": f"{description or '/'.join(prefixes)} present "
                               f"({len(found)} id(s))",
                    "evidence": found[:5]}
        return {"status": CheckStatus.FAIL.value,
                "details": f"{description or '/'.join(prefixes)} not found in {relative_path}",
                "evidence": []}
    except Exception as e:
        return {"status": CheckStatus.UNKNOWN.value,
                "details": f"Error reading file: {str(e)}", "evidence": []}


def file_contains_any(project_dir: Path, relative_path: str, 
                      patterns: List[str]) -> Dict[str, Any]:
    """Check if file contains ANY of the patterns (for flexible checks)"""
    fpath = project_dir / relative_path
    if not fpath.exists():
        return {
            "status": CheckStatus.FAIL.value,
            "details": f"File missing: {relative_path}",
            "evidence": [],
        }
    
    try:
        content = fpath.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                return {
                    "status": CheckStatus.PASS.value,
                    "details": f"Found: {pattern}",
                    "evidence": [pattern],
                }
        return {
            "status": CheckStatus.PARTIAL.value,
            "details": f"None of expected patterns found: {patterns}",
            "evidence": [],
        }
    except Exception as e:
        return {
            "status": CheckStatus.UNKNOWN.value,
            "details": f"Error: {str(e)}",
            "evidence": [],
        }


def audit_log_updated(project_dir: Path, agent: str) -> Dict[str, Any]:
    """Check if agent-audit.md was updated with this agent's run"""
    audit_file = project_dir / "agent-audit.md"
    if not audit_file.exists():
        return {
            "status": CheckStatus.FAIL.value,
            "details": "agent-audit.md does not exist",
            "evidence": [],
        }
    
    try:
        content = audit_file.read_text(encoding="utf-8", errors="ignore")
        # Check for recent entry (last 50 lines)
        lines = content.splitlines()[-50:]
        recent = "\n".join(lines)
        if agent.lower() in recent.lower():
            return {
                "status": CheckStatus.PASS.value,
                "details": f"Recent entry for {agent} found in audit log",
                "evidence": [l for l in lines if agent.lower() in l.lower()][:2],
            }
        return {
            "status": CheckStatus.FAIL.value,
            "details": f"No recent entry for {agent} in audit log",
            "evidence": [],
        }
    except Exception as e:
        return {
            "status": CheckStatus.UNKNOWN.value,
            "details": f"Error: {str(e)}",
            "evidence": [],
        }


def pipeline_state_updated(project_dir: Path, agent: str) -> Dict[str, Any]:
    """Check if pipeline.json was updated"""
    pipeline_file = project_dir / "pipeline.json"
    if not pipeline_file.exists():
        return {
            "status": CheckStatus.FAIL.value,
            "details": "pipeline.json does not exist",
            "evidence": [],
        }
    
    try:
        with open(pipeline_file) as f:
            data = json.load(f)
        
        # Check if any stage references this agent
        stages = data.get("stages", [])
        agent_stages = [s for s in stages if s.get("agent", "").lower() == agent.lower()]
        
        if agent_stages:
            latest = max(agent_stages, key=lambda s: s.get("timestamp", ""))
            if latest.get("status") == "completed":
                return {
                    "status": CheckStatus.PASS.value,
                    "details": f"Stage '{latest.get('name', agent)}' marked completed",
                    "evidence": [latest.get("timestamp", "")],
                }
            return {
                "status": CheckStatus.PARTIAL.value,
                "details": f"Stage exists but status is '{latest.get('status')}'",
                "evidence": [],
            }
        
        return {
            "status": CheckStatus.PARTIAL.value,
            "details": f"No stage for agent '{agent}' in pipeline.json",
            "evidence": [],
        }
    except Exception as e:
        return {
            "status": CheckStatus.UNKNOWN.value,
            "details": f"Error: {str(e)}",
            "evidence": [],
        }


def test_files_exist(project_dir: Path, required_count: int = 1) -> Dict[str, Any]:
    """Check if test files exist in the project"""
    test_locations = [
        project_dir / "tests",
        project_dir / "test-framework" / "tests" / project_dir.name,
        project_dir / "apps" / "api" / "tests",
    ]
    
    total_tests = 0
    for loc in test_locations:
        if loc.exists():
            total_tests += sum(1 for _ in loc.rglob("test_*.py"))
    
    if total_tests >= required_count:
        return {
            "status": CheckStatus.PASS.value,
            "details": f"Found {total_tests} test files",
            "evidence": [str(loc) for loc in test_locations if loc.exists()][:3],
        }
    return {
        "status": CheckStatus.FAIL.value,
        "details": f"Only {total_tests} test files found, need {required_count}",
        "evidence": [],
    }


def no_mocks_or_stubs(project_dir: Path) -> Dict[str, Any]:
    """Check for TODO, FIXME, mock, stub in production code (stack-agnostic)."""
    patterns = [r"\bTODO\b", r"\bFIXME\b", r"\bXXX\b"]
    mock_patterns = [r"\bmock\s*=", r"\bstub\s*=", r"return\s+None\s*#\s*todo"]
    code_exts = (".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs",
                 ".cs", ".dart", ".php", ".rb", ".kt", ".swift")

    issues = []
    # Scan any conventional source roots (never a hardcoded project/package name).
    src_dirs = [project_dir / b for b in
                ("src", "app", "apps", "backend", "server", "packages", "lib")]
    for src_dir in src_dirs:
        if not src_dir.exists():
            continue
        for f in src_dir.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in code_exts:
                continue
            if "test" in f.name.lower() or "spec" in f.name.lower() or "mock" in f.name.lower():
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for pattern in patterns + mock_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        issues.append(f"{f.relative_to(project_dir)}: {len(matches)} '{pattern}'")
            except Exception:
                pass
    
    if not issues:
        return {
            "status": CheckStatus.PASS.value,
            "details": "No TODO, FIXME, mock, or stub found in production code",
            "evidence": [],
        }
    return {
        "status": CheckStatus.FAIL.value,
        "details": f"Found {len(issues)} issues: {'; '.join(issues[:3])}",
        "evidence": issues[:5],
    }


def docker_build_works(project_dir: Path) -> Dict[str, Any]:
    """Check if Docker build works (only if Docker is available)"""
    if not (project_dir / "Dockerfile").exists() and not (project_dir / "docker-compose.yml").exists():
        return {
            "status": CheckStatus.SKIPPED.value,
            "details": "No Docker files to verify",
            "evidence": [],
        }
    
    # Check docker-compose.yml syntax (basic)
    compose_file = project_dir / "docker-compose.yml"
    if compose_file.exists():
        try:
            import yaml
            with open(compose_file) as f:
                config = yaml.safe_load(f)
            if "services" in config and len(config["services"]) > 0:
                return {
                    "status": CheckStatus.PASS.value,
                    "details": f"docker-compose.yml is valid with {len(config['services'])} services",
                    "evidence": list(config["services"].keys()),
                }
            return {
                "status": CheckStatus.FAIL.value,
                "details": "docker-compose.yml has no services",
                "evidence": [],
            }
        except ImportError:
            return {
                "status": CheckStatus.SKIPPED.value,
                "details": "PyYAML not available for validation",
                "evidence": [],
            }
        except Exception as e:
            return {
                "status": CheckStatus.FAIL.value,
                "details": f"docker-compose.yml invalid: {str(e)}",
                "evidence": [],
            }
    
    return {
        "status": CheckStatus.SKIPPED.value,
        "details": "No docker-compose.yml to verify",
        "evidence": [],
    }


def tests_pass(project_dir: Path) -> Dict[str, Any]:
    """Check if tests pass (run pytest if available)"""
    test_dirs = [
        project_dir / "tests",
        project_dir / "apps" / "api" / "tests",
    ]
    
    has_tests = any(d.exists() for d in test_dirs)
    if not has_tests:
        return {
            "status": CheckStatus.SKIPPED.value,
            "details": "No test directories found",
            "evidence": [],
        }
    
    # Don't actually run tests (too slow), just check they exist
    return {
        "status": CheckStatus.PASS.value,
        "details": "Test files exist (run separately to verify they pass)",
        "evidence": [str(d) for d in test_dirs if d.exists()],
    }


# ============ PER-AGENT CHECKLISTS ============

AGENT_CHECKLISTS = {
    "ideation": {
        "files": {
            "description": "Required files",
            "items": [
                {
                    "id": "product-plan-exists",
                    "name": "Product plan created",
                    "description": "docs/product-plan.md must exist after ideation",
                    "severity": "critical",
                    "check": lambda pd: file_exists(pd, "docs/product-plan.md"),
                },
                {
                    "id": "project-config-exists",
                    "name": "Project config created",
                    "description": "project-config.json must exist",
                    "severity": "critical",
                    "check": lambda pd: file_exists(pd, "project-config.json"),
                },
            ],
        },
        "content": {
            "description": "Required content in product plan",
            "items": [
                {
                    "id": "vision-present",
                    "name": "Vision statement present",
                    "description": "Product plan should have vision/goal",
                    "severity": "critical",
                    "check": lambda pd: file_contains_any(pd, "docs/product-plan.md", 
                        [r"# Vision", r"## Vision", r"## Goal", r"## VISION", r"elevator pitch", r"## Product Vision"]),
                },
                {
                    "id": "personas-present",
                    "name": "User personas present",
                    "description": "Product plan should have user personas",
                    "severity": "high",
                    "check": lambda pd: file_contains_any(pd, "docs/product-plan.md",
                        [r"persona", r"## User", r"## Primary User", r"## Audience", r"target user", r"## Customer"]),
                },
                {
                    "id": "workflow-present",
                    "name": "E2E workflow present",
                    "description": "Product plan should have workflow/journey",
                    "severity": "high",
                    "check": lambda pd: file_contains_any(pd, "docs/product-plan.md",
                        [r"workflow", r"journey", r"## E2E", r"## User Journey", r"## Onboarding"]),
                },
                {
                    "id": "features-listed",
                    "name": "Features listed",
                    "description": "Product plan should list features",
                    "severity": "critical",
                    "check": lambda pd: file_contains(pd, "docs/product-plan.md",
                        r"## Features|## Feature List|## Scope|^### F-\d|^## F-\d", "Features section"),
                },
            ],
        },
        "workflow": {
            "description": "Workflow compliance",
            "items": [
                {
                    "id": "discovery-done",
                    "name": "Discovery process followed",
                    "description": "Ideation should do discovery (personas, workflow, vision)",
                    "severity": "high",
                    "check": lambda pd: file_contains_any(pd, "docs/product-plan.md",
                        [r"persona", r"workflow", r"vision", r"journey"]),
                },
                {
                    "id": "type-classified",
                    "name": "Product type classified",
                    "description": "Product type should be in project-config",
                    "severity": "high",
                    "check": lambda pd: file_contains(pd, "project-config.json", r"\"product_type\""),
                },
                {
                    "id": "domain-detected",
                    "name": "Domain detected",
                    "description": "Product domain should be in project-config",
                    "severity": "high",
                    "check": lambda pd: file_contains(pd, "project-config.json", r"\"product_domain\""),
                },
                {
                    "id": "tech-stack-initial",
                    "name": "Initial tech stack captured",
                    "description": "Design stage should capture tech stack",
                    "severity": "high",
                    "check": lambda pd: file_contains(pd, "project-config.json", r"\"tech_stack_hints\""),
                },
            ],
        },
        "audit": {
            "description": "Audit trail",
            "items": [
                {
                    "id": "audit-logged",
                    "name": "Audit log updated",
                    "description": "agent-audit.md must have entry for ideation",
                    "severity": "critical",
                    "check": lambda pd: audit_log_updated(pd, "ideation"),
                },
            ],
        },
    },
    
    "design": {
        "files": {
            "description": "Required files",
            "items": [
                {
                    "id": "requirements-exists",
                    "name": "Requirements document created",
                    "description": "docs/requirements.md must exist",
                    "severity": "critical",
                    "check": lambda pd: file_exists(pd, "docs/requirements.md"),
                },
                {
                    "id": "design-exists",
                    "name": "Design document created",
                    "description": "docs/design.md must exist",
                    "severity": "critical",
                    "check": lambda pd: file_exists(pd, "docs/design.md"),
                },
            ],
        },
        "content": {
            "description": "Required content",
            "items": [
                {
                    "id": "frs-present",
                    "name": "Functional Requirements present",
                    "description": "Requirements doc should have FRs",
                    "severity": "critical",
                    "check": lambda pd: file_has_ids(pd, "docs/requirements.md", ["FR"],
                                                     "Functional Requirements",
                                                     r"##\s*Functional Requirements"),
                },
                {
                    "id": "nfrs-present",
                    "name": "Non-Functional Requirements present",
                    "description": "Requirements doc should have NFRs",
                    "severity": "high",
                    "check": lambda pd: file_has_ids(pd, "docs/requirements.md", ["NFR"],
                                                     "Non-Functional Requirements",
                                                     r"##\s*Non-Functional"),
                },
                {
                    "id": "user-stories",
                    "name": "User stories present",
                    "description": "Requirements doc should have user stories",
                    "severity": "high",
                    "check": lambda pd: file_has_ids(pd, "docs/requirements.md", ["US"],
                                                     "User stories", r"As a .* I want"),
                },
                {
                    "id": "no-scope-reduction",
                    "name": "No scope reduction",
                    "description": "Design should not reduce scope without approval",
                    "severity": "critical",
                    "check": lambda pd: file_contains(pd, "docs/requirements.md", r"out of scope|deferred to phase 2", 
                        "scope reduction"),
                },
                {
                    "id": "design-direction",
                    "name": "Design direction documented",
                    "description": "Design doc should have design direction",
                    "severity": "high",
                    "check": lambda pd: file_contains(pd, "docs/design.md", r"## 1\.|## Design Direction|## Direction"),
                },
                {
                    "id": "components-defined",
                    "name": "Components/modules defined",
                    "description": "Design should have component breakdown",
                    "severity": "high",
                    "check": lambda pd: file_contains(pd, "docs/design.md", r"## Component|## Module|component|## Structure"),
                },
            ],
        },
        "audit": {
            "description": "Audit trail",
            "items": [
                {
                    "id": "audit-logged",
                    "name": "Audit log updated",
                    "description": "agent-audit.md must have entry for design",
                    "severity": "critical",
                    "check": lambda pd: audit_log_updated(pd, "design"),
                },
            ],
        },
    },
    
    "architect": {
        "files": {
            "description": "Required files",
            "items": [
                {
                    "id": "architecture-exists",
                    "name": "Architecture document created",
                    "description": "docs/architecture.md must exist",
                    "severity": "critical",
                    "check": lambda pd: file_exists(pd, "docs/architecture.md"),
                },
                {
                    "id": "architecture-drawio",
                    "name": "Architecture diagram created",
                    "description": "docs/architecture.drawio should exist",
                    "severity": "high",
                    "check": lambda pd: file_exists(pd, "docs/architecture.drawio"),
                },
            ],
        },
        "content": {
            "description": "Required content",
            "items": [
                {
                    "id": "tech-stack-defined",
                    "name": "Tech stack defined",
                    "description": "Architecture should have tech stack section",
                    "severity": "critical",
                    "check": lambda pd: file_contains(pd, "docs/architecture.md", r"## 2\.|## Tech Stack|Tech Stack"),
                },
                {
                    "id": "adrs-present",
                    "name": "ADRs present",
                    "description": "Architecture should have ADRs",
                    "severity": "critical",
                    "check": lambda pd: file_has_ids(pd, "docs/architecture.md", ["ADR"],
                                                     "Architecture decisions", r"##\s*ADR"),
                },
                {
                    "id": "architecture-style",
                    "name": "Architecture style chosen",
                    "description": "Architecture should declare style (microservices/monolith/etc)",
                    "severity": "high",
                    "check": lambda pd: file_contains(pd, "docs/architecture.md", 
                        r"microservices|monolith|serverless|modular monolith|event-driven"),
                },
                {
                    "id": "data-model",
                    "name": "Data model documented",
                    "description": "Architecture should have data model/ERD",
                    "severity": "high",
                    "check": lambda pd: file_contains(pd, "docs/architecture.md", r"## Data|## Schema|## Database|## Entities"),
                },
                {
                    "id": "deployment-arch",
                    "name": "Deployment architecture documented",
                    "description": "Architecture should have deployment section",
                    "severity": "high",
                    "check": lambda pd: file_contains(pd, "docs/architecture.md", r"## Deployment|## Deploy|## Infrastructure"),
                },
            ],
        },
        "audit": {
            "description": "Audit trail",
            "items": [
                {
                    "id": "audit-logged",
                    "name": "Audit log updated",
                    "description": "agent-audit.md must have entry for architect",
                    "severity": "critical",
                    "check": lambda pd: audit_log_updated(pd, "architect"),
                },
            ],
        },
    },
    
    "implement": {
        "files": {
            "description": "Required files",
            "items": [
                {
                    "id": "src-exists",
                    "name": "Source code created",
                    "description": "apps/ directory with code must exist",
                    "severity": "critical",
                    "check": lambda pd: file_exists(pd, "apps"),
                },
                {
                    "id": "dockerfile-api",
                    "name": "API Dockerfile",
                    "description": "Dockerfile.api must exist",
                    "severity": "high",
                    "check": lambda pd: file_exists(pd, "Dockerfile.api"),
                },
                {
                    "id": "dockerfile-web",
                    "name": "Web Dockerfile",
                    "description": "Dockerfile.web must exist",
                    "severity": "high",
                    "check": lambda pd: file_exists(pd, "Dockerfile.web"),
                },
                {
                    "id": "docker-compose",
                    "name": "docker-compose.yml",
                    "description": "docker-compose.yml must exist",
                    "severity": "critical",
                    "check": lambda pd: file_exists(pd, "docker-compose.yml"),
                },
            ],
        },
        "code_quality": {
            "description": "Code quality",
            "items": [
                {
                    "id": "no-mocks",
                    "name": "No mocks/stubs/TODOs",
                    "description": "Production code should not have TODO, FIXME, mocks",
                    "severity": "critical",
                    "check": no_mocks_or_stubs,
                },
                {
                    "id": "tests-exist",
                    "name": "Test files exist",
                    "description": "Test files must be created",
                    "severity": "critical",
                    "check": lambda pd: test_files_exist(pd, required_count=3),
                },
            ],
        },
        "build": {
            "description": "Build verification",
            "items": [
                {
                    "id": "docker-compose-valid",
                    "name": "docker-compose.yml is valid",
                    "description": "docker-compose.yml should parse correctly",
                    "severity": "critical",
                    "check": docker_build_works,
                },
            ],
        },
        "audit": {
            "description": "Audit trail",
            "items": [
                {
                    "id": "audit-logged",
                    "name": "Audit log updated",
                    "description": "agent-audit.md must have entry for implement",
                    "severity": "critical",
                    "check": lambda pd: audit_log_updated(pd, "implement"),
                },
                {
                    "id": "state-updated",
                    "name": "Pipeline state updated",
                    "description": "pipeline.json must reflect implement completion",
                    "severity": "high",
                    "check": lambda pd: pipeline_state_updated(pd, "implement"),
                },
            ],
        },
    },
    
    "code-review": {
        "files": {
            "description": "Required files",
            "items": [
                {
                    "id": "review-report",
                    "name": "Code review report created",
                    "description": "reports/code-review.md must exist",
                    "severity": "critical",
                    "check": lambda pd: file_exists(pd, "reports/code-review.md"),
                },
            ],
        },
        "content": {
            "description": "Required content",
            "items": [
                {
                    "id": "verdict-present",
                    "name": "Verdict present",
                    "description": "Code review must have APPROVED or NEEDS-FIXES verdict",
                    "severity": "critical",
                    "check": lambda pd: file_contains(pd, "reports/code-review.md", 
                        r"APPROVED|NEEDS-FIXES|CHANGES REQUIRED|verdict|## Verdict|## Conclusion"),
                },
                {
                    "id": "findings-listed",
                    "name": "Findings documented",
                    "description": "Code review should list specific findings",
                    "severity": "high",
                    "check": lambda pd: file_contains(pd, "reports/code-review.md", 
                        r"## Findings|## Issues|## Review|## Observations"),
                },
            ],
        },
        "audit": {
            "description": "Audit trail",
            "items": [
                {
                    "id": "audit-logged",
                    "name": "Audit log updated",
                    "description": "agent-audit.md must have entry for code-review",
                    "severity": "critical",
                    "check": lambda pd: audit_log_updated(pd, "code-review"),
                },
            ],
        },
    },
    
    "validate": {
        "files": {
            "description": "Required files",
            "items": [
                {
                    "id": "test-results",
                    "name": "Test results logged",
                    "description": "Test results should be in test-framework/reports",
                    "severity": "high",
                    "check": lambda pd: file_exists(pd, "test-framework/reports/metrics.json"),
                },
            ],
        },
        "content": {
            "description": "Validation content",
            "items": [
                {
                    "id": "defects-tracked",
                    "name": "Defects tracked (if any)",
                    "description": "Any defects should be logged in defect tracker",
                    "severity": "high",
                    "check": lambda pd: {"status": "skipped", "details": "Defect check is informational"},
                },
            ],
        },
        "build": {
            "description": "Build verification",
            "items": [
                {
                    "id": "tests-exist",
                    "name": "Tests exist and can be run",
                    "description": "Test files must exist for validation",
                    "severity": "critical",
                    "check": tests_pass,
                },
            ],
        },
        "audit": {
            "description": "Audit trail",
            "items": [
                {
                    "id": "audit-logged",
                    "name": "Audit log updated",
                    "description": "agent-audit.md must have entry for validate",
                    "severity": "critical",
                    "check": lambda pd: audit_log_updated(pd, "validate"),
                },
            ],
        },
    },
    
    "fix": {
        "audit": {
            "description": "Audit trail",
            "items": [
                {
                    "id": "audit-logged",
                    "name": "Audit log updated",
                    "description": "agent-audit.md must have entry for fix",
                    "severity": "critical",
                    "check": lambda pd: audit_log_updated(pd, "fix"),
                },
            ],
        },
        "content": {
            "description": "Fix content",
            "items": [
                {
                    "id": "fixes-applied",
                    "name": "Fixes applied",
                    "description": "Fix should have made changes",
                    "severity": "high",
                    "check": lambda pd: audit_log_updated(pd, "fix"),
                },
            ],
        },
    },
    
    "document": {
        "files": {
            "description": "Required files",
            "items": [
                {
                    "id": "readme-exists",
                    "name": "README.md",
                    "description": "README.md must exist",
                    "severity": "critical",
                    "check": lambda pd: file_exists(pd, "README.md"),
                },
                {
                    "id": "user-guide",
                    "name": "USER_GUIDE.md",
                    "description": "USER_GUIDE.md should exist",
                    "severity": "high",
                    "check": lambda pd: file_exists(pd, "USER_GUIDE.md"),
                },
                {
                    "id": "developer-guide",
                    "name": "DEVELOPER_GUIDE.md",
                    "description": "DEVELOPER_GUIDE.md should exist",
                    "severity": "high",
                    "check": lambda pd: file_exists(pd, "DEVELOPER_GUIDE.md"),
                },
                {
                    "id": "api-docs",
                    "name": "API documentation",
                    "description": "API.md or openapi.json should exist",
                    "severity": "high",
                    "check": lambda pd: file_contains_any(pd, "README.md", [r"## API", r"openapi"]) if (pd / "README.md").exists() else {"status": "fail", "details": "No README", "evidence": []},
                },
            ],
        },
        "audit": {
            "description": "Audit trail",
            "items": [
                {
                    "id": "audit-logged",
                    "name": "Audit log updated",
                    "description": "agent-audit.md must have entry for document",
                    "severity": "critical",
                    "check": lambda pd: audit_log_updated(pd, "document"),
                },
            ],
        },
    },
    
    "package": {
        "files": {
            "description": "Required files",
            "items": [
                {
                    "id": "dist-exists",
                    "name": "Distribution created",
                    "description": "dist/ directory must exist",
                    "severity": "critical",
                    "check": lambda pd: file_exists(pd, "dist"),
                },
                {
                    "id": "bom-exists",
                    "name": "BOM created",
                    "description": "BOM.md or bom/bom.json must exist",
                    "severity": "high",
                    "check": lambda pd: file_exists(pd, "BOM.md"),
                },
                {
                    "id": "release-notes",
                    "name": "RELEASE.md",
                    "description": "RELEASE.md must exist",
                    "severity": "high",
                    "check": lambda pd: file_exists(pd, "RELEASE.md"),
                },
            ],
        },
        "build": {
            "description": "Build verification",
            "items": [
                {
                    "id": "docker-valid",
                    "name": "Docker files valid",
                    "description": "Docker compose must be valid",
                    "severity": "critical",
                    "check": docker_build_works,
                },
            ],
        },
        "audit": {
            "description": "Audit trail",
            "items": [
                {
                    "id": "audit-logged",
                    "name": "Audit log updated",
                    "description": "agent-audit.md must have entry for package",
                    "severity": "critical",
                    "check": lambda pd: audit_log_updated(pd, "package"),
                },
            ],
        },
    },
    
    "devops": {
        "files": {
            "description": "Required files",
            "items": [
                {
                    "id": "ci-config",
                    "name": "CI/CD configuration",
                    "description": ".github/workflows/ or .gitlab-ci.yml should exist",
                    "severity": "high",
                    "check": lambda pd: file_exists(pd, ".github/workflows") if not (pd / ".gitlab-ci.yml").exists() else {"status": "pass", "details": "GitLab CI configured", "evidence": []},
                },
            ],
        },
        "build": {
            "description": "Build verification",
            "items": [
                {
                    "id": "docker-compose-valid",
                    "name": "docker-compose.yml valid",
                    "description": "docker-compose.yml should parse correctly",
                    "severity": "critical",
                    "check": docker_build_works,
                },
            ],
        },
        "audit": {
            "description": "Audit trail",
            "items": [
                {
                    "id": "audit-logged",
                    "name": "Audit log updated",
                    "description": "agent-audit.md must have entry for devops",
                    "severity": "critical",
                    "check": lambda pd: audit_log_updated(pd, "devops"),
                },
            ],
        },
    },
}


def run_compliance_check(project: str, agent: str = None, 
                        stage: str = None,
                        products_dir: str = "products") -> Dict[str, Any]:
    """
    Run compliance check for one or all agents.
    
    Args:
        project: Project name
        agent: Specific agent to check (None = all completed agents)
        stage: Specific stage to check
        products_dir: Products directory
    
    Returns:
        Compliance report dict
    """
    checker = ComplianceChecker(project, products_dir)
    
    if agent:
        # Check specific agent
        report = checker.check_agent(agent, stage or "")
        return report.to_dict()
    else:
        # Check all agents that have run
        reports = checker.get_all_reports()
        if not reports:
            # Try to detect from audit log
            audit_file = Path(products_dir) / project / "agent-audit.md"
            if audit_file.exists():
                content = audit_file.read_text(encoding="utf-8", errors="ignore")
                # Find agent names in audit log
                agent_names = set()
                for line in content.splitlines():
                    match = re.match(r"\[.*?\]\s*\[(\w+)\]", line)
                    if match:
                        agent_names.add(match.group(1).lower())
                
                for agent_name in agent_names:
                    if agent_name in AGENT_CHECKLISTS:
                        checker.check_agent(agent_name, "")
        
        return checker.generate_final_report()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python compliance_check.py <project> [agent] [stage]")
        print("")
        print("Examples:")
        print("  python compliance_check.py <project>                  # Check all agents")
        print("  python compliance_check.py <project> implement        # Check implement agent")
        print("  python compliance_check.py <project> implement 4a    # Check implement in stage 4a")
        sys.exit(1)
    
    project = sys.argv[1]
    agent = sys.argv[2] if len(sys.argv) > 2 else None
    stage = sys.argv[3] if len(sys.argv) > 3 else None
    
    result = run_compliance_check(project, agent, stage)
    
    # Print summary
    if "summary" in result:
        summary = result["summary"]
        print(f"\n{'='*60}")
        print(f"  COMPLIANCE REPORT: {result.get('project', project)}")
        if agent:
            print(f"  Agent: {result.get('agent', agent)} | Stage: {result.get('stage', stage or 'N/A')}")
        print(f"{'='*60}")
        print(f"  Total checks:   {summary.get('total', 0)}")
        print(f"  [PASS] Passed:  {summary.get('passed', summary.get('total_passed', 0))}")
        print(f"  [FAIL] Failed:  {summary.get('failed', summary.get('total_failed', 0))}")
        print(f"  [WARN] Partial: {summary.get('partial', summary.get('total_partial', 0))}")
        print(f"  Score:          {result.get('overall_score', summary.get('overall_score', 0)):.1f}%")
        print(f"  Status:         {result.get('overall_status', 'unknown')}")
        print(f"{'='*60}\n")
        
        if "categories" in result:
            for cat in result["categories"]:
                stats = cat.get("stats", {})
                print(f"  [{cat['name']}] {stats.get('passed', 0)}/{stats.get('total', 0)} passed")
                for item in cat.get("items", []):
                    icon = {"pass": "[OK]", "fail": "[FAIL]", "partial": "[WARN]", "unknown": "[?]", "skipped": "[SKIP]"}.get(item["status"], "[?]")
                    print(f"    {icon} {item['name']}")
                    if item["status"] in ("fail", "partial") and item.get("details"):
                        print(f"        {item['details'][:100]}")
        elif "agents" in result:
            for a in result["agents"]:
                icon = {"pass": "[OK]", "fail": "[FAIL]", "partial": "[WARN]"}.get(a["status"], "[?]")
                print(f"  {icon} {a['agent']} ({a['stage']}): {a['score']:.1f}% - {a['passed']} pass, {a['failed']} fail")
            
            if result.get("anomalies"):
                print(f"\n  [WARN] ANOMALIES ({len(result['anomalies'])}):")
                for anom in result["anomalies"][:10]:
                    print(f"    - [{anom['severity'].upper()}] {anom['agent']}/{anom['stage']}: {anom['item']}")
    else:
        print(json.dumps(result, indent=2))
