"""
LLM Error Handler - Handles LLM API errors with retry logic
"""
import time
import json
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

class LLMErrorType(Enum):
    TOKEN_LIMIT = "token_limit"
    API_FAILURE = "api_failure"
    RATE_LIMIT = "rate_limit"
    NETWORK_TIMEOUT = "network_timeout"
    AUTHENTICATION = "authentication"
    UNKNOWN = "unknown"

@dataclass
class LLMError:
    error_id: str
    error_type: LLMErrorType
    message: str
    agent: str
    stage: int
    timestamp: str
    retry_count: int
    max_retries: int
    status: str  # pending, retrying, resolved, failed

class LLMErrorHandler:
    """Handles LLM API errors with retry logic"""
    
    def __init__(self, project: str, max_retries: int = 3):
        self.project = project
        self.max_retries = max_retries
        self.errors_file = Path(__file__).parent.parent / "products" / project / "llm-errors.json"
        self.errors: list = self._load_errors()
    
    def _load_errors(self) -> list:
        if self.errors_file.exists():
            with open(self.errors_file) as f:
                return json.load(f)
        return []
    
    def _save_errors(self):
        with open(self.errors_file, 'w') as f:
            json.dump(self.errors, f, indent=2)
    
    def handle_error(self, error_type: LLMErrorType, message: str, agent: str, stage: int) -> LLMError:
        """Handle an LLM error"""
        error = LLMError(
            error_id=f"ERR-{len(self.errors)+1:04d}",
            error_type=error_type,
            message=message,
            agent=agent,
            stage=stage,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            retry_count=0,
            max_retries=self.max_retries,
            status="pending"
        )
        self.errors.append(asdict(error))
        self._save_errors()
        return error
    
    def should_retry(self, error_id: str) -> bool:
        """Check if we should retry"""
        for error in self.errors:
            if error["error_id"] == error_id:
                if error["retry_count"] < error["max_retries"]:
                    error["retry_count"] += 1
                    error["status"] = "retrying"
                    self._save_errors()
                    return True
                else:
                    error["status"] = "failed"
                    self._save_errors()
                    return False
        return False
    
    def get_errors(self, agent: Optional[str] = None, stage: Optional[int] = None) -> list:
        """Get errors, optionally filtered"""
        filtered = self.errors
        if agent:
            filtered = [e for e in filtered if e["agent"] == agent]
        if stage is not None:
            filtered = [e for e in filtered if e["stage"] == stage]
        return filtered
    
    def get_retry_delay(self, error_id: str) -> int:
        """Get retry delay in seconds (exponential backoff)"""
        for error in self.errors:
            if error["error_id"] == error_id:
                return min(2 ** error["retry_count"], 60)
        return 0
    
    def clear_resolved(self):
        """Clear resolved errors"""
        self.errors = [e for e in self.errors if e["status"] not in ("resolved", "failed")]
        self._save_errors()
