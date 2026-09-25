"""
Queue Manager
Priority-based project scheduling for concurrent execution
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import IntEnum


class Priority(IntEnum):
    """Queue priority levels"""
    CRITICAL = 0  # Highest priority
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4  # Lowest priority


@dataclass
class QueueItem:
    """Queue item"""
    project: str
    priority: int
    queued_at: str
    reason: Optional[str]
    estimated_duration_minutes: Optional[int]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueItem':
        return cls(**data)


class QueueManager:
    """
    Priority-based queue manager for project scheduling.
    
    Features:
    - Priority-based ordering
    - FIFO within same priority
    - Queue persistence
    - Queue statistics
    """
    
    def __init__(self, products_dir: str = "products"):
        """
        Initialize queue manager.
        
        Args:
            products_dir: Path to products directory
        """
        self.products_dir = Path(products_dir)
        self.queue_path = self.products_dir / "queue.json"
        self._ensure_queue()
    
    def _ensure_queue(self):
        """Ensure queue file exists"""
        if not self.queue_path.exists():
            self._save_queue([])
    
    def _load_queue(self) -> List[Dict[str, Any]]:
        """Load queue from file"""
        if self.queue_path.exists():
            with open(self.queue_path, 'r') as f:
                return json.load(f)
        return []
    
    def _save_queue(self, queue: List[Dict[str, Any]]):
        """Save queue to file"""
        # Atomic write
        temp_path = self.queue_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w') as f:
                json.dump(queue, f, indent=2)
            temp_path.replace(self.queue_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise Exception(f"Failed to save queue: {e}")
    
    def enqueue(
        self,
        project: str,
        priority: Priority = Priority.NORMAL,
        reason: Optional[str] = None,
        estimated_duration_minutes: Optional[int] = None
    ) -> bool:
        """
        Add project to queue.
        
        Args:
            project: Project name
            priority: Priority level
            reason: Optional reason for queuing
            estimated_duration_minutes: Estimated execution time
            
        Returns:
            True if added successfully
        """
        queue = self._load_queue()
        
        # Check if already in queue
        if any(item["project"] == project for item in queue):
            return False
        
        item = QueueItem(
            project=project,
            priority=priority.value,
            queued_at=datetime.now().isoformat(),
            reason=reason,
            estimated_duration_minutes=estimated_duration_minutes
        )
        
        queue.append(item.to_dict())
        
        # Sort by priority (lower number = higher priority)
        queue.sort(key=lambda x: (x["priority"], x["queued_at"]))
        
        self._save_queue(queue)
        return True
    
    def dequeue(self, project: str) -> Optional[QueueItem]:
        """
        Remove project from queue.
        
        Args:
            project: Project name
            
        Returns:
            Removed QueueItem if found, None otherwise
        """
        queue = self._load_queue()
        
        for i, item in enumerate(queue):
            if item["project"] == project:
                removed = queue.pop(i)
                self._save_queue(queue)
                return QueueItem.from_dict(removed)
        
        return None
    
    def get_next(self) -> Optional[QueueItem]:
        """
        Get next project to execute.
        
        Returns:
            Next QueueItem or None if queue is empty
        """
        queue = self._load_queue()
        
        if not queue:
            return None
        
        return QueueItem.from_dict(queue[0])
    
    def get_queue(self) -> List[QueueItem]:
        """
        Get all items in queue.
        
        Returns:
            List of QueueItems
        """
        queue = self._load_queue()
        return [QueueItem.from_dict(item) for item in queue]
    
    def get_queue_size(self) -> int:
        """
        Get queue size.
        
        Returns:
            Number of items in queue
        """
        return len(self._load_queue())
    
    def is_in_queue(self, project: str) -> bool:
        """
        Check if project is in queue.
        
        Args:
            project: Project name
            
        Returns:
            True if in queue
        """
        queue = self._load_queue()
        return any(item["project"] == project for item in queue)
    
    def clear_queue(self) -> int:
        """
        Clear all items from queue.
        
        Returns:
            Number of items removed
        """
        queue = self._load_queue()
        count = len(queue)
        self._save_queue([])
        return count
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Returns:
            Queue statistics
        """
        queue = self._load_queue()
        
        by_priority = {}
        for item in queue:
            priority = item["priority"]
            by_priority[priority] = by_priority.get(priority, 0) + 1
        
        return {
            "total": len(queue),
            "by_priority": by_priority,
            "oldest_item": queue[0]["queued_at"] if queue else None,
            "newest_item": queue[-1]["queued_at"] if queue else None
        }
