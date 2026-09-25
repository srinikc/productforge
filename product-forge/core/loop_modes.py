"""
Loop Modes - Phase 3.1 & 3.2

Different loop execution modes for agent operations:
- Time-Based Loop (3.1): Run for a fixed time period
- Event-Based Loop (3.2): Run until a specific event occurs

Phase 3 (ADVANCED): Flexible loop execution patterns.
"""
import json
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum


class LoopMode(str, Enum):
    """Execution loop modes."""
    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"
    COUNT_BASED = "count_based"
    UNTIL_SUCCESS = "until_success"
    UNTIL_FAILURE = "until_failure"


class LoopState(str, Enum):
    """Loop execution state."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class LoopConfig:
    """Configuration for a loop execution."""
    mode: str
    max_iterations: int = 100
    max_duration_seconds: int = 3600
    target_event: Optional[str] = None
    sleep_between_iterations: float = 0.0
    stop_on_first_success: bool = False
    stop_on_first_failure: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class LoopResult:
    """Result of a loop execution."""
    mode: str
    iterations: int
    duration_seconds: float
    success: bool
    state: str
    started_at: str
    completed_at: str
    error: Optional[str] = None
    results: list = field(default_factory=list)


class LoopController:
    """
    Controller for various loop execution modes.
    
    Phase 3.1 & 3.2: Time-Based and Event-Based loops.
    """
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.loops_dir = self.products_dir / ".pipeline" / "loops"
        self.loops_dir.mkdir(parents=True, exist_ok=True)
        self._active_loops: dict[str, dict] = {}
        self._event_listeners: dict[str, list[Callable]] = {}
    
    def create_loop(
        self,
        loop_id: str,
        config: LoopConfig,
    ) -> dict:
        """Create a new loop and return its state."""
        loop_state = {
            "id": loop_id,
            "config": asdict(config),
            "state": LoopState.PENDING.value,
            "iterations": 0,
            "started_at": None,
            "completed_at": None,
            "results": [],
            "error": None,
        }
        self._active_loops[loop_id] = loop_state
        self._save_loop(loop_id, loop_state)
        return loop_state
    
    def execute_time_based(
        self,
        loop_id: str,
        action: Callable,
        duration_seconds: int,
        interval: float = 0.0,
    ) -> LoopResult:
        """
        Execute an action in a time-based loop.
        
        Phase 3.1: Runs the action repeatedly for a fixed duration.
        """
        start = datetime.utcnow()
        end = start + timedelta(seconds=duration_seconds)
        iterations = 0
        results = []
        
        while datetime.utcnow() < end:
            try:
                result = action()
                results.append(result)
                iterations += 1
            except Exception as e:
                results.append({"error": str(e), "iteration": iterations})
            
            if interval > 0:
                time.sleep(interval)
        
        duration = (datetime.utcnow() - start).total_seconds()
        return LoopResult(
            mode=LoopMode.TIME_BASED.value,
            iterations=iterations,
            duration_seconds=duration,
            success=True,
            state=LoopState.COMPLETED.value,
            started_at=start.isoformat(),
            completed_at=datetime.utcnow().isoformat(),
            results=results,
        )
    
    def execute_event_based(
        self,
        loop_id: str,
        action: Callable,
        event_name: str,
        timeout_seconds: int = 3600,
    ) -> LoopResult:
        """
        Execute an action in an event-based loop.
        
        Phase 3.2: Runs the action until a specific event is fired.
        """
        start = datetime.utcnow()
        end = start + timedelta(seconds=timeout_seconds)
        iterations = 0
        results = []
        event_fired = threading.Event()
        
        def trigger():
            event_fired.set()
        
        # Register listener
        if event_name not in self._event_listeners:
            self._event_listeners[event_name] = []
        self._event_listeners[event_name].append(trigger)
        
        try:
            while not event_fired.is_set() and datetime.utcnow() < end:
                try:
                    result = action()
                    results.append(result)
                    iterations += 1
                except Exception as e:
                    results.append({"error": str(e), "iteration": iterations})
                
                # Wait briefly
                if event_fired.wait(timeout=0.1):
                    break
            
            duration = (datetime.utcnow() - start).total_seconds()
            return LoopResult(
                mode=LoopMode.EVENT_BASED.value,
                iterations=iterations,
                duration_seconds=duration,
                success=event_fired.is_set(),
                state=LoopState.COMPLETED.value if event_fired.is_set() else LoopState.STOPPED.value,
                started_at=start.isoformat(),
                completed_at=datetime.utcnow().isoformat(),
                results=results,
            )
        finally:
            # Cleanup listener
            if trigger in self._event_listeners.get(event_name, []):
                self._event_listeners[event_name].remove(trigger)
    
    def fire_event(self, event_name: str, data: Optional[dict] = None) -> int:
        """Fire an event to all listeners."""
        listeners = self._event_listeners.get(event_name, [])
        for listener in listeners:
            try:
                listener()
            except Exception:
                pass
        return len(listeners)
    
    def execute_count_based(
        self,
        action: Callable,
        count: int,
        interval: float = 0.0,
    ) -> LoopResult:
        """Execute an action exactly N times."""
        start = datetime.utcnow()
        results = []
        
        for i in range(count):
            try:
                result = action()
                results.append(result)
            except Exception as e:
                results.append({"error": str(e), "iteration": i})
            
            if interval > 0 and i < count - 1:
                time.sleep(interval)
        
        duration = (datetime.utcnow() - start).total_seconds()
        return LoopResult(
            mode=LoopMode.COUNT_BASED.value,
            iterations=count,
            duration_seconds=duration,
            success=True,
            state=LoopState.COMPLETED.value,
            started_at=start.isoformat(),
            completed_at=datetime.utcnow().isoformat(),
            results=results,
        )
    
    def _save_loop(self, loop_id: str, state: dict) -> None:
        """Save loop state to disk."""
        loop_file = self.loops_dir / f"{loop_id}.json"
        loop_file.write_text(json.dumps(state, indent=2, default=str))
    
    def get_loop_state(self, loop_id: str) -> Optional[dict]:
        """Get state of an active loop."""
        return self._active_loops.get(loop_id)
