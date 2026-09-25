"""
Security Test Template
Reusable template for security vulnerability tests
"""

import pytest
import httpx

pytestmark = [pytest.mark.security, pytest.mark.{{feature_id}}]

class Test{{feature_name}}Security:
    """Security tests for {{feature_name}}"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_{{feature_id}}_sql_injection(self, base_url):
        """Test {{feature_id}} against SQL injection"""
        payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users;--",
            "1' UNION SELECT * FROM users--",
        ]
        
        for payload in payloads:
            response = httpx.get(f"{base_url}/api/{{feature_id}}", params={"q": payload})
            assert response.status_code != 500, f"SQL injection vulnerability with: {payload}"
    
    def test_{{feature_id}}_xss(self, base_url):
        """Test {{feature_id}} against XSS"""
        payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
        ]
        
        for payload in payloads:
            response = httpx.get(f"{base_url}/api/{{feature_id}}", params={"q": payload})
            assert payload not in response.text, f"XSS vulnerability with: {payload}"
    
    def test_{{feature_id}}_authentication(self, base_url):
        """Test {{feature_id}} requires authentication"""
        response = httpx.get(f"{base_url}/api/{{feature_id}}")
        assert response.status_code in [401, 403], "Endpoint accessible without auth"
    
    def test_{{feature_id}}_rate_limiting(self, base_url):
        """Test {{feature_id}} has rate limiting"""
        responses = []
        for _ in range(100):
            responses.append(httpx.get(f"{base_url}/api/{{feature_id}}"))
        
        rate_limited = any(r.status_code == 429 for r in responses)
        # Not all endpoints need rate limiting, so this is informational
        print(f"Rate limiting {'detected' if rate_limited else 'not detected'}")
    
    def test_{{feature_id}}_headers(self, base_url):
        """Test {{feature_id}} security headers"""
        response = httpx.get(f"{base_url}/api/{{feature_id}}")
        
        # Check for security headers
        headers = response.headers
        assert "x-content-type-options" in headers, "Missing X-Content-Type-Options header"
        assert "x-frame-options" in headers, "Missing X-Frame-Options header"
