"""
Agent Memory System — Phase G

Provides persistent memory across agent runs with 8 memory types:
1. Raw Evidence   — original sources and observations
2. Semantic        — facts, concepts, relationships
3. Episodic        — what agents did and what happened
4. Decision        — decisions, rationale, alternatives
5. Procedural      — reusable workflows and skills
6. Failure         — failed approaches and why they failed
7. Policy          — rules, permissions, constraints
8. Working         — current task/session context

Supports retrieval (query with filtering), storage (JSON file-backed),
validation (mark entries verified), and knowledge compilation
(consolidate related memories into structured knowledge).
"""

import json
import os
import time
import hashlib
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum
from datetime import datetime, timezone
from pathlib import Path
import re
from collections import defaultdict
import threading


class MemoryType(Enum):
    """Eight distinct memory categories for agent knowledge."""
    RAW_EVIDENCE = "raw_evidence"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    DECISION = "decision"
    PROCEDURAL = "procedural"
    FAILURE = "failure"
    POLICY = "policy"
    WORKING = "working"


class MemoryPriority(Enum):
    """Priority levels for memory retention and retrieval ordering."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class RetrievalStrategy(Enum):
    """Strategies for scoring and ranking memory retrieval results."""
    RELEVANCE = "relevance"
    RECENCY = "recency"
    CONFIDENCE = "confidence"
    HYBRID = "hybrid"


@dataclass
class MemoryEntry:
    """A single memory entry stored in the agent memory system.

    Attributes:
        entry_id: Unique identifier for this memory entry.
        memory_type: The category of memory (one of MemoryType).
        content: The actual text content of the memory.
        source: Origin of the memory (e.g., file path, agent name, user input).
        timestamp: ISO-8601 UTC timestamp when the memory was created.
        confidence: Confidence score between 0.0 and 1.0.
        tags: Descriptive tags for filtering and categorization.
        metadata: Arbitrary key-value metadata for extensibility.
        validated: Whether this entry has been verified.
        validation_source: What validated this entry (if validated).
        priority: Retention priority level.
        access_count: Number of times this entry has been retrieved.
        last_accessed: ISO-8601 UTC timestamp of last retrieval.
        related_entries: List of entry_ids this entry is related to.
        ttl_seconds: Time-to-live in seconds; 0 means no expiry.
        expires_at: ISO-8601 UTC timestamp when this entry expires; None means never.
    """
    entry_id: str
    memory_type: str
    content: str
    source: str
    timestamp: str
    confidence: float
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    validated: bool = False
    validation_source: str = ""
    priority: str = "normal"
    access_count: int = 0
    last_accessed: str = ""
    related_entries: List[str] = field(default_factory=list)
    ttl_seconds: int = 0
    expires_at: str = ""

    def is_expired(self) -> bool:
        """Check if this memory entry has exceeded its TTL."""
        if self.ttl_seconds <= 0 or not self.expires_at:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) >= exp
        except (ValueError, TypeError):
            return False

    def touch(self) -> None:
        """Record that this entry was accessed (updates count and timestamp)."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entry to a JSON-compatible dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Deserialize a dictionary into a MemoryEntry instance."""
        return cls(
            entry_id=data.get("entry_id", ""),
            memory_type=data.get("memory_type", ""),
            content=data.get("content", ""),
            source=data.get("source", ""),
            timestamp=data.get("timestamp", ""),
            confidence=float(data.get("confidence", 0.0)),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            validated=data.get("validated", False),
            validation_source=data.get("validation_source", ""),
            priority=data.get("priority", "normal"),
            access_count=data.get("access_count", 0),
            last_accessed=data.get("last_accessed", ""),
            related_entries=data.get("related_entries", []),
            ttl_seconds=data.get("ttl_seconds", 0),
            expires_at=data.get("expires_at", ""),
        )


