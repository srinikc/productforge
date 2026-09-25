"""
Test Runner - Executes test suites and manages test execution
"""

import os
import subprocess
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path

@dataclass
class TestResult:
    test_id: str
    name: str
    status: str  # passed, failed, skipped, error
    duration: float
    message: Optional[str] = None
    traceback: Optional[str] = None
    screenshots: Optional[List[str]] = None
    
@dataclass
class SuiteResult:
    suite_id: str
    project: str
    suite_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"
    tests: List[TestResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration: float = 0.0
    coverage: Optional[float] = None
    
class TestRunner:
    """Main test execution engine"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.execution_config = config.get("execution", {})
        self.base_path = Path(config.get("base_path", ".."))
        
    def run_suite(self, project: str, suite_name: str, 
                  project_config: Dict[str, Any],
                  selective_tests: Optional[List[str]] = None) -> SuiteResult:
        """Run a test suite for a project"""
        result = SuiteResult(
            suite_id=f"{project}_{suite_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            project=project,
            suite_name=suite_name,
            start_time=datetime.now()
        )
        
        try:
            # Get test commands for each app
            apps = project_config.get("apps", {})
            
            for app_name, app_config in apps.items():
                app_results = self._run_app_tests(
                    project, app_name, app_config, selective_tests
                )
                result.tests.extend(app_results)
            
            # Calculate summary
            result.total = len(result.tests)
            result.passed = sum(1 for t in result.tests if t.status == "passed")
            result.failed = sum(1 for t in result.tests if t.status == "failed")
            result.skipped = sum(1 for t in result.tests if t.status == "skipped")
            result.errors = sum(1 for t in result.tests if t.status == "error")
            result.status = "completed" if result.failed == 0 and result.errors == 0 else "failed"
            
        except Exception as e:
            result.status = "failed"
            result.errors += 1
            
        finally:
            result.end_time = datetime.now()
            result.duration = (result.end_time - result.start_time).total_seconds()
        
        return result
    
    def _run_app_tests(self, project: str, app_name: str, 
                       app_config: Dict[str, Any],
                       selective_tests: Optional[List[str]] = None) -> List[TestResult]:
        """Run tests for a specific app"""
        results = []
        
        test_command = app_config.get("test_command")
        if not test_command:
            return results
        
        # Build full path
        app_path = self.base_path / project / app_config.get("path", "")
        
        if not app_path.exists():
            return results
        
        # Run tests based on app type
        app_type = app_config.get("type", "python")
        
        if app_type == "python":
            results = self._run_python_tests(app_path, test_command, selective_tests)
        elif app_type in ["typescript", "javascript"]:
            results = self._run_javascript_tests(app_path, test_command, selective_tests)
        
        return results
    
    def _run_python_tests(self, app_path: Path, test_command: str,
                          selective_tests: Optional[List[str]] = None) -> List[TestResult]:
        """Run Python tests with pytest"""
        results = []
        
        cmd = test_command.split()
        
        # Add selective tests
        if selective_tests:
            cmd.extend(selective_tests)
        
        # Add output format
        cmd.extend(["--tb=short", "-q"])
        
        try:
            process = subprocess.run(
                cmd,
                cwd=str(app_path),
                capture_output=True,
                text=True,
                timeout=self.execution_config.get("default_timeout", 300)
            )
            
            results = self._parse_pytest_output(process.stdout, process.stderr, process.returncode)
            
        except subprocess.TimeoutExpired:
            results.append(TestResult(
                test_id="timeout",
                name="Test execution timeout",
                status="error",
                duration=self.execution_config.get("default_timeout", 300),
                message="Test execution timed out"
            ))
        except Exception as e:
            results.append(TestResult(
                test_id="error",
                name="Test execution error",
                status="error",
                duration=0,
                message=str(e)
            ))
        
        return results
    
    def _run_javascript_tests(self, app_path: Path, test_command: str,
                              selective_tests: Optional[List[str]] = None) -> List[TestResult]:
        """Run JavaScript/TypeScript tests with Jest"""
        results = []
        
        cmd = ["npm", "test"]
        
        # Add Jest arguments
        jest_args = []
        if selective_tests:
            jest_args.extend(["--testPathPattern", "|".join(selective_tests)])
        
        if jest_args:
            cmd.extend(["--", *jest_args])
        
        try:
            process = subprocess.run(
                cmd,
                cwd=str(app_path),
                capture_output=True,
                text=True,
                timeout=self.execution_config.get("default_timeout", 300)
            )
            
            results = self._parse_jest_output(process.stdout, process.stderr, process.returncode)
            
        except subprocess.TimeoutExpired:
            results.append(TestResult(
                test_id="timeout",
                name="Test execution timeout",
                status="error",
                duration=self.execution_config.get("default_timeout", 300),
                message="Test execution timed out"
            ))
        except Exception as e:
            results.append(TestResult(
                test_id="error",
                name="Test execution error",
                status="error",
                duration=0,
                message=str(e)
            ))
        
        return results
    
    def _parse_pytest_output(self, stdout: str, stderr: str, returncode: int) -> List[TestResult]:
        """Parse pytest output"""
        results = []
        
        lines = stdout.split('\n')
        for line in lines:
            if "PASSED" in line:
                test_name = line.split("::")[-1] if "::" in line else line.strip()
                results.append(TestResult(
                    test_id=test_name,
                    name=test_name,
                    status="passed",
                    duration=0
                ))
            elif "FAILED" in line:
                test_name = line.split("::")[-1] if "::" in line else line.strip()
                results.append(TestResult(
                    test_id=test_name,
                    name=test_name,
                    status="failed",
                    duration=0,
                    message=line
                ))
            elif "SKIPPED" in line:
                test_name = line.split("::")[-1] if "::" in line else line.strip()
                results.append(TestResult(
                    test_id=test_name,
                    name=test_name,
                    status="skipped",
                    duration=0
                ))
            elif "ERROR" in line and "ERRORS" not in line:
                results.append(TestResult(
                    test_id="error",
                    name="Test error",
                    status="error",
                    duration=0,
                    message=line
                ))
        
        return results
    
    def _parse_jest_output(self, stdout: str, stderr: str, returncode: int) -> List[TestResult]:
        """Parse Jest output"""
        results = []
        
        lines = stdout.split('\n')
        for line in lines:
            if "✓" in line or "PASS" in line:
                results.append(TestResult(
                    test_id=line.strip(),
                    name=line.strip(),
                    status="passed",
                    duration=0
                ))
            elif "✗" in line or "FAIL" in line:
                results.append(TestResult(
                    test_id=line.strip(),
                    name=line.strip(),
                    status="failed",
                    duration=0,
                    message=line
                ))
        
        return results
    
    def run_selective(self, project: str, test_files: List[str],
                      project_config: Dict[str, Any]) -> SuiteResult:
        """Run specific test files"""
        return self.run_suite(project, "selective", project_config, selective_tests=test_files)
    
    def run_category(self, project: str, category: str,
                     project_config: Dict[str, Any]) -> SuiteResult:
        """Run all tests in a category"""
        # Get test files for category
        test_files = self._get_test_files_for_category(project, category, project_config)
        return self.run_suite(project, category, project_config, selective_tests=test_files)
    
    def _get_test_files_for_category(self, project: str, category: str,
                                     project_config: Dict[str, Any]) -> List[str]:
        """Get test files for a specific category"""
        # This would be enhanced with actual test discovery
        return []
