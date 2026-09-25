"""
Write Safety
Atomic file operations for concurrent multi-project execution
"""

import json
import os
import platform
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
from contextlib import contextmanager

if platform.system() != "Windows":
    import fcntl
else:
    import msvcrt


class WriteSafety:
    """
    Safe file write operations for concurrent access.
    
    Features:
    - Atomic writes using temp-file-then-rename
    - File locking for critical files
    - Backup before write
    - Rollback on failure
    """
    
    def __init__(self, products_dir: str = "products"):
        """
        Initialize write safety.
        
        Args:
            products_dir: Path to products directory
        """
        self.products_dir = Path(products_dir)
    
    @contextmanager
    def file_lock(self, file_path: Path, timeout: int = 30):
        """
        Context manager for file locking.
        
        Args:
            file_path: Path to file to lock
            timeout: Lock timeout in seconds
            
        Yields:
            None (lock is held during context)
        """
        lock_path = file_path.with_suffix('.lock')
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        
        lock_file = open(lock_path, 'w')
        try:
            # Try to acquire lock with timeout
            import time
            start_time = time.time()
            
            while True:
                try:
                    # Windows locking
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except IOError:
                    if time.time() - start_time > timeout:
                        raise TimeoutError(f"Could not acquire lock on {file_path}")
                    time.sleep(0.1)
            
            yield
            
        finally:
            try:
                # Release lock
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            except:
                pass
            lock_file.close()
            if lock_path.exists():
                lock_path.unlink()
    
    def atomic_write_json(
        self, 
        file_path: Path, 
        data: Dict[str, Any],
        backup: bool = True
    ) -> bool:
        """
        Atomically write JSON file.
        
        Args:
            file_path: Target file path
            data: Data to write
            backup: Create backup before write
            
        Returns:
            True if successful
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create backup if requested
        backup_path = None
        if backup and file_path.exists():
            backup_path = file_path.with_suffix('.bak')
            shutil.copy2(file_path, backup_path)
        
        # Write to temp file first
        temp_path = file_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            temp_path.replace(file_path)
            return True
            
        except Exception as e:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
            
            # Restore from backup on failure
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, file_path)
            
            raise Exception(f"Failed to write {file_path}: {e}")
        
        finally:
            # Clean up backup
            if backup_path and backup_path.exists():
                backup_path.unlink()
    
    def atomic_write_text(
        self, 
        file_path: Path, 
        content: str,
        backup: bool = True
    ) -> bool:
        """
        Atomically write text file.
        
        Args:
            file_path: Target file path
            content: Content to write
            backup: Create backup before write
            
        Returns:
            True if successful
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create backup if requested
        backup_path = None
        if backup and file_path.exists():
            backup_path = file_path.with_suffix('.bak')
            shutil.copy2(file_path, backup_path)
        
        # Write to temp file first
        temp_path = file_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Atomic rename
            temp_path.replace(file_path)
            return True
            
        except Exception as e:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
            
            # Restore from backup on failure
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, file_path)
            
            raise Exception(f"Failed to write {file_path}: {e}")
        
        finally:
            # Clean up backup
            if backup_path and backup_path.exists():
                backup_path.unlink()
    
    def safe_update_json(
        self,
        file_path: Path,
        updater: callable,
        backup: bool = True
    ) -> Dict[str, Any]:
        """
        Safely update JSON file with function.
        
        Args:
            file_path: Target file path
            updater: Function that takes current data and returns updated data
            backup: Create backup before write
            
        Returns:
            Updated data
        """
        with self.file_lock(file_path):
            # Read current data
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_data = json.load(f)
            else:
                current_data = {}
            
            # Apply updater
            updated_data = updater(current_data)
            
            # Write atomically
            self.atomic_write_json(file_path, updated_data, backup)
            
            return updated_data
    
    def safe_append_json(
        self,
        file_path: Path,
        item: Any,
        list_key: Optional[str] = None
    ) -> bool:
        """
        Safely append item to JSON array.
        
        Args:
            file_path: Target file path
            item: Item to append
            list_key: Key containing the array (None for root array)
            
        Returns:
            True if successful
        """
        def updater(data):
            if list_key:
                if list_key not in data:
                    data[list_key] = []
                data[list_key].append(item)
            else:
                if not isinstance(data, list):
                    data = []
                data.append(item)
            return data
        
        self.safe_update_json(file_path, updater)
        return True
    
    def create_backup(self, file_path: Path) -> Optional[Path]:
        """
        Create backup of file.
        
        Args:
            file_path: File to backup
            
        Returns:
            Backup path if successful, None otherwise
        """
        if not file_path.exists():
            return None
        
        backup_path = file_path.with_suffix('.bak')
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    def restore_backup(self, file_path: Path) -> bool:
        """
        Restore file from backup.
        
        Args:
            file_path: File to restore
            
        Returns:
            True if successful
        """
        backup_path = file_path.with_suffix('.bak')
        
        if not backup_path.exists():
            return False
        
        shutil.copy2(backup_path, file_path)
        backup_path.unlink()
        return True
    
    def ensure_directory(self, dir_path: Path) -> Path:
        """
        Ensure directory exists.
        
        Args:
            dir_path: Directory path
            
        Returns:
            Directory path
        """
        dir_path = Path(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path
    
    def safe_write_pipeline_state(
        self,
        project: str,
        state_data: Dict[str, Any]
    ) -> bool:
        """
        Safely write pipeline state for a project.
        
        Args:
            project: Project name
            state_data: State data to write
            
        Returns:
            True if successful
        """
        state_path = self.products_dir / project / "pipeline.json"
        return self.atomic_write_json(state_path, state_data)
    
    def safe_update_pipeline_state(
        self,
        project: str,
        updater: callable
    ) -> Dict[str, Any]:
        """
        Safely update pipeline state for a project.
        
        Args:
            project: Project name
            updater: Update function
            
        Returns:
            Updated state data
        """
        state_path = self.products_dir / project / "pipeline.json"
        return self.safe_update_json(state_path, updater)
    
    def safe_write_checkpoint(
        self,
        project: str,
        checkpoint_id: str,
        checkpoint_data: Dict[str, Any]
    ) -> bool:
        """
        Safely write checkpoint for a project.
        
        Args:
            project: Project name
            checkpoint_id: Checkpoint identifier
            checkpoint_data: Checkpoint data
            
        Returns:
            True if successful
        """
        checkpoint_path = self.products_dir / project / "checkpoints" / f"{checkpoint_id}.json"
        return self.atomic_write_json(checkpoint_path, checkpoint_data)
