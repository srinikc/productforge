"""
Stress Test Template
Reusable template for stress testing
"""

import pytest
import concurrent.futures
import time
import httpx

pytestmark = [pytest.mark.stress, pytest.mark.performance, pytest.mark.{{feature_id}}]

class Test{{feature_name}}Stress:
    """Stress tests for {{feature_name}}"""
    
    @pytest.fixture
    def base_url(self):
        return "http://localhost:8000"
    
    def test_{{feature_id}}_stress_sustained_load(self, base_url):
        """Test under sustained high load"""
        def make_request():
            return httpx.get(f"{base_url}/api/{{feature_id}}")
        
        # Run 500 requests with 50 concurrent
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            start = time.time()
            futures = [executor.submit(make_request) for _ in range(500)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
            duration = time.time() - start
        
        successful = sum(1 for r in results if r.status_code == 200)
        assert successful >= 450, f"Too many failures under stress: {500 - successful}"
        assert duration < 60, f"Stress test took too long: {duration}s"
    
    def test_{{feature_id}}_stress_spike_load(self, base_url):
        """Test under sudden traffic spike"""
        def make_request():
            return httpx.get(f"{base_url}/api/{{feature_id}}")
        
        # Sudden spike of 100 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            start = time.time()
            futures = [executor.submit(make_request) for _ in range(100)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
            duration = time.time() - start
        
        successful = sum(1 for r in results if r.status_code == 200)
        # Allow higher failure rate for stress test
        assert successful >= 70, f"System failed under spike: {100 - successful} failures"
    
    def test_{{feature_id}}_stress_memory(self, base_url):
        """Test memory usage under stress"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024
        
        def make_request():
            return httpx.get(f"{base_url}/api/{{feature_id}}")
        
        # Run many requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(200)]
            concurrent.futures.wait(futures)
        
        mem_after = process.memory_info().rss / 1024 / 1024
        mem_increase = mem_after - mem_before
        
        assert mem_increase < 100, f"Memory leak under stress: {mem_increase}MB increase"
    
    def test_{{feature_id}}_stress_recovery(self, base_url):
        """Test system recovery after stress"""
        def make_request():
            return httpx.get(f"{base_url}/api/{{feature_id}}")
        
        # Apply stress
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_request) for _ in range(200)]
            concurrent.futures.wait(futures)
        
        # Wait for recovery
        time.sleep(5)
        
        # Test normal operation
        response = httpx.get(f"{base_url}/api/{{feature_id}}")
        assert response.status_code == 200, "System did not recover after stress"
