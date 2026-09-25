"""
Logging Manager
Structured logging with auto-rotation for pipeline and per-product logs.

Industry Standard: Structured JSON logs, auto-rotation (1MB x 5 files),
per-product isolation, agent tracking.

Provides:
- Structured logging with agent/stage/action context
- Auto-rotation (1MB per file, 5 files max per product)
- Per-product log isolation
- Log querying and filtering
- Dashboard integration (log viewer)
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import logging
import logging.handlers


@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: str
    agent: str
    stage: int
    action: str
    level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message: str
    project: Optional[str] = None
    session_id: Optional[str] = None
    artifact: Optional[str] = None
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


class RotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Custom rotating file handler with structured JSON output"""

    def __init__(self, filename, maxBytes=1048576, backupCount=5, encoding="utf-8"):
        super().__init__(filename, maxBytes=maxBytes, backupCount=backupCount, encoding=encoding)
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record):
        """Emit log record as JSON"""
        try:
            msg = self.format(record)
            self.stream.write(msg + "\n")
            self.stream.flush()
        except Exception:
            self.handleError(record)


class ProductLogger:
    """Logger for a specific product with auto-rotation"""

    def __init__(self, project: str, products_dir: str = "products"):
        self.project = project
        self.products_dir = Path(products_dir)
        self.project_dir = self.products_dir / project
        self.logs_dir = self.project_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Set up rotating file handler (1MB x 5 files)
        log_file = self.logs_dir / f"{project}.log"
        self.handler = RotatingFileHandler(
            str(log_file),
            maxBytes=1048576,  # 1MB
            backupCount=5,
        )

        # Set up logger
        self.logger = logging.getLogger(f"pipeline.{project}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)
        self.logger.propagate = False

    def close(self):
        """Close the logger handler"""
        if self.handler:
            self.handler.close()
            self.logger.removeHandler(self.handler)

    def log(
        self,
        agent: str,
        stage: int,
        action: str,
        level: str,
        message: str,
        session_id: str = None,
        artifact: str = None,
        duration_seconds: float = None,
        metadata: Dict[str, Any] = None,
    ):
        """Log a structured entry"""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent=agent,
            stage=stage,
            action=action,
            level=level.upper(),
            message=message,
            project=self.project,
            session_id=session_id,
            artifact=artifact,
            duration_seconds=duration_seconds,
            metadata=metadata or {},
        )

        # Map level to logging level
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        self.logger.log(level_map.get(level.upper(), logging.INFO), entry.to_json())

    def info(self, agent: str, stage: int, action: str, message: str, **kwargs):
        self.log(agent, stage, action, "INFO", message, **kwargs)

    def warning(self, agent: str, stage: int, action: str, message: str, **kwargs):
        self.log(agent, stage, action, "WARNING", message, **kwargs)

    def error(self, agent: str, stage: int, action: str, message: str, **kwargs):
        self.log(agent, stage, action, "ERROR", message, **kwargs)

    def debug(self, agent: str, stage: int, action: str, message: str, **kwargs):
        self.log(agent, stage, action, "DEBUG", message, **kwargs)

    def critical(self, agent: str, stage: int, action: str, message: str, **kwargs):
        self.log(agent, stage, action, "CRITICAL", message, **kwargs)

    def get_logs(
        self,
        level: str = None,
        agent: str = None,
        stage: int = None,
        limit: int = 100,
    ) -> List[LogEntry]:
        """Query logs with filters"""
        entries = []

        # Read from current and rotated files
        log_files = list(self.logs_dir.glob(f"{self.project}.log*"))
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        for log_file in log_files:
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            entry = LogEntry.from_dict(data)

                            # Apply filters
                            if level and entry.level != level.upper():
                                continue
                            if agent and entry.agent != agent:
                                continue
                            if stage is not None and entry.stage != stage:
                                continue

                            entries.append(entry)

                            if len(entries) >= limit:
                                return entries
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

        return entries

    def get_log_files(self) -> List[Dict[str, Any]]:
        """Get list of log files with metadata"""
        files = []
        for f in self.logs_dir.glob(f"{self.project}.log*"):
            stat = f.stat()
            files.append({
                "name": f.name,
                "path": str(f),
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        return sorted(files, key=lambda x: x["modified"], reverse=True)

    def cleanup_old_logs(self, max_files: int = 5):
        """Clean up old log files beyond max_files"""
        files = sorted(
            self.logs_dir.glob(f"{self.project}.log*"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        for f in files[max_files:]:
            f.unlink()


class PipelineLogger:
    """Logger for the pipeline system itself (not per-product)"""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.logs_dir = self.base_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Set up rotating file handler
        log_file = self.logs_dir / "pipeline.log"
        self.handler = RotatingFileHandler(
            str(log_file),
            maxBytes=1048576,  # 1MB
            backupCount=5,
        )

        self.logger = logging.getLogger("pipeline")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)
        self.logger.propagate = False

    def close(self):
        """Close the logger handler"""
        if self.handler:
            self.handler.close()
            self.logger.removeHandler(self.handler)

    def log(self, agent: str, stage: int, action: str, level: str, message: str, **kwargs):
        """Log a structured entry"""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent=agent,
            stage=stage,
            action=action,
            level=level.upper(),
            message=message,
            **kwargs,
        )

        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        self.logger.log(level_map.get(level.upper(), logging.INFO), entry.to_json())

    def info(self, agent: str, stage: int, action: str, message: str, **kwargs):
        self.log(agent, stage, action, "INFO", message, **kwargs)

    def warning(self, agent: str, stage: int, action: str, message: str, **kwargs):
        self.log(agent, stage, action, "WARNING", message, **kwargs)

    def error(self, agent: str, stage: int, action: str, message: str, **kwargs):
        self.log(agent, stage, action, "ERROR", message, **kwargs)

    def get_logs(self, limit: int = 100) -> List[LogEntry]:
        """Get recent log entries"""
        entries = []
        log_files = sorted(
            self.logs_dir.glob("pipeline.log*"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        for log_file in log_files:
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            entries.append(LogEntry.from_dict(data))
                            if len(entries) >= limit:
                                return entries
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

        return entries
