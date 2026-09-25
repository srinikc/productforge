"""
Queue Manager Tests
Tests for priority-based project scheduling
"""

import pytest
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.queue_manager import QueueManager, QueueItem, Priority


class TestQueueManager:
    """Test suite for QueueManager"""
    
    def test_enqueue(self, temp_products_dir, sample_project):
        """Test adding project to queue"""
        qm = QueueManager(str(temp_products_dir))
        
        result = qm.enqueue(
            sample_project,
            priority=Priority.NORMAL,
            reason="Testing queue"
        )
        
        assert result is True
        assert qm.is_in_queue(sample_project)
    
    def test_enqueue_duplicate(self, temp_products_dir, sample_project):
        """Test that duplicate enqueue fails"""
        qm = QueueManager(str(temp_products_dir))
        
        qm.enqueue(sample_project)
        result = qm.enqueue(sample_project)
        
        assert result is False
    
    def test_dequeue(self, temp_products_dir, sample_project):
        """Test removing project from queue"""
        qm = QueueManager(str(temp_products_dir))
        
        qm.enqueue(sample_project)
        removed = qm.dequeue(sample_project)
        
        assert removed is not None
        assert removed.project == sample_project
        assert not qm.is_in_queue(sample_project)
    
    def test_get_next(self, temp_products_dir, multiple_projects):
        """Test getting next project from queue"""
        qm = QueueManager(str(temp_products_dir))
        
        # Enqueue with different priorities
        for i, project in enumerate(multiple_projects):
            qm.enqueue(
                project,
                priority=Priority(i)  # CRITICAL, HIGH, NORMAL
            )
        
        # Get next should return CRITICAL priority
        next_item = qm.get_next()
        assert next_item is not None
        assert next_item.priority == Priority.CRITICAL.value
    
    def test_priority_ordering(self, temp_products_dir):
        """Test that queue respects priority ordering"""
        qm = QueueManager(str(temp_products_dir))
        
        # Enqueue in reverse priority order
        qm.enqueue("low-project", priority=Priority.LOW)
        qm.enqueue("high-project", priority=Priority.HIGH)
        qm.enqueue("normal-project", priority=Priority.NORMAL)
        qm.enqueue("critical-project", priority=Priority.CRITICAL)
        
        # Get next should return CRITICAL
        next_item = qm.get_next()
        assert next_item.project == "critical-project"
        
        # Remove and get next should return HIGH
        qm.dequeue("critical-project")
        next_item = qm.get_next()
        assert next_item.project == "high-project"
    
    def test_get_queue(self, temp_products_dir, multiple_projects):
        """Test getting full queue"""
        qm = QueueManager(str(temp_products_dir))
        
        for project in multiple_projects:
            qm.enqueue(project)
        
        queue = qm.get_queue()
        assert len(queue) == len(multiple_projects)
    
    def test_get_queue_size(self, temp_products_dir, multiple_projects):
        """Test getting queue size"""
        qm = QueueManager(str(temp_products_dir))
        
        for project in multiple_projects:
            qm.enqueue(project)
        
        size = qm.get_queue_size()
        assert size == len(multiple_projects)
    
    def test_clear_queue(self, temp_products_dir, multiple_projects):
        """Test clearing queue"""
        qm = QueueManager(str(temp_products_dir))
        
        for project in multiple_projects:
            qm.enqueue(project)
        
        removed = qm.clear_queue()
        assert removed == len(multiple_projects)
        assert qm.get_queue_size() == 0
    
    def test_get_statistics(self, temp_products_dir):
        """Test queue statistics"""
        qm = QueueManager(str(temp_products_dir))
        
        qm.enqueue("project-1", priority=Priority.NORMAL)
        qm.enqueue("project-2", priority=Priority.HIGH)
        qm.enqueue("project-3", priority=Priority.NORMAL)
        
        stats = qm.get_statistics()
        
        assert stats["total"] == 3
        assert stats["by_priority"][Priority.NORMAL.value] == 2
        assert stats["by_priority"][Priority.HIGH.value] == 1


class TestQueueItem:
    """Test suite for QueueItem dataclass"""
    
    def test_queue_item_creation(self):
        """Test QueueItem creation"""
        item = QueueItem(
            project="test-project",
            priority=Priority.NORMAL.value,
            queued_at="2024-01-01T00:00:00",
            reason="Testing",
            estimated_duration_minutes=30
        )
        
        assert item.project == "test-project"
        assert item.priority == Priority.NORMAL.value
    
    def test_queue_item_serialization(self):
        """Test QueueItem serialization"""
        item = QueueItem(
            project="test-project",
            priority=Priority.NORMAL.value,
            queued_at="2024-01-01T00:00:00",
            reason="Testing",
            estimated_duration_minutes=30
        )
        
        data = item.to_dict()
        assert data["project"] == "test-project"
        
        restored = QueueItem.from_dict(data)
        assert restored.project == item.project
        assert restored.priority == item.priority
