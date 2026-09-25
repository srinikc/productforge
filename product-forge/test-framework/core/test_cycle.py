"""
Test Cycle - Tracks complete test cycles across all testing types.

A test cycle groups multiple test runs together:
- Web tests (unit, API, integration, E2E)
- Mobile tests (iOS, Android)
- Security tests
- Performance tests
- Visual regression tests
- etc.

Each test cycle has:
- Unique ID
- Phase/stage reference
- Start/end time
- Results from each testing type
- Overall pass/fail status
- Defects logged
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any


class TestType(Enum):
    UNIT = "unit"
    API = "api"
    INTEGRATION = "integration"
    E2E = "e2e"
    VISUAL = "visual"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MOBILE_IOS = "mobile_ios"
    MOBILE_ANDROID = "mobile_android"
    INSTALL = "install"
    SMOKE = "smoke"
    SANITY = "sanity"


class CycleStatus(Enum):
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class TestRunResult:
    """Result of a single test run within a cycle."""
    test_type: TestType
    framework: str  # vitest, pytest, playwright, stowaway, etc.
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    duration_seconds: float = 0
    status: str = "pending"  # pending, running, passed, failed, error
    error: str = ""
    details: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TestCycle:
    """A complete test cycle across all testing types."""
    cycle_id: str
    project: str
    phase: str  # e.g., "4a", "4b", "4c", "5", "6", "7"
    stage: str  # e.g., "4", "5", "6", "7"
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str = ""
    status: str = "running"  # running, passed, failed, error
    test_runs: List[TestRunResult] = field(default_factory=list)
    defects_logged: int = 0
    defects_fixed: int = 0
    build_version: str = ""
    notes: str = ""

    @property
    def total_tests(self) -> int:
        return sum(r.tests_run for r in self.test_runs)

    @property
    def total_passed(self) -> int:
        return sum(r.tests_passed for r in self.test_runs)

    @property
    def total_failed(self) -> int:
        return sum(r.tests_failed for r in self.test_runs)

    @property
    def overall_status(self) -> str:
        if any(r.status == "failed" for r in self.test_runs):
            return "failed"
        if any(r.status == "error" for r in self.test_runs):
            return "error"
        if all(r.status == "passed" for r in self.test_runs if r.tests_run > 0):
            return "passed"
        return "running"


class TestCycleManager:
    """Manages test cycles for a project."""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.test_framework_dir = self.project_dir.parent.parent / "test-framework"
        self.cycles_dir = self.test_framework_dir / "results" / "test-cycles"
        self.cycles_dir.mkdir(parents=True, exist_ok=True)

    def start_cycle(
        self,
        project: str,
        phase: str,
        stage: str,
        build_version: str = ""
    ) -> TestCycle:
        """Start a new test cycle."""
        cycle_id = f"{project}_phase{phase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        cycle = TestCycle(
            cycle_id=cycle_id,
            project=project,
            phase=phase,
            stage=stage,
            build_version=build_version
        )

        self._save_cycle(cycle)
        print(f"Started test cycle: {cycle_id}")
        return cycle

    def add_test_run(
        self,
        cycle_id: str,
        test_type: TestType,
        framework: str,
        tests_run: int = 0,
        tests_passed: int = 0,
        tests_failed: int = 0,
        tests_skipped: int = 0,
        duration_seconds: float = 0,
        status: str = "pending",
        error: str = "",
        details: List[str] = None
    ) -> Optional[TestCycle]:
        """Add a test run result to a cycle."""
        cycle = self._load_cycle(cycle_id)
        if not cycle:
            print(f"Cycle not found: {cycle_id}")
            return None

        test_run = TestRunResult(
            test_type=test_type,
            framework=framework,
            tests_run=tests_run,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            tests_skipped=tests_skipped,
            duration_seconds=duration_seconds,
            status=status,
            error=error,
            details=details or []
        )

        cycle.test_runs.append(test_run)
        cycle.status = cycle.overall_status
        self._save_cycle(cycle)

        print(f"Added {test_type.value} results to cycle {cycle_id}")
        return cycle

    def complete_cycle(self, cycle_id: str, notes: str = "") -> Optional[TestCycle]:
        """Mark a cycle as complete."""
        cycle = self._load_cycle(cycle_id)
        if not cycle:
            return None

        cycle.completed_at = datetime.now().isoformat()
        cycle.status = cycle.overall_status
        cycle.notes = notes
        self._save_cycle(cycle)

        print(f"Completed test cycle: {cycle_id} [{cycle.status}]")
        return cycle

    def get_cycle(self, cycle_id: str) -> Optional[TestCycle]:
        """Get a test cycle by ID."""
        return self._load_cycle(cycle_id)

    def get_cycles_for_phase(self, phase: str) -> List[TestCycle]:
        """Get all cycles for a phase."""
        cycles = []
        for cycle_file in self.cycles_dir.glob("*.json"):
            cycle = self._load_cycle_from_file(cycle_file)
            if cycle and cycle.phase == phase:
                cycles.append(cycle)
        return sorted(cycles, key=lambda c: c.started_at)

    def get_latest_cycle(self) -> Optional[TestCycle]:
        """Get the most recent test cycle."""
        cycles = []
        for cycle_file in self.cycles_dir.glob("*.json"):
            cycle = self._load_cycle_from_file(cycle_file)
            if cycle:
                cycles.append(cycle)

        if not cycles:
            return None

        return sorted(cycles, key=lambda c: c.started_at)[-1]

    def get_cycle_summary(self, cycle_id: str) -> Dict[str, Any]:
        """Get a summary of a test cycle."""
        cycle = self._load_cycle(cycle_id)
        if not cycle:
            return {"error": "Cycle not found"}

        return {
            "cycle_id": cycle.cycle_id,
            "project": cycle.project,
            "phase": cycle.phase,
            "stage": cycle.stage,
            "status": cycle.status,
            "started_at": cycle.started_at,
            "completed_at": cycle.completed_at,
            "total_tests": cycle.total_tests,
            "total_passed": cycle.total_passed,
            "total_failed": cycle.total_failed,
            "test_types": [r.test_type.value for r in cycle.test_runs],
            "defects_logged": cycle.defects_logged,
            "defects_fixed": cycle.defects_fixed,
            "build_version": cycle.build_version
        }

    def get_project_summary(self) -> Dict[str, Any]:
        """Get summary of all cycles for a project."""
        cycles = []
        for cycle_file in self.cycles_dir.glob("*.json"):
            cycle = self._load_cycle_from_file(cycle_file)
            if cycle:
                cycles.append(cycle)

        if not cycles:
            return {"total_cycles": 0, "cycles": []}

        return {
            "total_cycles": len(cycles),
            "passed": sum(1 for c in cycles if c.status == "passed"),
            "failed": sum(1 for c in cycles if c.status == "failed"),
            "running": sum(1 for c in cycles if c.status == "running"),
            "total_tests": sum(c.total_tests for c in cycles),
            "total_passed": sum(c.total_passed for c in cycles),
            "total_failed": sum(c.total_failed for c in cycles),
            "cycles": [self.get_cycle_summary(c.cycle_id) for c in cycles]
        }

    def _save_cycle(self, cycle: TestCycle):
        """Save a test cycle to file."""
        filepath = self.cycles_dir / f"{cycle.cycle_id}.json"
        with open(filepath, "w") as f:
            json.dump(asdict(cycle), f, indent=2, default=str)

    def _load_cycle(self, cycle_id: str) -> Optional[TestCycle]:
        """Load a test cycle from file."""
        filepath = self.cycles_dir / f"{cycle_id}.json"
        return self._load_cycle_from_file(filepath)

    def _load_cycle_from_file(self, filepath: Path) -> Optional[TestCycle]:
        """Load a test cycle from a file path."""
        try:
            with open(filepath) as f:
                data = json.load(f)

            cycle = TestCycle(
                cycle_id=data["cycle_id"],
                project=data["project"],
                phase=data["phase"],
                stage=data["stage"],
                started_at=data.get("started_at", ""),
                completed_at=data.get("completed_at", ""),
                status=data.get("status", "running"),
                defects_logged=data.get("defects_logged", 0),
                defects_fixed=data.get("defects_fixed", 0),
                build_version=data.get("build_version", ""),
                notes=data.get("notes", "")
            )

            for run_data in data.get("test_runs", []):
                _tt = run_data.get("test_type")
                if isinstance(_tt, str) and _tt.startswith("TestType."):
                    _tt = _tt.split(".", 1)[1]
                if isinstance(_tt, str) and _tt not in {t.name for t in TestType} \
                        and _tt not in {t.value for t in TestType}:
                    _tt = list(TestType)[0].name
                try:
                    _tt_enum = TestType[_tt] if _tt in {t.name for t in TestType} else TestType(_tt)
                except Exception:
                    _tt_enum = list(TestType)[0]
                test_run = TestRunResult(
                    test_type=_tt_enum,
                    framework=run_data["framework"],
                    tests_run=run_data.get("tests_run", 0),
                    tests_passed=run_data.get("tests_passed", 0),
                    tests_failed=run_data.get("tests_failed", 0),
                    tests_skipped=run_data.get("tests_skipped", 0),
                    duration_seconds=run_data.get("duration_seconds", 0),
                    status=run_data.get("status", "pending"),
                    error=run_data.get("error", ""),
                    details=run_data.get("details", []),
                    timestamp=run_data.get("timestamp", "")
                )
                cycle.test_runs.append(test_run)

            return cycle
        except Exception as e:
            print(f"Error loading cycle {filepath}: {e}")
            return None


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python test_cycle.py <command> [args]")
        print("Commands:")
        print("  start <project> <phase> <stage>    Start a new test cycle")
        print("  add <cycle_id> <test_type> ...     Add test run to cycle")
        print("  complete <cycle_id>                Complete a cycle")
        print("  summary [cycle_id]                 Show cycle summary")
        print("  project <project>                  Show project summary")
        sys.exit(1)

    command = sys.argv[1]

    if command == "start":
        if len(sys.argv) < 5:
            print("Usage: python test_cycle.py start <project> <phase> <stage>")
            sys.exit(1)

        project = sys.argv[2]
        phase = sys.argv[3]
        stage = sys.argv[4]

        # Get project directory
        products_dir = Path(__file__).parent.parent.parent / "products"
        project_dir = products_dir / project

        manager = TestCycleManager(str(project_dir))
        cycle = manager.start_cycle(project, phase, stage)
        print(f"Cycle started: {cycle.cycle_id}")

    elif command == "complete":
        if len(sys.argv) < 3:
            print("Usage: python test_cycle.py complete <cycle_id>")
            sys.exit(1)

        cycle_id = sys.argv[2]
        products_dir = Path(__file__).parent.parent.parent / "products"

        # Find project from cycle_id
        project = cycle_id.split("_")[0]
        project_dir = products_dir / project

        manager = TestCycleManager(str(project_dir))
        cycle = manager.complete_cycle(cycle_id)
        if cycle:
            print(f"Cycle completed: {cycle.status}")

    elif command == "summary":
        cycle_id = sys.argv[2] if len(sys.argv) > 2 else None
        products_dir = Path(__file__).parent.parent.parent / "products"

        if cycle_id:
            project = cycle_id.split("_")[0]
            project_dir = products_dir / project
            manager = TestCycleManager(str(project_dir))
            summary = manager.get_cycle_summary(cycle_id)
        else:
            # Get latest cycle
            project = "myworld"  # Default
            project_dir = products_dir / project
            manager = TestCycleManager(str(project_dir))
            cycle = manager.get_latest_cycle()
            if cycle:
                summary = manager.get_cycle_summary(cycle.cycle_id)
            else:
                summary = {"error": "No cycles found"}

        print(json.dumps(summary, indent=2))

    elif command == "project":
        if len(sys.argv) < 3:
            print("Usage: python test_cycle.py project <project>")
            sys.exit(1)

        project = sys.argv[2]
        products_dir = Path(__file__).parent.parent.parent / "products"
        project_dir = products_dir / project

        manager = TestCycleManager(str(project_dir))
        summary = manager.get_project_summary()
        print(json.dumps(summary, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
