"""
Lock Manager - Prevents concurrent execution of the same project.

Phase 1.2 (CRITICAL): Multi-project parallel execution support.
"""
import json
import fcntl
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


class LockManager:
    """File-based lock manager for project execution."""
    
    LOCK_DIR_NAME = ".locks"
    DEFAULT_TIMEOUT = 30  # seconds
    STALE_LOCK_HOURS = 2
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.lock_dir = self.products_dir / self.LOCK_DIR_NAME
        self.lock_dir.mkdir(parents=True, exist_ok=True)
    
    def acquire(self, project: str, holder: str = "pipeline", timeout: int = DEFAULT_TIMEOUT) -> bool:
        """
        Acquire a lock for a project.
        
        Args:
            project: Project name
            holder: Identifier of the lock holder
            timeout: Seconds to wait for lock
        
        Returns:
            True if lock acquired, False otherwise
        """
        lock_file = self.lock_dir / f"{project}.lock"
        
        # Check for stale lock
        if lock_file.exists():
            try:
                lock_data = json.loads(lock_file.read_text())
                locked_at = datetime.fromisoformat(lock_data["locked_at"])
                if datetime.utcnow() - locked_at > timedelta(hours=self.STALE_LOCK_HOURS):
                    # Stale lock, remove it
                    lock_file.unlink()
            except (json.JSONDecodeError, KeyError, ValueError):
                # Corrupted lock, remove it
                lock_file.unlink()
        
        # Try to acquire lock
        start = time.time()
        while time.time() - start < timeout:
            try:
                with open(lock_file, 'x') as f:
                    lock_data = {
                        "project": project,
                        "holder": holder,
                        "locked_at": datetime.utcnow().isoformat(),
                        "pid": os.getpid(),
                    }
                    json.dump(lock_data, f, indent=2)
                return True
            except FileExistsError:
                # Lock exists, wait and retry
                time.sleep(0.5)
        
        return False
    
    def release(self, project: str) -> bool:
        """
        Release a lock for a project.
        
        Args:
            project: Project name
        
        Returns:
            True if lock released, False if no lock existed
        """
        lock_file = self.lock_dir / f"{project}.lock"
        
        if not lock_file.exists():
            return False
        
        try:
            lock_file.unlink()
            return True
        except OSError:
            return False
    
    def is_locked(self, project: str) -> bool:
        """Check if a project is currently locked."""
        return (self.lock_dir / f"{project}.lock").exists()
    
    def get_lock_info(self, project: str) -> Optional[dict]:
        """Get information about an existing lock."""
        lock_file = self.lock_dir / f"{project}.lock"
        
        if not lock_file.exists():
            return None
        
        try:
            return json.loads(lock_file.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    
    def force_release(self, project: str) -> bool:
        """Force release a lock (admin operation)."""
        return self.release(project)
    
    def list_locks(self) -> list[dict]:
        """List all current locks."""
        locks = []
        for lock_file in self.lock_dir.glob("*.lock"):
            try:
                lock_data = json.loads(lock_file.read_text())
                locks.append(lock_data)
            except (json.JSONDecodeError, OSError):
                continue
        return locks
