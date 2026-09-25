"""
Write Safety Tests
Tests for atomic file operations
"""

import pytest
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.write_safety import WriteSafety


class TestWriteSafety:
    """Test suite for WriteSafety"""
    
    def test_atomic_write_json(self, temp_products_dir, sample_project):
        """Test atomic JSON write"""
        ws = WriteSafety(str(temp_products_dir))
        
        test_data = {"key": "value", "nested": {"inner": 123}}
        file_path = temp_products_dir / sample_project / "test.json"
        
        result = ws.atomic_write_json(file_path, test_data)
        assert result is True
        
        # Verify file was written
        assert file_path.exists()
        
        # Verify content
        with open(file_path, 'r') as f:
            loaded = json.load(f)
        assert loaded == test_data
    
    def test_atomic_write_text(self, temp_products_dir, sample_project):
        """Test atomic text write"""
        ws = WriteSafety(str(temp_products_dir))
        
        content = "Hello, World!\nLine 2\nLine 3"
        file_path = temp_products_dir / sample_project / "test.txt"
        
        result = ws.atomic_write_text(file_path, content)
        assert result is True
        
        # Verify file was written
        assert file_path.exists()
        
        # Verify content
        with open(file_path, 'r') as f:
            loaded = f.read()
        assert loaded == content
    
    def test_backup_on_write(self, temp_products_dir, sample_project):
        """Test that backup is created before write and cleaned up after success"""
        ws = WriteSafety(str(temp_products_dir))
        
        file_path = temp_products_dir / sample_project / "test.json"
        
        # Write initial content
        ws.atomic_write_json(file_path, {"version": 1})
        assert file_path.exists()
        
        # Write again with backup
        ws.atomic_write_json(file_path, {"version": 2}, backup=True)
        
        # Verify backup is cleaned up after successful write
        backup_path = file_path.with_suffix('.bak')
        assert not backup_path.exists()  # Backup should be cleaned up
        
        # Verify file has new content
        with open(file_path, 'r') as f:
            data = json.load(f)
        assert data["version"] == 2
    
    def test_safe_update_json(self, temp_products_dir, sample_project):
        """Test safe JSON update with function"""
        ws = WriteSafety(str(temp_products_dir))
        
        file_path = temp_products_dir / sample_project / "test.json"
        
        # Write initial content
        ws.atomic_write_json(file_path, {"count": 0, "items": []})
        
        # Update with function
        def updater(data):
            data["count"] += 1
            data["items"].append("new-item")
            return data
        
        updated = ws.safe_update_json(file_path, updater)
        
        assert updated["count"] == 1
        assert "new-item" in updated["items"]
    
    def test_safe_append_json(self, temp_products_dir, sample_project):
        """Test safe JSON array append"""
        ws = WriteSafety(str(temp_products_dir))
        
        file_path = temp_products_dir / sample_project / "test.json"
        
        # Write initial array
        ws.atomic_write_json(file_path, [])
        
        # Append items
        ws.safe_append_json(file_path, {"id": 1})
        ws.safe_append_json(file_path, {"id": 2})
        
        # Verify
        with open(file_path, 'r') as f:
            data = json.load(f)
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[1]["id"] == 2
    
    def test_create_backup(self, temp_products_dir, sample_project):
        """Test backup creation"""
        ws = WriteSafety(str(temp_products_dir))
        
        file_path = temp_products_dir / sample_project / "test.json"
        ws.atomic_write_json(file_path, {"data": "original"})
        
        # Create backup
        backup_path = ws.create_backup(file_path)
        assert backup_path is not None
        assert backup_path.exists()
    
    def test_restore_backup(self, temp_products_dir, sample_project):
        """Test restoring file from backup"""
        ws = WriteSafety(str(temp_products_dir))
        
        file_path = temp_products_dir / sample_project / "test.json"
        
        # Write original
        ws.atomic_write_json(file_path, {"version": "original"})
        
        # Create backup
        ws.create_backup(file_path)
        
        # Modify file directly (not using atomic_write_json to preserve backup)
        with open(file_path, 'w') as f:
            json.dump({"version": "modified"}, f)
        
        # Restore backup
        restored = ws.restore_backup(file_path)
        assert restored is True
        
        # Verify restored content
        with open(file_path, 'r') as f:
            data = json.load(f)
        assert data["version"] == "original"
    
    def test_ensure_directory(self, temp_products_dir, sample_project):
        """Test directory creation"""
        ws = WriteSafety(str(temp_products_dir))
        
        dir_path = temp_products_dir / sample_project / "new" / "nested" / "dir"
        result = ws.ensure_directory(dir_path)
        
        assert result.exists()
        assert result.is_dir()
    
    def test_safe_write_pipeline_state(self, temp_products_dir, sample_project):
        """Test safe pipeline state write"""
        ws = WriteSafety(str(temp_products_dir))
        
        state_data = {
            "current_stage": 2,
            "status": "running",
            "timestamp": "2024-01-01T00:00:00"
        }
        
        result = ws.safe_write_pipeline_state(sample_project, state_data)
        assert result is True
        
        # Verify file was written
        state_path = temp_products_dir / sample_project / "pipeline.json"
        assert state_path.exists()
    
    def test_safe_update_pipeline_state(self, temp_products_dir, sample_project):
        """Test safe pipeline state update"""
        ws = WriteSafety(str(temp_products_dir))
        
        # Write initial state
        initial_state = {"current_stage": 0, "status": "idle"}
        ws.safe_write_pipeline_state(sample_project, initial_state)
        
        # Update state
        def updater(data):
            data["current_stage"] = 1
            data["status"] = "running"
            return data
        
        updated = ws.safe_update_pipeline_state(sample_project, updater)
        
        assert updated["current_stage"] == 1
        assert updated["status"] == "running"
