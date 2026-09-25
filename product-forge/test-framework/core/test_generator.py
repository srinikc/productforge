"""
Test Generator - AI + Playwright MCP test generation
"""

import os
import json
from typing import Dict, List, Optional, Any
from pathlib import Path

class TestGenerator:
    """Generates tests using AI and Playwright MCP"""
    
    def __init__(self, templates_path: Optional[str] = None):
        self.templates_path = Path(templates_path or Path(__file__).parent.parent / "templates")
        self.templates = self._load_templates()
        
    def _load_templates(self) -> Dict[str, Any]:
        """Load test templates (every category directory under templates/)."""
        templates = {}
        if not self.templates_path.exists():
            return templates
        for category_path in sorted(self.templates_path.iterdir()):
            if not category_path.is_dir():
                continue
            items = []
            for template_file in category_path.glob("*.py"):
                items.append({
                    "name": template_file.stem,
                    "path": str(template_file),
                    "content": template_file.read_text(encoding="utf-8")
                })
            if items:
                templates[category_path.name] = items
        return templates
    
    def generate_api_tests(self, api_spec: Dict[str, Any], feature: Dict[str, Any]) -> List[str]:
        """Generate API tests from specification"""
        tests = []
        
        endpoints = api_spec.get("endpoints", [])
        feature_tests = feature.get("tests", [])
        
        for endpoint in endpoints:
            method = endpoint.get("method", "GET")
            path = endpoint.get("path", "/")
            name = endpoint.get("name", "unknown")
            
            test_code = f'''
import pytest
import httpx

pytestmark = [pytest.mark.api, pytest.mark.{feature.get("id", "unknown")}]

class Test{name.title().replace("-", "")}:
    """Tests for {name} endpoint"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_{name.replace("-", "_")}_success(self, base_url):
        """Test {method} {path} returns 200"""
        response = httpx.{method.lower()}(f"{{base_url}}{path}")
        assert response.status_code == 200
    
    def test_{name.replace("-", "_")}_response_time(self, base_url):
        """Test {method} {path} response time"""
        import time
        start = time.time()
        response = httpx.{method.lower()}(f"{{base_url}}{path}")
        duration = time.time() - start
        assert duration < 1.0, f"Response too slow: {{duration}}s"
'''
            tests.append(test_code)
        
        return tests
    
    def generate_e2e_tests(self, user_flows: List[Dict[str, Any]], feature: Dict[str, Any]) -> List[str]:
        """Generate E2E tests from user flows"""
        tests = []
        
        for flow in user_flows:
            flow_name = flow.get("name", "unknown")
            steps = flow.get("steps", [])
            
            steps_code = ""
            for i, step in enumerate(steps):
                action = step.get("action", "click")
                selector = step.get("selector", "")
                value = step.get("value", "")
                
                if action == "navigate":
                    steps_code += f'        page.goto("{value}")\n'
                elif action == "click":
                    steps_code += f'        page.click("{selector}")\n'
                elif action == "fill":
                    steps_code += f'        page.fill("{selector}", "{value}")\n'
                elif action == "assert":
                    steps_code += f'        expect(page.locator("{selector}")).to_be_visible()\n'
            
            test_code = f'''
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.e2e, pytest.mark.{feature.get("id", "unknown")}]

class Test{flow_name.title().replace("-", "")}:
    """E2E tests for {flow_name} flow"""
    
    def test_{flow_name.replace("-", "_")}(self, page: Page):
        """Test {flow_name} user flow"""
{steps_code}
'''
            tests.append(test_code)
        
        return tests
    
    def generate_visual_tests(self, pages: List[Dict[str, Any]], feature: Dict[str, Any]) -> List[str]:
        """Generate visual regression tests using Playwright MCP"""
        tests = []
        
        for page_info in pages:
            page_name = page_info.get("name", "unknown")
            url = page_info.get("url", "/")
            
            test_code = f'''
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.visual, pytest.mark.{feature.get("id", "unknown")}]

class Test{page_name.title().replace("-", "")}Visual:
    """Visual regression tests for {page_name}"""
    
    def test_{page_name.replace("-", "_")}_visual(self, page: Page):
        """Test {page_name} visual consistency"""
        page.goto("{url}")
        
        # Take screenshot for visual comparison
        page.screenshot(path="screenshots/{page_name}_baseline.png")
        
        # Verify no visual regressions
        expect(page).to_have_screenshot("{page_name}_baseline.png")
    
    def test_{page_name.replace("-", "_")}_responsive(self, page: Page):
        """Test {page_name} responsive design"""
        page.goto("{url}")
        
        # Test mobile viewport
        page.set_viewport_size({{"width": 375, "height": 667}})
        page.screenshot(path="screenshots/{page_name}_mobile.png")
        
        # Test tablet viewport
        page.set_viewport_size({{"width": 768, "height": 1024}})
        page.screenshot(path="screenshots/{page_name}_tablet.png")
        
        # Test desktop viewport
        page.set_viewport_size({{"width": 1280, "height": 720}})
        page.screenshot(path="screenshots/{page_name}_desktop.png")
'''
            tests.append(test_code)
        
        return tests
    
    def generate_from_templates(self, feature: Dict[str, Any], category: str) -> List[str]:
        """Generate tests from templates"""
        tests = []
        
        templates = self.templates.get(category, [])
        for template in templates:
            # Replace placeholders with feature data
            content = template["content"]
            content = content.replace("{{feature_id}}", feature.get("id", "unknown"))
            content = content.replace("{{feature_name}}", feature.get("name", "Unknown"))
            tests.append(content)
        
        return tests
    
    def generate_all_tests(self, project_config: Dict[str, Any]) -> Dict[str, List[str]]:
        """Generate all tests for a project"""
        all_tests = {}
        
        features = project_config.get("features", [])
        test_categories = project_config.get("test_categories", {})
        
        for feature in features:
            feature_id = feature.get("id", "unknown")
            
            # Generate based on enabled categories
            if test_categories.get("api", False):
                all_tests[f"{feature_id}_api"] = self.generate_api_tests(
                    {"endpoints": [{"method": "GET", "path": f"/api/{feature_id}", "name": feature_id}]},
                    feature
                )
            
            if test_categories.get("e2e", False):
                all_tests[f"{feature_id}_e2e"] = self.generate_e2e_tests(
                    [{"name": feature_id, "steps": [{"action": "navigate", "value": "/"}]}],
                    feature
                )
            
            if test_categories.get("visual", False):
                all_tests[f"{feature_id}_visual"] = self.generate_visual_tests(
                    [{"name": feature_id, "url": f"/{feature_id}"}],
                    feature
                )
        
        return all_tests
    
    def save_tests(self, tests: Dict[str, List[str]], output_path: str):
        """Save generated tests to files"""
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for test_name, test_codes in tests.items():
            for i, test_code in enumerate(test_codes):
                test_file = output_dir / f"{test_name}_{i}.py"
                test_file.write_text(test_code)
