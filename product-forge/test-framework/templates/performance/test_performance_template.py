"""
Performance Test Template
Reusable template for performance and load tests
"""

import pytest
import time
import httpx

pytestmark = [pytest.mark.performance, pytest.mark.{{feature_id}}]

class Test{{feature_name}}Performance:
    """Performance tests for {{feature_name}}"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_{{feature_id}}_response_time(self, base_url):
        """Test {{feature_id}} response time"""
        start = time.time()
        response = httpx.get(f"{base_url}/api/{{feature_id}}")
        duration = (time.time() - start) * 1000  # Convert to ms
        
        assert response.status_code == 200
        assert duration < 500, f"Response too slow: {duration}ms (threshold: 500ms)"
    
    def test_{{feature_id}}_concurrent_requests(self, base_url):
        """Test {{feature_id}} under concurrent load"""
        import concurrent.futures
        
        def make_request():
            return httpx.get(f"{base_url}/api/{{feature_id}}")
        
        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        duration = time.time() - start
        
        successful = sum(1 for r in results if r.status_code == 200)
        assert successful >= 45, f"Too many failures: {50 - successful}"
        assert duration < 10, f"Too slow under load: {duration}s"
    
    def test_{{feature_id}}_memory_usage(self, base_url):
        """Test {{feature_id}} memory usage"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Make multiple requests
        for _ in range(100):
            httpx.get(f"{base_url}/api/{{feature_id}}")
        
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        mem_increase = mem_after - mem_before
        
        assert mem_increase < 50, f"Memory leak detected: {mem_increase}MB increase"
