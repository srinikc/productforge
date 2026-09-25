"""
Visual Test Template
Reusable template for visual regression tests using Playwright
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.visual, pytest.mark.{{feature_id}}]

class Test{{feature_name}}Visual:
    """Visual regression tests for {{feature_name}}"""
    
    def test_{{feature_id}}_visual_baseline(self, page: Page):
        """Test {{feature_id}} visual baseline"""
        page.goto("http://localhost:3000/{{feature_id}}")
        page.screenshot(path="screenshots/{{feature_id}}_baseline.png")
    
    def test_{{feature_id}}_visual_comparison(self, page: Page):
        """Test {{feature_id}} visual comparison"""
        page.goto("http://localhost:3000/{{feature_id}}")
        expect(page).to_have_screenshot("{{feature_id}}_baseline.png")
    
    def test_{{feature_id}}_mobile_visual(self, page: Page):
        """Test {{feature_id}} mobile visual"""
        page.goto("http://localhost:3000/{{feature_id}}")
        page.set_viewport_size({"width": 375, "height": 667})
        page.screenshot(path="screenshots/{{feature_id}}_mobile.png")
    
    def test_{{feature_id}}_tablet_visual(self, page: Page):
        """Test {{feature_id}} tablet visual"""
        page.goto("http://localhost:3000/{{feature_id}}")
        page.set_viewport_size({"width": 768, "height": 1024})
        page.screenshot(path="screenshots/{{feature_id}}_tablet.png")
    
    def test_{{feature_id}}_desktop_visual(self, page: Page):
        """Test {{feature_id}} desktop visual"""
        page.goto("http://localhost:3000/{{feature_id}}")
        page.set_viewport_size({"width": 1280, "height": 720})
        page.screenshot(path="screenshots/{{feature_id}}_desktop.png")
