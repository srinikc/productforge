"""
Circuit Breaker - Prevents cascading failures.

Phase 1.7 (CRITICAL): Circuit breaker pattern for failing operations.
"""
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures."""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 60,
        success_threshold: int = 2,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Identifier for this circuit
            failure_threshold: Failures before opening
            recovery_timeout_seconds: Time before trying again
            success_threshold: Successes in half-open to close
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change: Optional[datetime] = None
    
    def record_success(self) -> bool:
        """
        Record a successful operation.
        
        Returns:
            True if call should proceed
        """
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.last_state_change = datetime.utcnow()
            else:
                return False  # Still open
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._close()
            return True
        
        # CLOSED state
        self.failure_count = 0
        return True
    
    def record_failure(self) -> bool:
        """
        Record a failed operation.
        
        Returns:
            True if call should proceed (circuit is closed)
        """
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitState.HALF_OPEN:
            self._open()
            return False
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._open()
                return False
        
        return True  # Allow the call
    
    def can_proceed(self) -> bool:
        """Check if a call can proceed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.last_state_change = datetime.utcnow()
                return True
            return False
        
        # HALF_OPEN: allow limited calls
        return True
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout
    
    def _open(self) -> None:
        """Open the circuit."""
        self.state = CircuitState.OPEN
        self.last_state_change = datetime.utcnow()
    
    def _close(self) -> None:
        """Close the circuit (normal operation)."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = datetime.utcnow()
    
    def get_state(self) -> dict:
        """Get current circuit state as dict."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_state_change": self.last_state_change.isoformat() if self.last_state_change else None,
        }
    
    def reset(self) -> None:
        """Manually reset the circuit."""
        self._close()


class CircuitBreakerRegistry:
    """Manages circuit breakers for multiple operations."""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self.breakers: dict[str, CircuitBreaker] = {}
    
    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
    ) -> CircuitBreaker:
        """Get an existing circuit breaker or create a new one."""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout_seconds=recovery_timeout,
            )
        return self.breakers[name]
    
    def record_success(self, name: str) -> None:
        """Record success for a named circuit."""
        if name in self.breakers:
            self.breakers[name].record_success()
    
    def record_failure(self, name: str) -> None:
        """Record failure for a named circuit."""
        if name in self.breakers:
            self.breakers[name].record_failure()
    
    def can_proceed(self, name: str) -> bool:
        """Check if a circuit allows the call."""
        if name not in self.breakers:
            return True
        return self.breakers[name].can_proceed()
    
    def get_all_states(self) -> list[dict]:
        """Get states of all circuits."""
        return [cb.get_state() for cb in self.breakers.values()]
    
    def reset_all(self) -> None:
        """Reset all circuits."""
        for cb in self.breakers.values():
            cb.reset()
    
    def reset(self, name: str) -> bool:
        """Reset a specific circuit."""
        if name in self.breakers:
            self.breakers[name].reset()
            return True
        return False
