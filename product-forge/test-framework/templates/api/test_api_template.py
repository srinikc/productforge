"""
API Test Template
Reusable template for API endpoint tests
"""

import pytest
import httpx

pytestmark = [pytest.mark.api, pytest.mark.{{feature_id}}]

class Test{{feature_name}}API:
    """API tests for {{feature_name}}"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_{{feature_id}}_endpoint_exists(self, base_url):
        """Test {{feature_id}} endpoint exists"""
        response = httpx.get(f"{base_url}/api/{{feature_id}}")
        assert response.status_code in [200, 401, 403]  # Exists but may require auth
    
    def test_{{feature_id}}_returns_json(self, base_url):
        """Test {{feature_id}} returns JSON"""
        response = httpx.get(f"{base_url}/api/{{feature_id}}")
        assert response.headers.get("content-type") == "application/json"
    
    def test_{{feature_id}}_response_time(self, base_url):
        """Test {{feature_id}} response time"""
        import time
        start = time.time()
        response = httpx.get(f"{base_url}/api/{{feature_id}}")
        duration = time.time() - start
        assert duration < 1.0, f"Response too slow: {duration}s"
    
    def test_{{feature_id}}_error_handling(self, base_url):
        """Test {{feature_id}} error handling"""
        response = httpx.get(f"{base_url}/api/{{feature_id}}/invalid")
        assert response.status_code in [400, 404, 422]
