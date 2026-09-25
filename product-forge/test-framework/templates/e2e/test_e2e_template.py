"""
E2E Test Template
Reusable template for end-to-end tests using Playwright
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.e2e, pytest.mark.{{feature_id}}]

class Test{{feature_name}}E2E:
    """E2E tests for {{feature_name}}"""
    
    def test_{{feature_id}}_page_loads(self, page: Page):
        """Test {{feature_id}} page loads"""
        page.goto("http://localhost:3000/{{feature_id}}")
        expect(page).to_have_title("MyWorld")
    
    def test_{{feature_id}}_elements_visible(self, page: Page):
        """Test {{feature_id}} elements are visible"""
        page.goto("http://localhost:3000/{{feature_id}}")
        # TODO: Add specific element checks
        # expect(page.locator("selector")).to_be_visible()
    
    def test_{{feature_id}}_user_interaction(self, page: Page):
        """Test {{feature_id}} user interaction"""
        page.goto("http://localhost:3000/{{feature_id}}")
        # TODO: Add interaction tests
        # page.click("button")
        # page.fill("input", "value")
    
    def test_{{feature_id}}_responsive(self, page: Page):
        """Test {{feature_id}} responsive design"""
        page.goto("http://localhost:3000/{{feature_id}}")
        
        # Mobile
        page.set_viewport_size({"width": 375, "height": 667})
        page.screenshot(path="screenshots/{{feature_id}}_mobile.png")
        
        # Desktop
        page.set_viewport_size({"width": 1280, "height": 720})
        page.screenshot(path="screenshots/{{feature_id}}_desktop.png")
