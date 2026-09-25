"""
Circuit Breaker - Prevents cascading failures
"""
import time
import json
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class CircuitBreaker:
    name: str
    state: str
    failure_count: int
    success_count: int
    threshold: int
    timeout: int
    last_failure_time: Optional[str]
    last_success_time: Optional[str]

class CircuitBreakerRegistry:
    """Registry of circuit breakers"""
    
    def __init__(self, project: str, threshold: int = 5, timeout: int = 60):
        self.project = project
        self.threshold = threshold
        self.timeout = timeout
        self.registry_file = Path(__file__).parent.parent / "products" / project / "circuit-breakers.json"
        self.breakers: Dict[str, CircuitBreaker] = self._load_breakers()
    
    def _load_breakers(self) -> Dict[str, CircuitBreaker]:
        if self.registry_file.exists():
            with open(self.registry_file) as f:
                data = json.load(f)
                return {k: CircuitBreaker(**v) for k, v in data.items()}
        return {}
    
    def _save_breakers(self):
        with open(self.registry_file, 'w') as f:
            json.dump({k: asdict(v) for k, v in self.breakers.items()}, f, indent=2)
    
    def get_breaker(self, name: str) -> CircuitBreaker:
        """Get or create circuit breaker"""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(
                name=name,
                state=CircuitState.CLOSED.value,
                failure_count=0,
                success_count=0,
                threshold=self.threshold,
                timeout=self.timeout,
                last_failure_time=None,
                last_success_time=None
            )
            self._save_breakers()
        return self.breakers[name]
    
    def can_execute(self, name: str) -> bool:
        """Check if execution is allowed"""
        breaker = self.get_breaker(name)
        
        if breaker.state == CircuitState.CLOSED.value:
            return True
        
        if breaker.state == CircuitState.OPEN.value:
            if breaker.last_failure_time:
                elapsed = time.time() - time.mktime(time.strptime(breaker.last_failure_time, "%Y-%m-%dT%H:%M:%S"))
                if elapsed >= breaker.timeout:
                    breaker.state = CircuitState.HALF_OPEN.value
                    self._save_breakers()
                    return True
            return False
        
        if breaker.state == CircuitState.HALF_OPEN.value:
            return True
        
        return False
    
    def record_success(self, name: str):
        """Record success"""
        breaker = self.get_breaker(name)
        breaker.success_count += 1
        breaker.last_success_time = time.strftime("%Y-%m-%dT%H:%M:%S")
        
        if breaker.state == CircuitState.HALF_OPEN.value:
            breaker.state = CircuitState.CLOSED.value
            breaker.failure_count = 0
        
        self._save_breakers()
    
    def record_failure(self, name: str):
        """Record failure"""
        breaker = self.get_breaker(name)
        breaker.failure_count += 1
        breaker.last_failure_time = time.strftime("%Y-%m-%dT%H:%M:%S")
        
        if breaker.failure_count >= breaker.threshold:
            breaker.state = CircuitState.OPEN.value
        
        self._save_breakers()
    
    def reset(self, name: str):
        """Reset circuit breaker"""
        if name in self.breakers:
            self.breakers[name].state = CircuitState.CLOSED.value
            self.breakers[name].failure_count = 0
            self.breakers[name].success_count = 0
            self._save_breakers()
    
    def get_status(self) -> Dict[str, str]:
        """Get status of all breakers"""
        return {k: v.state for k, v in self.breakers.items()}
