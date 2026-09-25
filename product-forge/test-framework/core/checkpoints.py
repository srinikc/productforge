"""
Checkpoints - Save and resume pipeline state.

Phase 1.2 (CRITICAL): Checkpoint/resume system for long-running pipelines.
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict, field


@dataclass
class Checkpoint:
    """A pipeline checkpoint for resume capability."""
    id: str
    project: str
    stage: int
    stage_name: str
    created_at: str
    state: dict
    metadata: dict = field(default_factory=dict)
    parent_checkpoint: Optional[str] = None
    checksum: str = ""
    
    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._compute_checksum()
    
    def _compute_checksum(self) -> str:
        """Compute SHA256 checksum of state for integrity verification."""
        state_str = json.dumps(self.state, sort_keys=True, default=str)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]
    
    def verify(self) -> bool:
        """Verify checkpoint integrity."""
        return self.checksum == self._compute_checksum()


class CheckpointManager:
    """Manages checkpoints for pipeline resume."""
    
    CHECKPOINTS_DIR = "checkpoints"
    
    def __init__(self, project: str, products_dir: str = "products"):
        self.project = project
        self.products_dir = Path(products_dir)
        self.checkpoint_dir = self.products_dir / project / self.CHECKPOINTS_DIR
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def save(
        self,
        stage: int,
        stage_name: str,
        state: dict,
        metadata: Optional[dict] = None,
        parent: Optional[str] = None,
    ) -> Checkpoint:
        """
        Save a checkpoint.
        
        Args:
            stage: Current stage number
            stage_name: Stage name
            state: State data to save
            metadata: Optional metadata
            parent: Parent checkpoint ID
        
        Returns:
            Created checkpoint
        """
        checkpoint_id = f"ckpt_{stage}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        checkpoint = Checkpoint(
            id=checkpoint_id,
            project=self.project,
            stage=stage,
            stage_name=stage_name,
            created_at=datetime.utcnow().isoformat(),
            state=state,
            metadata=metadata or {},
            parent_checkpoint=parent,
        )
        
        # Save to file
        ckpt_file = self.checkpoint_dir / f"{checkpoint_id}.json"
        ckpt_file.write_text(json.dumps(asdict(checkpoint), indent=2, default=str))
        
        # Update index
        self._update_index(checkpoint)
        
        return checkpoint
    
    def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load a checkpoint by ID."""
        ckpt_file = self.checkpoint_dir / f"{checkpoint_id}.json"
        
        if not ckpt_file.exists():
            return None
        
        try:
            data = json.loads(ckpt_file.read_text())
            checkpoint = Checkpoint(**data)
            
            if not checkpoint.verify():
                return None  # Corrupted
            
            return checkpoint
        except (json.JSONDecodeError, OSError, TypeError):
            return None
    
    def load_latest(self) -> Optional[Checkpoint]:
        """Load the most recent checkpoint."""
        index = self._load_index()
        
        if not index["checkpoints"]:
            return None
        
        latest = index["checkpoints"][-1]
        return self.load(latest["id"])
    
    def list_checkpoints(self) -> list[dict]:
        """List all checkpoints for this project."""
        index = self._load_index()
        return index["checkpoints"]
    
    def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        ckpt_file = self.checkpoint_dir / f"{checkpoint_id}.json"
        
        if not ckpt_file.exists():
            return False
        
        try:
            ckpt_file.unlink()
            self._remove_from_index(checkpoint_id)
            return True
        except OSError:
            return False
    
    def cleanup_old(self, keep_last: int = 10) -> int:
        """Keep only the N most recent checkpoints. Returns count deleted."""
        checkpoints = self.list_checkpoints()
        
        if len(checkpoints) <= keep_last:
            return 0
        
        to_delete = checkpoints[:-keep_last]
        deleted = 0
        for ckpt in to_delete:
            if self.delete(ckpt["id"]):
                deleted += 1
        
        return deleted
    
    def _index_file(self) -> Path:
        """Get the index file path."""
        return self.checkpoint_dir / "index.json"
    
    def _load_index(self) -> dict:
        """Load the checkpoint index."""
        index_file = self._index_file()
        
        if not index_file.exists():
            return {"checkpoints": []}
        
        try:
            return json.loads(index_file.read_text())
        except (json.JSONDecodeError, OSError):
            return {"checkpoints": []}
    
    def _update_index(self, checkpoint: Checkpoint) -> None:
        """Update the index with a new checkpoint."""
        index = self._load_index()
        index["checkpoints"].append({
            "id": checkpoint.id,
            "stage": checkpoint.stage,
            "stage_name": checkpoint.stage_name,
            "created_at": checkpoint.created_at,
            "checksum": checkpoint.checksum,
        })
        self._index_file().write_text(json.dumps(index, indent=2, default=str))
    
    def _remove_from_index(self, checkpoint_id: str) -> None:
        """Remove a checkpoint from the index."""
        index = self._load_index()
        index["checkpoints"] = [
            c for c in index["checkpoints"] if c["id"] != checkpoint_id
        ]
        self._index_file().write_text(json.dumps(index, indent=2, default=str))
