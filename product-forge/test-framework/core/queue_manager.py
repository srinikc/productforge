"""
Queue Manager - Manages project execution queue for parallel execution.

Phase 1.2 (CRITICAL): Multi-project parallel execution with controlled concurrency.
"""
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum


class QueueStatus(str, Enum):
    """Status of a project in the queue."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueueItem:
    """An item in the project execution queue."""
    project: str
    priority: int = 1  # Lower = higher priority
    enqueued_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: str = QueueStatus.PENDING.value
    attempts: int = 0
    last_error: Optional[str] = None
    
    def __post_init__(self):
        if not self.enqueued_at:
            self.enqueued_at = datetime.utcnow().isoformat()


class QueueManager:
    """File-based project execution queue with priority support."""
    
    QUEUE_FILE = "queue.json"
    MAX_PARALLEL_DEFAULT = 3
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.queue_file = self.products_dir / self.QUEUE_FILE
    
    def _load_queue(self) -> dict:
        """Load queue state from disk."""
        if not self.queue_file.exists():
            return {"max_parallel": self.MAX_PARALLEL_DEFAULT, "items": []}
        
        try:
            return json.loads(self.queue_file.read_text())
        except (json.JSONDecodeError, OSError):
            return {"max_parallel": self.MAX_PARALLEL_DEFAULT, "items": []}
    
    def _save_queue(self, queue: dict) -> None:
        """Save queue state to disk."""
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self.queue_file.write_text(json.dumps(queue, indent=2, default=str))
    
    def enqueue(self, project: str, priority: int = 1) -> QueueItem:
        """
        Add a project to the execution queue.
        
        Args:
            project: Project name
            priority: Priority (lower = higher priority)
        
        Returns:
            The created queue item
        """
        queue = self._load_queue()
        
        # Check if already in queue
        for item in queue["items"]:
            if item["project"] == project and item["status"] in [
                QueueStatus.PENDING.value, QueueStatus.RUNNING.value
            ]:
                # Update priority if lower
                if priority < item["priority"]:
                    item["priority"] = priority
                    self._save_queue(queue)
                return QueueItem(**item)
        
        # Add new item
        item = QueueItem(project=project, priority=priority)
        queue["items"].append(asdict(item))
        self._save_queue(queue)
        
        return item
    
    def dequeue(self) -> Optional[QueueItem]:
        """
        Get the next project to run (highest priority, oldest first).
        
        Returns:
            Next queue item or None if queue is empty
        """
        queue = self._load_queue()
        
        # Get pending items, sort by priority then enqueue time
        pending = [QueueItem(**i) for i in queue["items"] if i["status"] == QueueStatus.PENDING.value]
        pending.sort(key=lambda x: (x.priority, x.enqueued_at))
        
        if not pending:
            return None
        
        # Check if we can start more (max_parallel)
        running = [i for i in queue["items"] if i["status"] == QueueStatus.RUNNING.value]
        if len(running) >= queue.get("max_parallel", self.MAX_PARALLEL_DEFAULT):
            return None
        
        return pending[0]
    
    def mark_running(self, project: str) -> bool:
        """Mark a project as currently running."""
        queue = self._load_queue()
        
        for item in queue["items"]:
            if item["project"] == project and item["status"] == QueueStatus.PENDING.value:
                item["status"] = QueueStatus.RUNNING.value
                item["started_at"] = datetime.utcnow().isoformat()
                item["attempts"] += 1
                self._save_queue(queue)
                return True
        
        return False
    
    def mark_completed(self, project: str) -> bool:
        """Mark a project as completed."""
        queue = self._load_queue()
        
        for item in queue["items"]:
            if item["project"] == project and item["status"] == QueueStatus.RUNNING.value:
                item["status"] = QueueStatus.COMPLETED.value
                item["completed_at"] = datetime.utcnow().isoformat()
                self._save_queue(queue)
                return True
        
        return False
    
    def mark_failed(self, project: str, error: str) -> bool:
        """Mark a project as failed."""
        queue = self._load_queue()
        
        for item in queue["items"]:
            if item["project"] == project and item["status"] == QueueStatus.RUNNING.value:
                item["status"] = QueueStatus.FAILED.value
                item["completed_at"] = datetime.utcnow().isoformat()
                item["last_error"] = error
                self._save_queue(queue)
                return True
        
        return False
    
    def cancel(self, project: str) -> bool:
        """Cancel a pending or running project."""
        queue = self._load_queue()
        
        for item in queue["items"]:
            if item["project"] == project and item["status"] in [
                QueueStatus.PENDING.value, QueueStatus.RUNNING.value
            ]:
                item["status"] = QueueStatus.CANCELLED.value
                item["completed_at"] = datetime.utcnow().isoformat()
                self._save_queue(queue)
                return True
        
        return False
    
    def get_position(self, project: str) -> Optional[int]:
        """Get a project's position in the queue (1-indexed, 0 if running)."""
        queue = self._load_queue()
        
        for item in queue["items"]:
            if item["project"] == project:
                if item["status"] == QueueStatus.RUNNING.value:
                    return 0
                elif item["status"] == QueueStatus.PENDING.value:
                    pending = sorted(
                        [i for i in queue["items"] if i["status"] == QueueStatus.PENDING.value],
                        key=lambda x: (x["priority"], x["enqueued_at"])
                    )
                    for pos, p in enumerate(pending, 1):
                        if p["project"] == project:
                            return pos
        return None
    
    def list_items(self, status: Optional[str] = None) -> list[QueueItem]:
        """List queue items, optionally filtered by status."""
        queue = self._load_queue()
        items = queue["items"]
        
        if status:
            items = [i for i in items if i["status"] == status]
        
        return [QueueItem(**i) for i in items]
    
    def clear_completed(self) -> int:
        """Remove completed/failed/cancelled items from queue. Returns count removed."""
        queue = self._load_queue()
        before = len(queue["items"])
        queue["items"] = [
            i for i in queue["items"]
            if i["status"] in [QueueStatus.PENDING.value, QueueStatus.RUNNING.value]
        ]
        removed = before - len(queue["items"])
        self._save_queue(queue)
        return removed
