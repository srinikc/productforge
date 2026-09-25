"""
Memory Batch/Export API
High-level API for batch operations on the memory system.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Iterator
from dataclasses import dataclass, field, asdict

from core.agent_memory import AgentMemory, MemoryType, MemoryEntry, MemoryQuery, RetrievalStrategy


@dataclass
class ExportBundle:
    """A bundle of memory entries for export."""
    project: str
    exported_at: str
    entry_count: int
    entries: List[Dict]
    metadata: Dict = field(default_factory=dict)


@dataclass
class ImportResult:
    """Result of an import operation."""
    total_processed: int
    successful: int
    failed: int
    skipped: int
    errors: List[str] = field(default_factory=list)


class MemoryAPI:
    """
    High-level API for memory batch operations.

    Provides:
    - Batch store/retrieve
    - Export/Import to JSON
    - Bulk delete by criteria
    - Memory analytics
    - Migration support
    """

    def __init__(self, products_dir: str = "products", project: str = "default"):
        self.memory = AgentMemory(products_dir=products_dir, project=project)
        self.products_dir = products_dir
        self.project = project

    # ---- Batch Store ----

    def store_batch(
        self,
        entries: List[Dict],
        skip_duplicates: bool = True
    ) -> ImportResult:
        """
        Store multiple memory entries in batch.

        Each entry dict should have:
        - memory_type: str (e.g., "semantic", "episodic")
        - content: str
        - source: str
        - confidence: float (optional, default 0.9)
        - tags: List[str] (optional)
        - metadata: Dict (optional)
        """
        result = ImportResult(
            total_processed=len(entries),
            successful=0,
            failed=0,
            skipped=0,
            errors=[]
        )

        for i, entry_data in enumerate(entries):
            try:
                # Check for duplicate
                if skip_duplicates:
                    existing = self.memory.retrieve(MemoryQuery(
                        query=entry_data.get("content", ""),
                        min_confidence=0.0,
                        max_results=5
                    ))
                    if any(e.content == entry_data.get("content") for e in existing):
                        result.skipped += 1
                        continue

                # Store the entry
                stored = self.memory.store(
                    memory_type=entry_data.get("memory_type", "semantic"),
                    content=entry_data.get("content", ""),
                    source=entry_data.get("source", "unknown"),
                    confidence=entry_data.get("confidence", 0.9),
                    tags=entry_data.get("tags", []),
                    metadata=entry_data.get("metadata", {})
                )

                if stored:
                    result.successful += 1
                else:
                    result.failed += 1
                    result.errors.append(f"Entry {i}: store returned None")

            except Exception as e:
                result.failed += 1
                result.errors.append(f"Entry {i}: {str(e)}")

        return result

    # ---- Batch Retrieve ----

    def retrieve_batch(
        self,
        queries: List[str],
        min_confidence: float = 0.5,
        max_per_query: int = 10
    ) -> Dict[str, List[MemoryEntry]]:
        """Retrieve entries for multiple queries."""
        results = {}
        for query in queries:
            results[query] = self.memory.retrieve(MemoryQuery(
                query=query,
                min_confidence=min_confidence,
                max_results=max_per_query
            ))
        return results

    # ---- Export ----

    def export_all(self, include_metadata: bool = True) -> ExportBundle:
        """Export all memory entries."""
        entries = []
        for memory_type in MemoryType:
            type_entries = self.memory.list_entries(memory_type=memory_type.value)
            for entry in type_entries:
                entry_dict = entry.to_dict() if hasattr(entry, "to_dict") else asdict(entry)
                if not include_metadata:
                    entry_dict.pop("metadata", None)
                entries.append(entry_dict)

        return ExportBundle(
            project=self.project,
            exported_at=datetime.now().isoformat(),
            entry_count=len(entries),
            entries=entries,
            metadata={
                "memory_types": [mt.value for mt in MemoryType],
                "version": "1.0"
            }
        )

    def export_by_type(self, memory_type: str) -> ExportBundle:
        """Export entries of a specific type."""
        entries = self.memory.list_entries(memory_type=memory_type)
        entry_dicts = []
        for entry in entries:
            entry_dict = entry.to_dict() if hasattr(entry, "to_dict") else asdict(entry)
            entry_dicts.append(entry_dict)

        return ExportBundle(
            project=self.project,
            exported_at=datetime.now().isoformat(),
            entry_count=len(entry_dicts),
            entries=entry_dicts,
            metadata={"memory_type": memory_type, "version": "1.0"}
        )

    def save_export(self, bundle: ExportBundle, output_path: str = None) -> str:
        """Save export bundle to a file."""
        if output_path is None:
            export_dir = Path(self.products_dir) / self.project / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            output_path = str(export_dir / f"memory-export-{timestamp}.json")

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(bundle), f, indent=2, ensure_ascii=False)

        return output_path

    # ---- Import ----

    def load_export(self, file_path: str) -> ExportBundle:
        """Load an export bundle from a file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return ExportBundle(
            project=data.get("project", "unknown"),
            exported_at=data.get("exported_at", ""),
            entry_count=data.get("entry_count", 0),
            entries=data.get("entries", []),
            metadata=data.get("metadata", {})
        )

    def import_bundle(
        self,
        bundle: ExportBundle,
        skip_duplicates: bool = True,
        overwrite: bool = False
    ) -> ImportResult:
        """Import entries from a bundle."""
        return self.store_batch(bundle.entries, skip_duplicates=skip_duplicates)

    def import_file(
        self,
        file_path: str,
        skip_duplicates: bool = True
    ) -> ImportResult:
        """Import from an export file."""
        bundle = self.load_export(file_path)
        return self.import_bundle(bundle, skip_duplicates=skip_duplicates)

    # ---- Bulk Operations ----

    def delete_by_tag(self, tag: str) -> int:
        """Delete all entries with a specific tag."""
        count = 0
        for memory_type in MemoryType:
            entries = self.memory.list_entries(memory_type=memory_type.value)
            for entry in entries:
                if tag in (entry.tags or []):
                    self.memory.delete(entry.entry_id)
                    count += 1
        return count

    def delete_by_source(self, source: str) -> int:
        """Delete all entries from a specific source."""
        count = 0
        for memory_type in MemoryType:
            entries = self.memory.list_entries(memory_type=memory_type.value)
            for entry in entries:
                if entry.source == source:
                    self.memory.delete(entry.entry_id)
                    count += 1
        return count

    def delete_expired(self) -> int:
        """Delete all expired entries."""
        count = 0
        for memory_type in MemoryType:
            entries = self.memory.list_entries(memory_type=memory_type.value)
            for entry in entries:
                if hasattr(entry, "is_expired") and entry.is_expired():
                    self.memory.delete(entry.entry_id)
                    count += 1
        return count

    # ---- Analytics ----

    def get_analytics(self) -> Dict:
        """Get memory analytics."""
        total_entries = 0
        type_counts = {}
        confidence_sum = 0.0
        source_counts = {}
        tag_counts = {}
        oldest_entry = None
        newest_entry = None

        for memory_type in MemoryType:
            entries = self.memory.list_entries(memory_type=memory_type.value)
            type_counts[memory_type.value] = len(entries)
            total_entries += len(entries)

            for entry in entries:
                confidence_sum += entry.confidence
                source_counts[entry.source] = source_counts.get(entry.source, 0) + 1

                for tag in (entry.tags or []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

                entry_time = entry.timestamp
                if oldest_entry is None or entry_time < oldest_entry:
                    oldest_entry = entry_time
                if newest_entry is None or entry_time > newest_entry:
                    newest_entry = entry_time

        avg_confidence = (confidence_sum / total_entries) if total_entries > 0 else 0

        # Top sources and tags
        top_sources = sorted(source_counts.items(), key=lambda x: -x[1])[:10]
        top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:10]

        return {
            "total_entries": total_entries,
            "by_type": type_counts,
            "avg_confidence": avg_confidence,
            "unique_sources": len(source_counts),
            "unique_tags": len(tag_counts),
            "top_sources": top_sources,
            "top_tags": top_tags,
            "oldest_entry": oldest_entry or "",
            "newest_entry": newest_entry or ""
        }

    # ---- Migration ----

    def migrate_from_legacy(self, legacy_data: List[Dict]) -> ImportResult:
        """
        Migrate from a legacy memory format.

        Expects dicts with at minimum:
        - type or memory_type
        - content or text
        - source
        """
        converted = []
        for item in legacy_data:
            converted.append({
                "memory_type": item.get("type") or item.get("memory_type") or "semantic",
                "content": item.get("content") or item.get("text") or "",
                "source": item.get("source") or "legacy_migration",
                "confidence": item.get("confidence", 0.8),
                "tags": item.get("tags", []),
                "metadata": item.get("metadata", {})
            })

        return self.store_batch(converted, skip_duplicates=False)
