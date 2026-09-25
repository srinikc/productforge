"""
Tool Result Cache - Phase 2.2

Caches tool/function results to avoid redundant calls. Includes
TTL-based expiry, content-based keys, and cache invalidation.

Phase 2.2 (IMPORTANT): Tool Result Caching - reduces token spend
and latency by caching deterministic tool results.
"""
import json
import hashlib
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class CacheStrategy(str, Enum):
    """Cache strategies."""
    TTL = "ttl"                    # Time-based expiry
    LRU = "lru"                    # Least recently used
    CONTENT_HASH = "content_hash"  # Cache by content fingerprint


@dataclass
class CacheEntry:
    """A single cache entry."""
    key: str
    value: Any
    created_at: str
    expires_at: str
    hits: int = 0
    last_accessed: str = ""
    size_bytes: int = 0
    metadata: dict = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        return datetime.utcnow() > datetime.fromisoformat(self.expires_at)
    
    def touch(self) -> None:
        """Update last accessed time."""
        self.last_accessed = datetime.utcnow().isoformat()
        self.hits += 1


class ToolResultCache:
    """
    Cache for tool/function call results.
    
    Phase 2.2: Avoids redundant tool calls by caching results.
    """
    
    CACHE_FILE = "tool_cache.json"
    DEFAULT_TTL_SECONDS = 3600  # 1 hour
    MAX_ENTRIES = 1000
    
    # Tools that should NOT be cached (side effects)
    NON_CACHEABLE_TOOLS = {
        "create_file", "write_file", "delete_file", "move_file",
        "create_user", "update_user", "delete_user",
        "send_email", "send_notification", "make_payment",
        "deploy", "publish", "push",
        "run_command", "shell", "exec", "execute",
    }
    
    def __init__(self, products_dir: str = "products", default_ttl: int = DEFAULT_TTL_SECONDS):
        self.products_dir = Path(products_dir)
        self.cache_file = self.products_dir / ".pipeline" / self.CACHE_FILE
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl
        self.entries: dict[str, CacheEntry] = self._load()
    
    def _load(self) -> dict[str, CacheEntry]:
        """Load cache from disk."""
        if not self.cache_file.exists():
            return {}
        
        try:
            data = json.loads(self.cache_file.read_text())
            return {
                k: CacheEntry(**v) for k, v in data.get("entries", {}).items()
            }
        except (json.JSONDecodeError, OSError, TypeError):
            return {}
    
    def _save(self) -> None:
        """Save cache to disk."""
        data = {
            "entries": {k: asdict(v) for k, v in self.entries.items()},
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.cache_file.write_text(json.dumps(data, indent=2, default=str))
    
    def _compute_key(
        self,
        tool_name: str,
        arguments: dict,
    ) -> str:
        """Compute cache key from tool name and arguments."""
        # Normalize arguments (sort keys, lowercase strings for stability)
        normalized = json.dumps(arguments, sort_keys=True, default=str)
        key_data = f"{tool_name}:{normalized}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]
    
    def is_cacheable(self, tool_name: str) -> bool:
        """Check if a tool's results can be cached."""
        return tool_name not in self.NON_CACHEABLE_TOOLS
    
    def get(
        self,
        tool_name: str,
        arguments: dict,
    ) -> Optional[Any]:
        """Get cached result for a tool call."""
        if not self.is_cacheable(tool_name):
            return None
        
        key = self._compute_key(tool_name, arguments)
        entry = self.entries.get(key)
        
        if not entry:
            return None
        
        if entry.is_expired():
            del self.entries[key]
            self._save()
            return None
        
        entry.touch()
        return entry.value
    
    def set(
        self,
        tool_name: str,
        arguments: dict,
        value: Any,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Cache a tool result."""
        if not self.is_cacheable(tool_name):
            return False
        
        # Check size limit
        if len(self.entries) >= self.MAX_ENTRIES:
            self._evict_lru()
        
        key = self._compute_key(tool_name, arguments)
        ttl = ttl_seconds or self.default_ttl
        now = datetime.utcnow()
        
        try:
            value_str = json.dumps(value, default=str)
            size_bytes = len(value_str.encode())
        except (TypeError, ValueError):
            return False  # Not JSON-serializable
        
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=ttl)).isoformat(),
            size_bytes=size_bytes,
            metadata=metadata or {},
        )
        
        self.entries[key] = entry
        self._save()
        return True
    
    def invalidate(self, tool_name: Optional[str] = None, pattern: Optional[str] = None) -> int:
        """Invalidate cache entries."""
        if not tool_name and not pattern:
            count = len(self.entries)
            self.entries.clear()
            self._save()
            return count
        
        to_remove = []
        for key in self.entries:
            # Cache key is hashed, so we can't directly match tool name
            # In production, would store tool name as metadata
            if pattern and pattern in key:
                to_remove.append(key)
        
        for key in to_remove:
            del self.entries[key]
        
        if to_remove:
            self._save()
        
        return len(to_remove)
    
    def _evict_lru(self) -> int:
        """Evict least recently used entries."""
        if not self.entries:
            return 0
        
        # Sort by last_accessed, evict oldest 10%
        sorted_entries = sorted(
            self.entries.items(),
            key=lambda x: x[1].last_accessed or x[1].created_at
        )
        evict_count = max(1, len(sorted_entries) // 10)
        
        for key, _ in sorted_entries[:evict_count]:
            del self.entries[key]
        
        return evict_count
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        total_hits = sum(e.hits for e in self.entries.values())
        total_size = sum(e.size_bytes for e in self.entries.values())
        expired = sum(1 for e in self.entries.values() if e.is_expired())
        
        return {
            "total_entries": len(self.entries),
            "total_hits": total_hits,
            "total_size_bytes": total_size,
            "expired_entries": expired,
            "max_entries": self.MAX_ENTRIES,
            "hit_rate": round(
                total_hits / max(1, len(self.entries)), 2
            ),
        }
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        expired_keys = [k for k, v in self.entries.items() if v.is_expired()]
        for k in expired_keys:
            del self.entries[k]
        
        if expired_keys:
            self._save()
        
        return len(expired_keys)
