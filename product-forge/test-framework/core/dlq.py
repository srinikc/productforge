"""
Dead Letter Queue - Handles failed operations for later retry.

Phase 1.3 (CRITICAL): Dead Letter Queue for failed pipeline operations.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict, field
from enum import Enum


class DLQStatus(str, Enum):
    """Status of a DLQ item."""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    RETRY_SCHEDULED = "retry_scheduled"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


@dataclass
class DLQItem:
    """An item in the dead letter queue."""
    id: str
    project: str
    stage: int
    stage_name: str
    agent: str
    error: str
    error_type: str
    input_data: dict
    attempts: int
    created_at: str
    last_retry_at: Optional[str] = None
    status: str = DLQStatus.PENDING.value
    metadata: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


class DeadLetterQueue:
    """Manages failed operations for later analysis and retry."""
    
    DLQ_DIR = "dlq"
    
    def __init__(self, project: str, products_dir: str = "products"):
        self.project = project
        self.products_dir = Path(products_dir)
        self.dlq_dir = self.products_dir / project / self.DLQ_DIR
        self.dlq_dir.mkdir(parents=True, exist_ok=True)
    
    def add(
        self,
        stage: int,
        stage_name: str,
        agent: str,
        error: str,
        error_type: str = "unknown",
        input_data: Optional[dict] = None,
        attempts: int = 1,
        metadata: Optional[dict] = None,
    ) -> DLQItem:
        """
        Add a failed operation to the DLQ.
        
        Args:
            stage: Stage number where failure occurred
            stage_name: Stage name
            agent: Agent that failed
            error: Error message
            error_type: Type/category of error
            input_data: Input that caused the failure
            attempts: Number of attempts made
            metadata: Optional metadata
        
        Returns:
            Created DLQ item
        """
        item_id = f"dlq_{stage}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        
        item = DLQItem(
            id=item_id,
            project=self.project,
            stage=stage,
            stage_name=stage_name,
            agent=agent,
            error=error,
            error_type=error_type,
            input_data=input_data or {},
            attempts=attempts,
            created_at=datetime.utcnow().isoformat(),
            metadata=metadata or {},
        )
        
        # Save to file
        self._save_item(item)
        return item
    
    def get(self, item_id: str) -> Optional[DLQItem]:
        """Get a DLQ item by ID."""
        item_file = self.dlq_dir / f"{item_id}.json"
        
        if not item_file.exists():
            return None
        
        try:
            return DLQItem(**json.loads(item_file.read_text()))
        except (json.JSONDecodeError, OSError, TypeError):
            return None
    
    def list_items(
        self,
        status: Optional[str] = None,
        stage: Optional[int] = None,
        agent: Optional[str] = None,
    ) -> list[DLQItem]:
        """List DLQ items with optional filters."""
        items = []
        
        for item_file in self.dlq_dir.glob("dlq_*.json"):
            try:
                data = json.loads(item_file.read_text())
                item = DLQItem(**data)
                
                if status and item.status != status:
                    continue
                if stage is not None and item.stage != stage:
                    continue
                if agent and item.agent != agent:
                    continue
                
                items.append(item)
            except (json.JSONDecodeError, OSError, TypeError):
                continue
        
        return sorted(items, key=lambda x: x.created_at, reverse=True)
    
    def update_status(
        self,
        item_id: str,
        status: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Update the status of a DLQ item."""
        item = self.get(item_id)
        if not item:
            return False
        
        item.status = status
        if notes:
            item.notes.append({
                "timestamp": datetime.utcnow().isoformat(),
                "text": notes,
            })
        
        self._save_item(item)
        return True
    
    def mark_retry(self, item_id: str) -> bool:
        """Mark a DLQ item as retried."""
        item = self.get(item_id)
        if not item:
            return False
        
        item.last_retry_at = datetime.utcnow().isoformat()
        item.status = DLQStatus.RETRY_SCHEDULED.value
        self._save_item(item)
        return True
    
    def resolve(self, item_id: str, notes: Optional[str] = None) -> bool:
        """Mark a DLQ item as resolved."""
        return self.update_status(item_id, DLQStatus.RESOLVED.value, notes)
    
    def abandon(self, item_id: str, notes: Optional[str] = None) -> bool:
        """Abandon a DLQ item (won't be retried)."""
        return self.update_status(item_id, DLQStatus.ABANDONED.value, notes)
    
    def delete(self, item_id: str) -> bool:
        """Delete a DLQ item."""
        item_file = self.dlq_dir / f"{item_id}.json"
        
        if not item_file.exists():
            return False
        
        try:
            item_file.unlink()
            return True
        except OSError:
            return False
    
    def get_stats(self) -> dict:
        """Get DLQ statistics."""
        items = self.list_items()
        
        return {
            "total": len(items),
            "pending": sum(1 for i in items if i.status == DLQStatus.PENDING.value),
            "in_review": sum(1 for i in items if i.status == DLQStatus.IN_REVIEW.value),
            "retry_scheduled": sum(1 for i in items if i.status == DLQStatus.RETRY_SCHEDULED.value),
            "resolved": sum(1 for i in items if i.status == DLQStatus.RESOLVED.value),
            "abandoned": sum(1 for i in items if i.status == DLQStatus.ABANDONED.value),
            "by_stage": self._count_by_field(items, "stage"),
            "by_agent": self._count_by_field(items, "agent"),
            "by_error_type": self._count_by_field(items, "error_type"),
        }
    
    def _count_by_field(self, items: list[DLQItem], field: str) -> dict:
        """Count items grouped by a field."""
        counts = {}
        for item in items:
            value = getattr(item, field, "unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts
    
    def _save_item(self, item: DLQItem) -> None:
        """Save a DLQ item to disk."""
        item_file = self.dlq_dir / f"{item.id}.json"
        item_file.write_text(json.dumps(asdict(item), indent=2, default=str))
