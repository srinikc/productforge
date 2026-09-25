"""
Suite Manager - Manages test suite selection and organization
"""

import yaml
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

class SuiteManager:
    """Manages test suite definitions and selection"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path or Path(__file__).parent.parent / "config")
        self.suites_config = self._load_suites_config()
        self.projects_config = self._load_projects_config()
        
    def _load_suites_config(self) -> Dict[str, Any]:
        """Load test suites configuration"""
        config_file = self.config_path / "test-suites.yaml"
        if config_file.exists():
            with open(config_file) as f:
                return yaml.safe_load(f)
        return {"suites": {}, "categories": {}}
    
    def _load_projects_config(self) -> Dict[str, Any]:
        """Load projects configuration"""
        config_file = self.config_path / "projects.yaml"
        if config_file.exists():
            with open(config_file) as f:
                return yaml.safe_load(f)
        return {"projects": {}}

    # ── write API (QA owns suite/cycle definitions) ─────────────────
    def get_project(self, project: str) -> Dict[str, Any]:
        return (self.projects_config.get("projects", {}) or {}).get(project, {})

    def get_suites(self, project: str) -> Dict[str, Any]:
        return self.get_project(project).get("suites") or {}

    def set_project_suites(self, project: str, suites: Dict[str, Any]) -> Dict[str, Any]:
        projects = self.projects_config.setdefault("projects", {})
        entry = projects.setdefault(project, {"name": project, "type": "product"})
        entry["suites"] = suites
        self._save_projects()
        return entry

    def define_cycle(self, project: str, cycle: Dict[str, Any]) -> Dict[str, Any]:
        projects = self.projects_config.setdefault("projects", {})
        entry = projects.setdefault(project, {"name": project, "type": "product"})
        cycles = entry.setdefault("cycles", {})
        cycles[cycle.get("name", "cycle")] = cycle
        self._save_projects()
        return entry

    def _save_projects(self):
        self.config_path.mkdir(parents=True, exist_ok=True)
        with open(self.config_path / "projects.yaml", "w") as f:
            yaml.safe_dump(self.projects_config, f, sort_keys=False)
    
    def get_suite(self, suite_name: str) -> Optional[Dict[str, Any]]:
        """Get a test suite definition"""
        return self.suites_config.get("suites", {}).get(suite_name)
    
    def list_suites(self) -> List[Dict[str, Any]]:
        """List all available test suites"""
        suites = []
        for suite_name, suite_data in self.suites_config.get("suites", {}).items():
            suites.append({
                "id": suite_name,
                "name": suite_name,
                "description": suite_data.get("description", ""),
                "duration": suite_data.get("duration", "unknown"),
                "schedule": suite_data.get("schedule", "manual"),
                "categories": suite_data.get("categories", []),
                "auto_run": suite_data.get("auto_run", False)
            })
        return suites
    
    def get_suite_for_schedule(self, schedule: str) -> Optional[str]:
        """Get suite name for a given schedule"""
        for suite_name, suite_data in self.suites_config.get("suites", {}).items():
            if suite_data.get("schedule") == schedule:
                return suite_name
        return None
    
    def get_categories_for_suite(self, suite_name: str) -> List[str]:
        """Get test categories for a suite"""
        suite = self.get_suite(suite_name)
        if not suite:
            return []
        
        categories = suite.get("categories", [])
        if "all" in categories:
            return list(self.suites_config.get("categories", {}).keys())
        
        return categories
    
    def get_enabled_categories(self, project: str) -> List[str]:
        """Get enabled test categories for a project"""
        project_config = self.projects_config.get("projects", {}).get(project, {})
        test_categories = project_config.get("test_categories", {})
        
        enabled = []
        for category, is_enabled in test_categories.items():
            if is_enabled:
                enabled.append(category)
        
        return enabled
    
    def select_tests_for_run(self, project: str, suite_name: str) -> Dict[str, Any]:
        """Select which tests to run based on project and suite"""
        suite_categories = self.get_categories_for_suite(suite_name)
        enabled_categories = self.get_enabled_categories(project)
        
        # Intersection of suite categories and enabled categories
        selected = [cat for cat in suite_categories if cat in enabled_categories]
        
        return {
            "project": project,
            "suite": suite_name,
            "selected_categories": selected,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_schedule_triggers(self) -> Dict[str, str]:
        """Get schedule triggers (cron expressions)"""
        triggers = {}
        
        schedules = self.suites_config.get("schedules", {})
        for schedule_name, schedule_data in schedules.items():
            if schedule_data.get("trigger") == "cron":
                triggers[schedule_name] = {
                    "cron": schedule_data.get("cron"),
                    "suite": schedule_data.get("suite")
                }
        
        return triggers
    
    def validate_suite(self, suite_name: str) -> Dict[str, Any]:
        """Validate a test suite definition"""
        suite = self.get_suite(suite_name)
        if not suite:
            return {"valid": False, "error": f"Suite '{suite_name}' not found"}
        
        issues = []
        
        # Check required fields
        required = ["description", "duration", "schedule", "categories"]
        for field in required:
            if field not in suite:
                issues.append(f"Missing required field: {field}")
        
        # Check categories exist
        categories = suite.get("categories", [])
        available_categories = self.suites_config.get("categories", {}).keys()
        
        for category in categories:
            if category != "all" and category not in available_categories:
                issues.append(f"Unknown category: {category}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "suite": suite_name
        }