@dataclass
class MemoryQuery:
    """Parameters for querying the memory system.

    Attributes:
        query: Free-text search string.
        memory_types: Restrict search to these memory types (empty = all).
        tags: Only return entries containing at least one of these tags.
        min_confidence: Minimum confidence score to include.
        max_results: Maximum number of results to return.
        strategy: Retrieval scoring strategy.
        include_expired: Whether to include expired entries.
        sort_by: Field name to sort by (default: by strategy).
        source_filter: Only return entries from this source (substring match).
    """
    query: str = ""
    memory_types: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    min_confidence: float = 0.0
    max_results: int = 10
    strategy: str = "hybrid"
    include_expired: bool = False
    sort_by: str = ""
    source_filter: str = ""


@dataclass
class CompiledKnowledge:
    """Result of knowledge compilation — a consolidated insight.

    Attributes:
        title: Short descriptive title for the compiled knowledge.
        summary: Human-readable summary of the consolidated insight.
        source_entries: Entry IDs that contributed to this compilation.
        memory_type: The memory type this compilation belongs to.
        confidence: Aggregated confidence (weighted average of sources).
        tags: Combined tags from all source entries.
        timestamp: When this compilation was created.
    """
    title: str
    summary: str
    source_entries: List[str]
    memory_type: str
    confidence: float
    tags: List[str] = field(default_factory=list)
    timestamp: str = ""


