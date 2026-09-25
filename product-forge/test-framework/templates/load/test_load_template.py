"""
Load Test Template
Reusable template for load testing using locust
"""

import pytest
from locust import HttpUser, task, between

pytestmark = [pytest.mark.load, pytest.mark.performance, pytest.mark.{{feature_id}}]

class {{feature_name}}LoadUser(HttpUser):
    """Load test user for {{feature_name}}"""
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup before test"""
        # TODO: Login or setup authentication
        pass
    
    @task(3)
    def test_{{feature_id}}_list(self):
        """Test list endpoint under load"""
        self.client.get("/api/{{feature_id}}")
    
    @task(2)
    def test_{{feature_id}}_detail(self):
        """Test detail endpoint under load"""
        self.client.get("/api/{{feature_id}}/1")
    
    @task(1)
    def test_{{feature_id}}_create(self):
        """Test create endpoint under load"""
        self.client.post("/api/{{feature_id}}", json={
            "name": "Load Test Item",
            "description": "Created during load test"
        })

class Test{{feature_name}}Load:
    """Load test configuration"""
    
    def test_{{feature_id}}_load_10_users(self):
        """Test with 10 concurrent users"""
        # Run with: locust -f test_load_template.py --host=http://localhost:8000
        pass
    
    def test_{{feature_id}}_load_50_users(self):
        """Test with 50 concurrent users"""
        pass
    
    def test_{{feature_id}}_load_100_users(self):
        """Test with 100 concurrent users"""
        pass
