"""
Lock Manager Tests
Tests for file-based execution locking
"""

import pytest
import json
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.lock_manager import LockManager, LockInfo


class TestLockManager:
    """Test suite for LockManager"""
    
    def test_acquire_lock(self, temp_products_dir, sample_project):
        """Test acquiring a lock on a project"""
        manager = LockManager(str(temp_products_dir))
        
        lock = manager.acquire_lock(
            sample_project,
            holder="test-session",
            ttl_seconds=3600
        )
        
        assert lock is not None
        assert lock.holder == "test-session"
        assert lock.project == sample_project
        assert not lock.is_expired()
    
    def test_lock_already_held(self, temp_products_dir, sample_project):
        """Test that lock cannot be acquired when already held"""
        manager = LockManager(str(temp_products_dir))
        
        # First acquisition
        lock1 = manager.acquire_lock(
            sample_project,
            holder="session-1",
            ttl_seconds=3600
        )
        assert lock1 is not None
        
        # Second acquisition should fail
        lock2 = manager.acquire_lock(
            sample_project,
            holder="session-2",
            ttl_seconds=3600
        )
        assert lock2 is None
    
    def test_same_holder_can_refresh(self, temp_products_dir, sample_project):
        """Test that same holder can refresh lock"""
        manager = LockManager(str(temp_products_dir))
        
        # First acquisition
        lock1 = manager.acquire_lock(
            sample_project,
            holder="same-session",
            ttl_seconds=3600
        )
        assert lock1 is not None
        
        # Refresh by same holder
        lock2 = manager.acquire_lock(
            sample_project,
            holder="same-session",
            ttl_seconds=3600
        )
        assert lock2 is not None
        assert lock2.holder == "same-session"
    
    def test_release_lock(self, temp_products_dir, sample_project):
        """Test releasing a lock"""
        manager = LockManager(str(temp_products_dir))
        
        # Acquire lock
        lock = manager.acquire_lock(
            sample_project,
            holder="test-session",
            ttl_seconds=3600
        )
        assert lock is not None
        
        # Release lock
        released = manager.release_lock(sample_project, "test-session")
        assert released is True
        
        # Verify lock is released
        assert not manager.is_locked(sample_project)
    
    def test_release_lock_wrong_holder(self, temp_products_dir, sample_project):
        """Test that wrong holder cannot release lock"""
        manager = LockManager(str(temp_products_dir))
        
        # Acquire lock
        lock = manager.acquire_lock(
            sample_project,
            holder="session-1",
            ttl_seconds=3600
        )
        assert lock is not None
        
        # Try to release with wrong holder
        released = manager.release_lock(sample_project, "session-2")
        assert released is False
        
        # Verify lock is still held
        assert manager.is_locked(sample_project)
    
    def test_lock_expiration(self, temp_products_dir, sample_project):
        """Test lock expiration"""
        manager = LockManager(str(temp_products_dir))
        
        # Acquire lock with very short TTL
        lock = manager.acquire_lock(
            sample_project,
            holder="test-session",
            ttl_seconds=1  # 1 second
        )
        assert lock is not None
        assert manager.is_locked(sample_project)
        
        # Wait for expiration
        time.sleep(2)
        
        # Verify lock is expired
        assert not manager.is_locked(sample_project)
    
    def test_get_lock_info(self, temp_products_dir, sample_project):
        """Test getting lock information"""
        manager = LockManager(str(temp_products_dir))
        
        # Acquire lock
        lock = manager.acquire_lock(
            sample_project,
            holder="test-session",
            ttl_seconds=3600
        )
        
        # Get lock info
        info = manager.get_lock_info(sample_project)
        assert info is not None
        assert info.holder == "test-session"
        assert info.project == sample_project
    
    def test_get_all_locks(self, temp_products_dir, multiple_projects):
        """Test getting all active locks"""
        manager = LockManager(str(temp_products_dir))
        
        # Acquire locks for multiple projects
        for project in multiple_projects:
            manager.acquire_lock(
                project,
                holder=f"session-{project}",
                ttl_seconds=3600
            )
        
        # Get all locks
        all_locks = manager.get_all_locks()
        assert len(all_locks) == len(multiple_projects)
    
    def test_cleanup_stale_locks(self, temp_products_dir, sample_project):
        """Test cleaning up stale locks"""
        manager = LockManager(str(temp_products_dir))
        
        # Acquire lock with short TTL
        manager.acquire_lock(
            sample_project,
            holder="test-session",
            ttl_seconds=1
        )
        
        # Wait for expiration
        time.sleep(2)
        
        # Cleanup stale locks
        removed = manager.cleanup_stale_locks()
        assert removed >= 1
    
    def test_extend_lock(self, temp_products_dir, sample_project):
        """Test extending lock TTL"""
        manager = LockManager(str(temp_products_dir))
        
        # Acquire lock
        lock = manager.acquire_lock(
            sample_project,
            holder="test-session",
            ttl_seconds=60
        )
        
        # Extend lock
        extended = manager.extend_lock(
            sample_project,
            "test-session",
            additional_seconds=3600
        )
        
        assert extended is not None
        assert extended.ttl_seconds == 60 + 3600


class TestLockInfo:
    """Test suite for LockInfo dataclass"""
    
    def test_lock_info_creation(self):
        """Test LockInfo creation"""
        lock = LockInfo(
            holder="test-session",
            acquired_at="2024-01-01T00:00:00",
            expires_at="2099-12-31T23:59:59",
            project="test-project",
            run_id="run-123",
            ttl_seconds=3600
        )
        
        assert lock.holder == "test-session"
        assert lock.project == "test-project"
        assert not lock.is_expired()
    
    def test_lock_info_expiration(self):
        """Test LockInfo expiration check"""
        lock = LockInfo(
            holder="test-session",
            acquired_at="2024-01-01T00:00:00",
            expires_at="2024-01-01T00:00:01",  # Already expired
            project="test-project",
            run_id="run-123",
            ttl_seconds=1
        )
        
        assert lock.is_expired()
    
    def test_lock_info_serialization(self):
        """Test LockInfo serialization"""
        lock = LockInfo(
            holder="test-session",
            acquired_at="2024-01-01T00:00:00",
            expires_at="2099-12-31T23:59:59",
            project="test-project",
            run_id="run-123",
            ttl_seconds=3600
        )
        
        # Convert to dict
        data = lock.to_dict()
        assert data["holder"] == "test-session"
        assert data["project"] == "test-project"
        
        # Create from dict
        restored = LockInfo.from_dict(data)
        assert restored.holder == lock.holder
        assert restored.project == lock.project
