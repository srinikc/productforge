"""
Product Logger - Structured logging for product pipeline operations.

Phase 1.5 (CRITICAL): Structured logging for debugging and auditing.
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict, field


LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


@dataclass
class LogEntry:
    """A single log entry."""
    timestamp: str
    level: str
    stage: int
    stage_name: str
    agent: str
    message: str
    project: str
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None


class ProductLogger:
    """Per-project logger with structured output."""
    
    LOG_DIR = "logs"
    LOG_FILE = "product.log"
    
    def __init__(self, project: str, products_dir: str = "products", log_level: str = "INFO"):
        self.project = project
        self.products_dir = Path(products_dir)
        self.log_dir = self.products_dir / project / self.LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.log_dir / self.LOG_FILE
        self.log_level = LOG_LEVELS.get(log_level.upper(), logging.INFO)
        self.entries: list[LogEntry] = []
    
    def _log(self, level: str, agent: str, stage: int, stage_name: str, message: str, metadata: Optional[dict] = None, error: Optional[str] = None) -> LogEntry:
        """Internal log method."""
        entry = LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level=level.upper(),
            stage=stage,
            stage_name=stage_name,
            agent=agent,
            message=message,
            project=self.project,
            metadata=metadata or {},
            error=error,
        )
        
        self.entries.append(entry)
        
        # Write to file
        with open(self.log_file, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")
        
        return entry
    
    def debug(self, agent: str, stage: int, stage_name: str, message: str, metadata: Optional[dict] = None) -> LogEntry:
        """Log debug message."""
        return self._log("DEBUG", agent, stage, stage_name, message, metadata)
    
    def info(self, agent: str, stage: int, stage_name: str, message: str, metadata: Optional[dict] = None) -> LogEntry:
        """Log info message."""
        return self._log("INFO", agent, stage, stage_name, message, metadata)
    
    def warning(self, agent: str, stage: int, stage_name: str, message: str, metadata: Optional[dict] = None) -> LogEntry:
        """Log warning message."""
        return self._log("WARNING", agent, stage, stage_name, message, metadata)
    
    def error(self, agent: str, stage: int, stage_name: str, message: str, error: Optional[str] = None, metadata: Optional[dict] = None) -> LogEntry:
        """Log error message."""
        return self._log("ERROR", agent, stage, stage_name, message, metadata, error)
    
    def critical(self, agent: str, stage: int, stage_name: str, message: str, error: Optional[str] = None, metadata: Optional[dict] = None) -> LogEntry:
        """Log critical message."""
        return self._log("CRITICAL", agent, stage, stage_name, message, metadata, error)
    
    def get_logs(self, level: Optional[str] = None, agent: Optional[str] = None, stage: Optional[int] = None, limit: Optional[int] = None) -> list[LogEntry]:
        """Get logs, optionally filtered."""
        logs = self.entries
        
        if level:
            logs = [l for l in logs if l.level == level.upper()]
        if agent:
            logs = [l for l in logs if l.agent == agent]
        if stage is not None:
            logs = [l for l in logs if l.stage == stage]
        
        if limit:
            logs = logs[-limit:]
        
        return logs
    
    def get_log_files(self) -> list[Path]:
        """Get list of log files for this product."""
        return sorted(self.log_dir.glob("*.log"))
    
    def close(self) -> None:
        """Close the logger (no-op for file-based)."""
        pass


class PipelineLogger:
    """Logger for the entire pipeline orchestrator."""
    
    PIPELINE_LOG_DIR = ".pipeline"
    PIPELINE_LOG_FILE = "pipeline.log"
    
    def __init__(self, products_dir: str = "products", log_level: str = "INFO"):
        self.products_dir = Path(products_dir)
        self.log_dir = self.products_dir / self.PIPELINE_LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.log_dir / self.PIPELINE_LOG_FILE
        self.entries: list[LogEntry] = []
    
    def _log(self, level: str, agent: str, stage: int, stage_name: str, message: str, project: str = "orchestrator", metadata: Optional[dict] = None, error: Optional[str] = None) -> LogEntry:
        """Internal log method."""
        entry = LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level=level.upper(),
            stage=stage,
            stage_name=stage_name,
            agent=agent,
            message=message,
            project=project,
            metadata=metadata or {},
            error=error,
        )
        
        self.entries.append(entry)
        
        with open(self.log_file, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")
        
        return entry
    
    def debug(self, agent: str, stage: int, stage_name: str, message: str, **kwargs) -> LogEntry:
        return self._log("DEBUG", agent, stage, stage_name, message, **kwargs)
    
    def info(self, agent: str, stage: int, stage_name: str, message: str, **kwargs) -> LogEntry:
        return self._log("INFO", agent, stage, stage_name, message, **kwargs)
    
    def warning(self, agent: str, stage: int, stage_name: str, message: str, **kwargs) -> LogEntry:
        return self._log("WARNING", agent, stage, stage_name, message, **kwargs)
    
    def error(self, agent: str, stage: int, stage_name: str, message: str, **kwargs) -> LogEntry:
        return self._log("ERROR", agent, stage, stage_name, message, **kwargs)
    
    def get_logs(self, level: Optional[str] = None, limit: Optional[int] = None) -> list[LogEntry]:
        """Get logs with optional filtering."""
        logs = self.entries
        
        if level:
            logs = [l for l in logs if l.level == level.upper()]
        
        if limit:
            logs = logs[-limit:]
        
        return logs
    
    def close(self) -> None:
        """Close the logger."""
        pass
