"""
Dead Letter Queue - Captures failed tasks
"""
import time
import json
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum

class DLQStatus(Enum):
    PENDING = "pending"
    RETRYING = "retrying"
    RESOLVED = "resolved"
    FAILED = "failed"

@dataclass
class DLQItem:
    item_id: str
    task: str
    agent: str
    stage: int
    error: str
    timestamp: str
    status: str
    retry_count: int
    max_retries: int

class DeadLetterQueue:
    """Dead Letter Queue for failed tasks"""
    
    def __init__(self, project: str, max_retries: int = 3):
        self.project = project
        self.max_retries = max_retries
        self.dlq_file = Path(__file__).parent.parent / "products" / project / "dead-letter-queue.json"
        self.items: List[DLQItem] = self._load_items()
    
    def _load_items(self) -> List[DLQItem]:
        if self.dlq_file.exists():
            with open(self.dlq_file) as f:
                data = json.load(f)
                return [DLQItem(**item) for item in data]
        return []
    
    def _save_items(self):
        with open(self.dlq_file, 'w') as f:
            json.dump([asdict(item) for item in self.items], f, indent=2)
    
    def add_item(self, task: str, agent: str, stage: int, error: str) -> DLQItem:
        """Add item to DLQ"""
        item = DLQItem(
            item_id=f"DLQ-{len(self.items)+1:04d}",
            task=task,
            agent=agent,
            stage=stage,
            error=error,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            status=DLQStatus.PENDING.value,
            retry_count=0,
            max_retries=self.max_retries
        )
        self.items.append(item)
        self._save_items()
        return item
    
    def get_item(self, item_id: str) -> Optional[DLQItem]:
        """Get item by ID"""
        for item in self.items:
            if item.item_id == item_id:
                return item
        return None
    
    def can_retry(self, item_id: str) -> bool:
        """Check if item can be retried"""
        item = self.get_item(item_id)
        if item and item.retry_count < item.max_retries:
            return True
        return False
    
    def retry_item(self, item_id: str) -> bool:
        """Retry item"""
        item = self.get_item(item_id)
        if item and item.retry_count < item.max_retries:
            item.retry_count += 1
            item.status = DLQStatus.RETRYING.value
            self._save_items()
            return True
        return False
    
    def resolve_item(self, item_id: str):
        """Mark item as resolved"""
        item = self.get_item(item_id)
        if item:
            item.status = DLQStatus.RESOLVED.value
            self._save_items()
    
    def fail_item(self, item_id: str):
        """Mark item as failed"""
        item = self.get_item(item_id)
        if item:
            item.status = DLQStatus.FAILED.value
            self._save_items()
    
    def get_pending(self) -> List[DLQItem]:
        """Get pending items"""
        return [item for item in self.items if item.status in (DLQStatus.PENDING.value, DLQStatus.RETRYING.value)]
    
    def get_failed(self) -> List[DLQItem]:
        """Get failed items"""
        return [item for item in self.items if item.status == DLQStatus.FAILED.value]
    
    def get_stats(self) -> Dict[str, int]:
        """Get DLQ statistics"""
        return {
            "total": len(self.items),
            "pending": len([i for i in self.items if i.status == DLQStatus.PENDING.value]),
            "retrying": len([i for i in self.items if i.status == DLQStatus.RETRYING.value]),
            "resolved": len([i for i in self.items if i.status == DLQStatus.RESOLVED.value]),
            "failed": len([i for i in self.items if i.status == DLQStatus.FAILED.value])
        }
    
    def clear_resolved(self):
        """Clear resolved items"""
        self.items = [item for item in self.items if item.status != DLQStatus.RESOLVED.value]
        self._save_items()
