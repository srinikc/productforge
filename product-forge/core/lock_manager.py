"""
Lock Manager
File-based execution locking with TTL for concurrent multi-project support
"""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta


@dataclass
class LockInfo:
    """Lock information"""
    holder: str  # Session ID or process ID
    acquired_at: str  # ISO timestamp
    expires_at: str  # ISO timestamp
    project: str
    run_id: str
    ttl_seconds: int = 3600  # Default 1 hour
    
    def is_expired(self) -> bool:
        """Check if lock has expired"""
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.now() > expires
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LockInfo':
        """Create from dictionary"""
        return cls(**data)


class LockManager:
    """
    File-based lock manager for concurrent multi-project execution.
    
    Features:
    - Atomic lock acquisition using temp-file-then-rename
    - TTL-based lock expiration
    - Stale lock detection and cleanup
    - Per-project isolation
    """
    
    def __init__(self, products_dir: str = "products"):
        """
        Initialize lock manager.
        
        Args:
            products_dir: Path to products directory
        """
        self.products_dir = Path(products_dir)
        self.locks_dir = self.products_dir / ".locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_lock_path(self, project: str) -> Path:
        """Get lock file path for project"""
        return self.locks_dir / f"{project}.lock"
    
    def _get_session_id(self) -> str:
        """Generate unique session ID"""
        return f"{uuid.uuid4().hex[:12]}"
    
    def acquire_lock(
        self, 
        project: str, 
        holder: Optional[str] = None,
        ttl_seconds: int = 3600,
        run_id: Optional[str] = None
    ) -> Optional[LockInfo]:
        """
        Acquire execution lock for a project.
        
        Args:
            project: Project name
            holder: Lock holder identifier (default: generated session ID)
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
            run_id: Optional run identifier
            
        Returns:
            LockInfo if successful, None if lock is held by another process
            
        Raises:
            Exception: If lock acquisition fails
        """
        lock_path = self._get_lock_path(project)
        
        # Check if lock exists and is valid
        if lock_path.exists():
            try:
                with open(lock_path, 'r') as f:
                    lock_data = json.load(f)
                existing_lock = LockInfo.from_dict(lock_data)
                
                # If lock is not expired, check if it's held by same process
                if not existing_lock.is_expired():
                    if holder and existing_lock.holder == holder:
                        # Same holder, refresh lock
                        return self._refresh_lock(project, holder, ttl_seconds, run_id)
                    # Different holder, lock is held
                    return None
                else:
                    # Lock is expired, clean it up
                    self._remove_lock(project)
            except (json.JSONDecodeError, KeyError):
                # Corrupted lock file, remove it
                self._remove_lock(project)
        
        # Create new lock
        now = datetime.now()
        expires = now + timedelta(seconds=ttl_seconds)
        
        lock_info = LockInfo(
            holder=holder or self._get_session_id(),
            acquired_at=now.isoformat(),
            expires_at=expires.isoformat(),
            project=project,
            run_id=run_id or self._get_session_id(),
            ttl_seconds=ttl_seconds
        )
        
        # Atomic write: write to temp file, then rename
        temp_path = lock_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w') as f:
                json.dump(lock_info.to_dict(), f, indent=2)
            
            # Atomic rename (on same filesystem)
            temp_path.rename(lock_path)
            return lock_info
        except Exception as e:
            # Clean up temp file on failure
            if temp_path.exists():
                temp_path.unlink()
            raise Exception(f"Failed to acquire lock for {project}: {e}")
    
    def _refresh_lock(
        self, 
        project: str, 
        holder: str, 
        ttl_seconds: int,
        run_id: Optional[str] = None
    ) -> LockInfo:
        """Refresh an existing lock held by the same process"""
        lock_path = self._get_lock_path(project)
        
        now = datetime.now()
        expires = now + timedelta(seconds=ttl_seconds)
        
        lock_info = LockInfo(
            holder=holder,
            acquired_at=now.isoformat(),
            expires_at=expires.isoformat(),
            project=project,
            run_id=run_id or self._get_session_id(),
            ttl_seconds=ttl_seconds
        )
        
        temp_path = lock_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w') as f:
                json.dump(lock_info.to_dict(), f, indent=2)
            # On Windows, rename doesn't overwrite, so remove target first
            if lock_path.exists():
                lock_path.unlink()
            temp_path.rename(lock_path)
            return lock_info
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise Exception(f"Failed to refresh lock for {project}: {e}")
    
    def release_lock(self, project: str, holder: str) -> bool:
        """
        Release execution lock for a project.
        
        Args:
            project: Project name
            holder: Lock holder identifier (must match acquired holder)
            
        Returns:
            True if lock was released, False if not held by this holder
        """
        lock_path = self._get_lock_path(project)
        
        if not lock_path.exists():
            return False
        
        try:
            with open(lock_path, 'r') as f:
                lock_data = json.load(f)
            existing_lock = LockInfo.from_dict(lock_data)
            
            if existing_lock.holder != holder:
                return False
            
            self._remove_lock(project)
            return True
        except (json.JSONDecodeError, KeyError):
            self._remove_lock(project)
            return False
    
    def _remove_lock(self, project: str):
        """Remove lock file"""
        lock_path = self._get_lock_path(project)
        if lock_path.exists():
            lock_path.unlink()
    
    def is_locked(self, project: str) -> bool:
        """
        Check if a project is locked.
        
        Args:
            project: Project name
            
        Returns:
            True if project is locked (and lock is not expired)
        """
        lock_path = self._get_lock_path(project)
        
        if not lock_path.exists():
            return False
        
        try:
            with open(lock_path, 'r') as f:
                lock_data = json.load(f)
            lock_info = LockInfo.from_dict(lock_data)
            return not lock_info.is_expired()
        except (json.JSONDecodeError, KeyError):
            return False
    
    def get_lock_info(self, project: str) -> Optional[LockInfo]:
        """
        Get lock information for a project.
        
        Args:
            project: Project name
            
        Returns:
            LockInfo if locked, None otherwise
        """
        lock_path = self._get_lock_path(project)
        
        if not lock_path.exists():
            return None
        
        try:
            with open(lock_path, 'r') as f:
                lock_data = json.load(f)
            lock_info = LockInfo.from_dict(lock_data)
            if lock_info.is_expired():
                self._remove_lock(project)
                return None
            return lock_info
        except (json.JSONDecodeError, KeyError):
            self._remove_lock(project)
            return None
    
    def get_all_locks(self) -> Dict[str, LockInfo]:
        """
        Get all active locks.
        
        Returns:
            Dictionary of project -> LockInfo
        """
        locks = {}
        
        for lock_file in self.locks_dir.glob("*.lock"):
            project = lock_file.stem
            lock_info = self.get_lock_info(project)
            if lock_info:
                locks[project] = lock_info
        
        return locks
    
    def cleanup_stale_locks(self) -> int:
        """
        Clean up all expired locks.
        
        Returns:
            Number of stale locks removed
        """
        removed = 0
        
        for lock_file in self.locks_dir.glob("*.lock"):
            project = lock_file.stem
            lock_info = self.get_lock_info(project)
            if lock_info is None:  # Expired or corrupted
                self._remove_lock(project)
                removed += 1
        
        return removed
    
    def extend_lock(self, project: str, holder: str, additional_seconds: int) -> Optional[LockInfo]:
        """
        Extend lock TTL.
        
        Args:
            project: Project name
            holder: Lock holder identifier
            additional_seconds: Additional seconds to extend
            
        Returns:
            Updated LockInfo if successful, None otherwise
        """
        lock_path = self._get_lock_path(project)
        
        if not lock_path.exists():
            return None
        
        try:
            with open(lock_path, 'r') as f:
                lock_data = json.load(f)
            existing_lock = LockInfo.from_dict(lock_data)
            
            if existing_lock.holder != holder:
                return None
            
            # Extend expiration
            expires = datetime.fromisoformat(existing_lock.expires_at) + timedelta(seconds=additional_seconds)
            
            lock_info = LockInfo(
                holder=holder,
                acquired_at=existing_lock.acquired_at,
                expires_at=expires.isoformat(),
                project=project,
                run_id=existing_lock.run_id,
                ttl_seconds=existing_lock.ttl_seconds + additional_seconds
            )
            
            temp_path = lock_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(lock_info.to_dict(), f, indent=2)
            # On Windows, rename doesn't overwrite, so remove target first
            if lock_path.exists():
                lock_path.unlink()
            temp_path.rename(lock_path)
            
            return lock_info
        except (json.JSONDecodeError, KeyError):
            return None