class AgentMemory:
    """Persistent memory store for agents with JSON file-backed storage.

    Provides CRUD operations, query with filtering and scoring,
    validation marking, knowledge compilation, and TTL-based expiry.

    Thread-safe: all mutations are protected by a reentrant lock.

    Args:
        products_dir: Root directory containing project folders.
        project: Project name (subdirectory under products_dir).
    """

    def __init__(self, products_dir: str = "products", project: str = "default"):
        self.products_dir = products_dir
        self.project = project
        self.memory_dir = os.path.join(products_dir, project, "memory")
        self._lock = threading.RLock()
        self._ensure_dirs()
        self.memory_store: Dict[str, List[MemoryEntry]] = {
            mt.value: [] for mt in MemoryType
        }
        self._load_all()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_dirs(self) -> None:
        """Create memory directories for each memory type if they do not exist."""
        for mt in MemoryType:
            os.makedirs(os.path.join(self.memory_dir, mt.value), exist_ok=True)

    def _load_all(self) -> None:
        """Load all memory entries from disk into the in-memory store."""
        for mt in MemoryType:
            dir_path = os.path.join(self.memory_dir, mt.value)
            if not os.path.exists(dir_path):
                continue
            for fname in os.listdir(dir_path):
                if not fname.endswith(".json"):
                    continue
                file_path = os.path.join(dir_path, fname)
                try:
                    with open(file_path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    entry = MemoryEntry.from_dict(data)
                    self.memory_store[mt.value].append(entry)
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    # Corrupted file — skip but log
                    print(f"[AgentMemory] Skipping corrupted file {file_path}: {exc}")

    def _entry_path(self, memory_type: str, entry_id: str) -> str:
        """Return the filesystem path for a given entry."""
        return os.path.join(self.memory_dir, memory_type, f"{entry_id}.json")

    def _save_entry(self, entry: MemoryEntry) -> bool:
        """Persist a single entry to disk. Returns True on success."""
        try:
            path = self._entry_path(entry.memory_type, entry.entry_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except OSError as exc:
            print(f"[AgentMemory] Failed to save entry {entry.entry_id}: {exc}")
            return False

    def _remove_entry_file(self, memory_type: str, entry_id: str) -> bool:
        """Delete an entry file from disk. Returns True on success."""
        try:
            path = self._entry_path(memory_type, entry_id)
            if os.path.exists(path):
                os.remove(path)
            return True
        except OSError as exc:
            print(f"[AgentMemory] Failed to remove entry {entry_id}: {exc}")
            return False

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Lowercase tokenize a string into alphanumeric tokens."""
        return [t for t in re.split(r"\W+", text.lower()) if t]

    @staticmethod
    def _compute_relevance_score(query_tokens: List[str], content_tokens: List[str]) -> float:
        """Compute a simple token-overlap relevance score in [0, 1].

        Jaccard-like: |intersection| / |union|.
        """
        if not query_tokens or not content_tokens:
            return 0.0
        q_set = set(query_tokens)
        c_set = set(content_tokens)
        intersection = q_set & c_set
        union = q_set | c_set
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _compute_recency_score(timestamp_str: str) -> float:
        """Score recency: 1.0 for now, decays over 30 days."""
        try:
            ts = datetime.fromisoformat(timestamp_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0
            return max(0.0, 1.0 - (age_days / 30.0))
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _compute_hybrid_score(
        relevance: float,
        recency: float,
        confidence: float,
        access_count: int,
    ) -> float:
        """Weighted hybrid of relevance, recency, confidence, and popularity."""
        popularity = min(1.0, access_count / 20.0)
        return 0.40 * relevance + 0.25 * recency + 0.25 * confidence + 0.10 * popularity

    # ------------------------------------------------------------------
    # Public API: CRUD
    # ------------------------------------------------------------------

    def store(
        self,
        memory_type: str,
        content: str,
        source: str,
        confidence: float = 1.0,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        priority: str = "normal",
        ttl_seconds: int = 0,
        entry_id: Optional[str] = None,
    ) -> Optional[MemoryEntry]:
        """Store a new memory entry.

        Args:
            memory_type: One of the MemoryType values (string).
            content: The memory content text.
            source: Origin of the memory.
            confidence: Confidence score 0.0–1.0.
            tags: Optional descriptive tags.
            metadata: Optional key-value metadata.
            priority: 'low', 'normal', 'high', or 'critical'.
            ttl_seconds: Time-to-live; 0 means no expiry.
            entry_id: Optional custom ID; auto-generated if omitted.

        Returns:
            The created MemoryEntry, or None on failure.
        """
        # Validate memory type
        valid_types = {mt.value for mt in MemoryType}
        if memory_type not in valid_types:
            print(f"[AgentMemory] Invalid memory_type: {memory_type}")
            return None

        # Clamp confidence
        confidence = max(0.0, min(1.0, float(confidence)))

        now = datetime.now(timezone.utc).isoformat()
        eid = entry_id or f"{memory_type}_{uuid.uuid4().hex[:12]}"

        # Compute expiry
        expires_at = ""
        if ttl_seconds > 0:
            exp_dt = datetime.now(timezone.utc).timestamp() + ttl_seconds
            expires_at = datetime.fromtimestamp(exp_dt, tz=timezone.utc).isoformat()

        entry = MemoryEntry(
            entry_id=eid,
            memory_type=memory_type,
            content=content,
            source=source,
            timestamp=now,
            confidence=confidence,
            tags=tags or [],
            metadata=metadata or {},
            validated=False,
            validation_source="",
            priority=priority,
            access_count=0,
            last_accessed="",
            related_entries=[],
            ttl_seconds=ttl_seconds,
            expires_at=expires_at,
        )

        with self._lock:
            if self._save_entry(entry):
                self.memory_store[memory_type].append(entry)
                return entry
        return None

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve a single entry by ID.

        Args:
            entry_id: The unique entry identifier.

        Returns:
            The MemoryEntry if found, else None.
        """
        with self._lock:
            for entries in self.memory_store.values():
                for entry in entries:
                    if entry.entry_id == entry_id:
                        entry.touch()
                        self._save_entry(entry)
                        return entry
        return None

    def update(
        self,
        entry_id: str,
        content: Optional[str] = None,
        confidence: Optional[float] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        priority: Optional[str] = None,
    ) -> Optional[MemoryEntry]:
        """Update fields of an existing memory entry.

        Args:
            entry_id: The entry to update.
            content: New content (if provided).
            confidence: New confidence (if provided).
            tags: Replace tags (if provided).
            metadata: Merge into existing metadata (if provided).
            priority: New priority (if provided).

        Returns:
            The updated MemoryEntry, or None if not found.
        """
        with self._lock:
            for entries in self.memory_store.values():
                for entry in entries:
                    if entry.entry_id == entry_id:
                        if content is not None:
                            entry.content = content
                        if confidence is not None:
                            entry.confidence = max(0.0, min(1.0, float(confidence)))
                        if tags is not None:
                            entry.tags = tags
                        if metadata is not None:
                            entry.metadata.update(metadata)
                        if priority is not None:
                            entry.priority = priority
                        self._save_entry(entry)
                        return entry
        return None

    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry by ID.

        Args:
            entry_id: The entry to delete.

        Returns:
            True if deleted, False if not found.
        """
        with self._lock:
            for mt_name, entries in self.memory_store.items():
                for i, entry in enumerate(entries):
                    if entry.entry_id == entry_id:
                        self._remove_entry_file(mt_name, entry_id)
                        entries.pop(i)
                        return True
        return False

    def list_entries(
        self,
        memory_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MemoryEntry]:
        """List memory entries, optionally filtered by type.

        Args:
            memory_type: Restrict to this type; None for all.
            limit: Max entries to return.
            offset: Pagination offset.

        Returns:
            List of MemoryEntry objects.
        """
        results: List[MemoryEntry] = []
        types_to_list = [memory_type] if memory_type else [mt.value for mt in MemoryType]

        for mt_name in types_to_list:
            results.extend(self.memory_store.get(mt_name, []))

        # Sort by timestamp descending (newest first)
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[offset: offset + limit]

    # ------------------------------------------------------------------
    # Public API: Query & Retrieval
    # ------------------------------------------------------------------

    def retrieve(self, query: MemoryQuery) -> List[MemoryEntry]:
        """Retrieve memory entries matching the query.

        Applies filtering (type, tags, confidence, expiry, source),
        computes a score per the requested strategy, and returns
        the top `max_results` entries sorted by score descending.

        Args:
            query: A MemoryQuery with filter and scoring parameters.

        Returns:
            List of MemoryEntry objects matching the query.
        """
        strategy = query.strategy or "hybrid"
        query_tokens = self._tokenize(query.query) if query.query else []

        candidates: List[Tuple[float, MemoryEntry]] = []

        types_to_search = (
            query.memory_types if query.memory_types else [mt.value for mt in MemoryType]
        )

        for mt_name in types_to_search:
            for entry in self.memory_store.get(mt_name, []):
                # --- Filters ---
                if entry.confidence < query.min_confidence:
                    continue
                if not query.include_expired and entry.is_expired():
                    continue
                if query.tags and not any(t in entry.tags for t in query.tags):
                    continue
                if query.source_filter and query.source_filter.lower() not in entry.source.lower():
                    continue

                # --- Scoring ---
                content_tokens = self._tokenize(entry.content)

                if strategy == "relevance":
                    score = self._compute_relevance_score(query_tokens, content_tokens)
                elif strategy == "recency":
                    score = self._compute_recency_score(entry.timestamp)
                elif strategy == "confidence":
                    score = entry.confidence
                else:  # hybrid
                    relevance = self._compute_relevance_score(query_tokens, content_tokens)
                    recency = self._compute_recency_score(entry.timestamp)
                    score = self._compute_hybrid_score(
                        relevance, recency, entry.confidence, entry.access_count
                    )

                candidates.append((score, entry))

        # Sort descending by score
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Collect results and touch each entry
        results: List[MemoryEntry] = []
        with self._lock:
            for _, entry in candidates[: query.max_results]:
                entry.touch()
                self._save_entry(entry)
                results.append(entry)

        return results

    # ------------------------------------------------------------------
    # Public API: Validation
    # ------------------------------------------------------------------

    def validate_entry(self, entry_id: str, validation_source: str) -> bool:
        """Mark a memory entry as validated.

        Args:
            entry_id: The entry to validate.
            validation_source: Who/what validated this entry.

        Returns:
            True if the entry was found and updated, False otherwise.
        """
        with self._lock:
            for entries in self.memory_store.values():
                for entry in entries:
                    if entry.entry_id == entry_id:
                        entry.validated = True
                        entry.validation_source = validation_source
                        entry.metadata["validated_at"] = datetime.now(timezone.utc).isoformat()
                        self._save_entry(entry)
                        return True
        return False

    def unvalidate_entry(self, entry_id: str) -> bool:
        """Remove validation status from a memory entry.

        Args:
            entry_id: The entry to unvalidate.

        Returns:
            True if found and updated, False otherwise.
        """
        with self._lock:
            for entries in self.memory_store.values():
                for entry in entries:
                    if entry.entry_id == entry_id:
                        entry.validated = False
                        entry.validation_source = ""
                        entry.metadata.pop("validated_at", None)
                        self._save_entry(entry)
                        return True
        return False

    def get_validated(self, memory_type: Optional[str] = None) -> List[MemoryEntry]:
        """Return only validated entries.

        Args:
            memory_type: Optional filter by memory type.

        Returns:
            List of validated MemoryEntry objects.
        """
        results: List[MemoryEntry] = []
        types = [memory_type] if memory_type else [mt.value for mt in MemoryType]
        for mt_name in types:
            for entry in self.memory_store.get(mt_name, []):
                if entry.validated:
                    results.append(entry)
        return results

    # ------------------------------------------------------------------
    # Public API: Knowledge Compilation
    # ------------------------------------------------------------------

    def compile_knowledge(
        self,
        memory_type: str,
        min_entries: int = 2,
        max_entries: int = 50,
        min_confidence: float = 0.5,
    ) -> List[CompiledKnowledge]:
        """Compile related memory entries into consolidated knowledge.

        Groups entries by shared tags, then merges each group into a
        single CompiledKnowledge with a summary and aggregated confidence.

        Args:
            memory_type: The memory type to compile.
            min_entries: Minimum group size to produce a compilation.
            max_entries: Maximum entries to process per compilation.
            min_confidence: Only include entries above this confidence.

        Returns:
            List of CompiledKnowledge objects.
        """
        entries = self.memory_store.get(memory_type, [])
        # Filter by confidence
        filtered = [e for e in entries if e.confidence >= min_confidence and not e.is_expired()]

        if len(filtered) < min_entries:
            return []

        # Group by shared tags
        tag_groups: Dict[str, List[MemoryEntry]] = defaultdict(list)
        untagged: List[MemoryEntry] = []

        for entry in filtered[:max_entries]:
            if entry.tags:
                for tag in entry.tags:
                    tag_groups[tag].append(entry)
            else:
                untagged.append(entry)

        compilations: List[CompiledKnowledge] = []

        # Compile each tag group with enough entries
        seen_ids: set = set()
        for tag, group_entries in tag_groups.items():
            # Deduplicate within group
            unique = []
            for e in group_entries:
                if e.entry_id not in seen_ids:
                    unique.append(e)
                    seen_ids.add(e.entry_id)

            if len(unique) < min_entries:
                continue

            # Build summary
            contents = [e.content for e in unique]
            avg_confidence = sum(e.confidence for e in unique) / len(unique)
            all_tags = list({t for e in unique for t in e.tags})
            source_ids = [e.entry_id for e in unique]

            summary = (
                f"Compiled {len(unique)} entries tagged '{tag}': "
                + "; ".join(contents[:5])
                + ("..." if len(contents) > 5 else "")
            )

            comp = CompiledKnowledge(
                title=f"Knowledge: {tag}",
                summary=summary,
                source_entries=source_ids,
                memory_type=memory_type,
                confidence=round(avg_confidence, 3),
                tags=all_tags,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            compilations.append(comp)

        # Also compile untagged entries if they are numerous enough
        if len(untagged) >= min_entries:
            contents = [e.content for e in untagged]
            avg_confidence = sum(e.confidence for e in untagged) / len(untagged)
            source_ids = [e.entry_id for e in untagged]

            summary = (
                f"Compiled {len(untagged)} untagged entries: "
                + "; ".join(contents[:5])
                + ("..." if len(contents) > 5 else "")
            )

            comp = CompiledKnowledge(
                title=f"Knowledge: untagged ({memory_type})",
                summary=summary,
                source_entries=source_ids,
                memory_type=memory_type,
                confidence=round(avg_confidence, 3),
                tags=[],
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            compilations.append(comp)

        return compilations

    # ------------------------------------------------------------------
    # Public API: TTL / Expiry Management
    # ------------------------------------------------------------------

    def purge_expired(self) -> int:
        """Remove all expired entries from the store.

        Returns:
            Number of entries purged.
        """
        purged = 0
        with self._lock:
            for mt_name in list(self.memory_store.keys()):
                entries = self.memory_store[mt_name]
                to_remove = [e for e in entries if e.is_expired()]
                for entry in to_remove:
                    self._remove_entry_file(mt_name, entry.entry_id)
                    entries.remove(entry)
                    purged += 1
        return purged

    def cleanup(self) -> int:
        """Alias for purge_expired. Returns number of purged entries."""
        return self.purge_expired()

    # ------------------------------------------------------------------
    # Public API: Linking & Relations
    # ------------------------------------------------------------------

    def link_entries(self, entry_id_a: str, entry_id_b: str) -> bool:
        """Create a bidirectional link between two memory entries.

        Args:
            entry_id_a: First entry ID.
            entry_id_b: Second entry ID.

        Returns:
            True if both entries were found and linked, False otherwise.
        """
        with self._lock:
            entry_a = None
            entry_b = None
            for entries in self.memory_store.values():
                for entry in entries:
                    if entry.entry_id == entry_id_a:
                        entry_a = entry
                    if entry.entry_id == entry_id_b:
                        entry_b = entry
                    if entry_a and entry_b:
                        break
                if entry_a and entry_b:
                    break

            if not entry_a or not entry_b:
                return False

            if entry_id_b not in entry_a.related_entries:
                entry_a.related_entries.append(entry_id_b)
                self._save_entry(entry_a)

            if entry_id_a not in entry_b.related_entries:
                entry_b.related_entries.append(entry_id_a)
                self._save_entry(entry_b)

            return True

    def get_related(self, entry_id: str) -> List[MemoryEntry]:
        """Get all entries linked to the given entry.

        Args:
            entry_id: The entry whose relations to retrieve.

        Returns:
            List of related MemoryEntry objects.
        """
        entry = self.get(entry_id)
        if not entry:
            return []

        related: List[MemoryEntry] = []
        for rid in entry.related_entries:
            rel = self.get(rid)
            if rel:
                related.append(rel)
        return related

    # ------------------------------------------------------------------
    # Public API: Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics.

        Returns:
            Dictionary with per-type counts, total, validated count,
            expired count, average confidence, and total access count.
        """
        stats: Dict[str, Any] = {}
        total = 0
        validated_count = 0
        expired_count = 0
        total_confidence = 0.0
        total_access = 0

        for mt in MemoryType:
            entries = self.memory_store.get(mt.value, [])
            count = len(entries)
            stats[mt.value] = count
            total += count

            for e in entries:
                total_confidence += e.confidence
                total_access += e.access_count
                if e.validated:
                    validated_count += 1
                if e.is_expired():
                    expired_count += 1

        stats["total"] = total
        stats["validated"] = validated_count
        stats["expired"] = expired_count
        stats["average_confidence"] = round(total_confidence / total, 3) if total > 0 else 0.0
        stats["total_access_count"] = total_access
        return stats

    def get_type_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get per-type detailed statistics.

        Returns:
            Dictionary mapping memory type to its stats (count, avg_confidence, etc.).
        """
        result: Dict[str, Dict[str, Any]] = {}
        for mt in MemoryType:
            entries = self.memory_store.get(mt.value, [])
            count = len(entries)
            if count == 0:
                result[mt.value] = {
                    "count": 0,
                    "avg_confidence": 0.0,
                    "validated": 0,
                    "expired": 0,
                }
                continue

            avg_conf = sum(e.confidence for e in entries) / count
            val_count = sum(1 for e in entries if e.validated)
            exp_count = sum(1 for e in entries if e.is_expired())
            result[mt.value] = {
                "count": count,
                "avg_confidence": round(avg_conf, 3),
                "validated": val_count,
                "expired": exp_count,
            }
        return result

    # ------------------------------------------------------------------
    # Public API: Export / Import
    # ------------------------------------------------------------------

    def export_all(self) -> Dict[str, Any]:
        """Export the entire memory store as a serializable dictionary.

        Returns:
            Dictionary mapping memory type to list of entry dicts.
        """
        export: Dict[str, Any] = {}
        for mt in MemoryType:
            entries = self.memory_store.get(mt.value, [])
            export[mt.value] = [e.to_dict() for e in entries]
        return export

    def import_entries(self, data: Dict[str, Any]) -> int:
        """Import entries from a dictionary (as produced by export_all).

        Entries with duplicate IDs are skipped.

        Args:
            data: Dictionary mapping memory type to list of entry dicts.

        Returns:
            Number of entries successfully imported.
        """
        imported = 0
        valid_types = {mt.value for mt in MemoryType}

        with self._lock:
            for mt_name, entries_list in data.items():
                if mt_name not in valid_types:
                    continue
                existing_ids = {e.entry_id for e in self.memory_store.get(mt_name, [])}
                for entry_dict in entries_list:
                    entry = MemoryEntry.from_dict(entry_dict)
                    if entry.entry_id in existing_ids:
                        continue
                    if self._save_entry(entry):
                        self.memory_store[mt_name].append(entry)
                        existing_ids.add(entry.entry_id)
                        imported += 1
        return imported

    # ------------------------------------------------------------------
    # Public API: Bulk Operations
    # ------------------------------------------------------------------

    def store_batch(
        self,
        entries_data: List[Dict[str, Any]],
    ) -> List[MemoryEntry]:
        """Store multiple memory entries in a single call.

        Each dict in entries_data should have keys matching MemoryEntry fields
        (except entry_id, which is auto-generated if not provided).

        Args:
            entries_data: List of dictionaries describing entries to store.

        Returns:
            List of successfully created MemoryEntry objects.
        """
        results: List[MemoryEntry] = []
        for data in entries_data:
            entry = self.store(
                memory_type=data.get("memory_type", ""),
                content=data.get("content", ""),
                source=data.get("source", ""),
                confidence=data.get("confidence", 1.0),
                tags=data.get("tags", []),
                metadata=data.get("metadata", {}),
                priority=data.get("priority", "normal"),
                ttl_seconds=data.get("ttl_seconds", 0),
                entry_id=data.get("entry_id"),
            )
            if entry:
                results.append(entry)
        return results

    def search_by_tag(self, tag: str, memory_type: Optional[str] = None) -> List[MemoryEntry]:
        """Find all entries that have a specific tag.

        Args:
            tag: The tag to search for.
            memory_type: Optional filter by memory type.

        Returns:
            List of matching MemoryEntry objects.
        """
        results: List[MemoryEntry] = []
        types = [memory_type] if memory_type else [mt.value for mt in MemoryType]
        for mt_name in types:
            for entry in self.memory_store.get(mt_name, []):
                if tag in entry.tags:
                    results.append(entry)
        return results

    def get_by_source(self, source: str) -> List[MemoryEntry]:
        """Find all entries from a specific source (substring match).

        Args:
            source: Source string to match against (case-insensitive substring).

        Returns:
            List of matching MemoryEntry objects.
        """
        results: List[MemoryEntry] = []
        source_lower = source.lower()
        for entries in self.memory_store.values():
            for entry in entries:
                if source_lower in entry.source.lower():
                    results.append(entry)
        return results

    def count(self, memory_type: Optional[str] = None) -> int:
        """Count entries, optionally filtered by type.

        Args:
            memory_type: Optional memory type to count.

        Returns:
            Number of entries.
        """
        if memory_type:
            return len(self.memory_store.get(memory_type, []))
        return sum(len(entries) for entries in self.memory_store.values())

    def clear_type(self, memory_type: str) -> int:
        """Remove all entries of a given memory type (from store and disk).

        Args:
            memory_type: The type to clear.

        Returns:
            Number of entries removed.
        """
        removed = 0
        with self._lock:
            entries = self.memory_store.get(memory_type, [])
            for entry in entries:
                self._remove_entry_file(memory_type, entry.entry_id)
                removed += 1
            self.memory_store[memory_type] = []
        return removed

    def clear_all(self) -> int:
        """Remove all entries across all types.

        Returns:
            Total number of entries removed.
        """
        total = 0
        for mt in MemoryType:
            total += self.clear_type(mt.value)
        return total


# ======================================================================
# Convenience helper
# ======================================================================

def create_agent_memory(
    products_dir: str = "products",
    project: str = "default",
) -> AgentMemory:
    """Helper to create an AgentMemory instance.

    Args:
        products_dir: Root products directory.
        project: Project name.

    Returns:
        A configured AgentMemory instance.
    """
    return AgentMemory(products_dir=products_dir, project=project)
