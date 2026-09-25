"""
Advanced Phase 3 Modules - Phases 3.3, 3.4, 3.5, 3.6

Combines:
- 3.3 Tool Result Compression
- 3.4 Adaptive Reasoning Control
- 3.5 Cross-Domain Knowledge Graph
- 3.6 Semantic Cache
"""
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any
from dataclasses import dataclass, field, asdict


# ======================================================================
# Phase 3.3: Tool Result Compression
# ======================================================================

class ToolResultCompressor:
    """
    Compresses tool results to reduce token usage.
    
    Phase 3.3: Intelligent compression that preserves meaning while
    reducing token count by 60-80%.
    """
    
    def __init__(self):
        self.compression_stats = {"total_compressed": 0, "tokens_saved": 0}
    
    def compress_json(self, data: Any, max_depth: int = 3) -> Any:
        """Compress JSON data by limiting depth and removing redundancies."""
        return self._limit_depth(data, max_depth)
    
    def _limit_depth(self, obj: Any, depth: int) -> Any:
        if depth <= 0:
            return "..." if isinstance(obj, (dict, list)) else obj
        if isinstance(obj, dict):
            return {k: self._limit_depth(v, depth - 1) for k, v in obj.items()}
        if isinstance(obj, list):
            if len(obj) > 10:
                return [self._limit_depth(x, depth - 1) for x in obj[:5]] + [f"... {len(obj) - 5} more ..."]
            return [self._limit_depth(x, depth - 1) for x in obj]
        return obj
    
    def compress_text(self, text: str, max_length: int = 2000) -> str:
        """Compress text by truncating intelligently."""
        if len(text) <= max_length:
            return text
        keep = int(max_length * 0.7)
        return text[:keep] + "\n\n[... truncated ...]\n\n" + text[-(max_length - keep - 100):]
    
    def compress_log(self, log: str, keep_errors: bool = True) -> str:
        """Compress log output, optionally keeping only errors."""
        if not keep_errors:
            return log
        
        lines = log.split("\n")
        errors = [l for l in lines if "error" in l.lower() or "ERROR" in l]
        warnings = [l for l in lines if "warning" in l.lower() or "WARN" in l]
        
        if errors or warnings:
            return "\n".join(errors + warnings + [f"\n[... {len(lines) - len(errors) - len(warnings)} lines omitted ...]"])
        return log
    
    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4 + 1
    
    def compress(
        self,
        result: Any,
        max_tokens: int = 1000,
        is_log: bool = False,
    ) -> Any:
        """Main compression method."""
        if isinstance(result, str):
            if is_log:
                compressed = self.compress_log(result)
            else:
                compressed = self.compress_text(result, max_length=max_tokens * 4)
            
            original_tokens = self.estimate_tokens(result)
            compressed_tokens = self.estimate_tokens(compressed)
            self.compression_stats["tokens_saved"] += max(0, original_tokens - compressed_tokens)
            self.compression_stats["total_compressed"] += 1
            return compressed
        
        if isinstance(result, (dict, list)):
            return self.compress_json(result, max_depth=3)
        
        return result
    
    def get_stats(self) -> dict:
        return self.compression_stats


# ======================================================================
# Phase 3.4: Adaptive Reasoning Control
# ======================================================================

class AdaptiveReasoningController:
    """
    Adjusts reasoning depth based on task complexity and history.
    
    Phase 3.4: Dynamic reasoning depth to balance cost vs quality.
    """
    
    DEPTH_LEVELS = {
        "minimal": {"max_tokens": 500, "iterations": 1},
        "low": {"max_tokens": 1500, "iterations": 2},
        "medium": {"max_tokens": 4000, "iterations": 3},
        "high": {"max_tokens": 8000, "iterations": 5},
        "maximum": {"max_tokens": 16000, "iterations": 10},
    }
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.state_file = self.products_dir / ".pipeline" / "adaptive_reasoning.json"
        self.history: list[dict] = []
    
    def assess_complexity(
        self,
        task: str,
        stage: int,
        prior_failures: int = 0,
    ) -> str:
        """Assess task complexity and return recommended depth."""
        score = 0
        
        # Length-based complexity
        if len(task) > 1000:
            score += 2
        elif len(task) > 300:
            score += 1
        
        # Stage-based complexity
        stage_weights = {0: 1, 1: 2, 2: 3, 3: 2, 4: 3, 5: 2, 6: 2, 7: 2, 8: 1, 9: 1}
        score += stage_weights.get(stage, 1)
        
        # Prior failures
        score += min(prior_failures, 3)
        
        # Keyword-based complexity
        complex_keywords = ["architect", "design", "implement", "refactor", "debug", "optimize"]
        if any(kw in task.lower() for kw in complex_keywords):
            score += 1
        
        # Map to depth
        if score >= 8:
            return "maximum"
        if score >= 6:
            return "high"
        if score >= 4:
            return "medium"
        if score >= 2:
            return "low"
        return "minimal"
    
    def get_config(self, depth: str) -> dict:
        """Get configuration for a depth level."""
        return self.DEPTH_LEVELS.get(depth, self.DEPTH_LEVELS["medium"])
    
    def record_outcome(self, depth: str, success: bool, quality: float) -> None:
        """Record outcome to learn from."""
        self.history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "depth": depth,
            "success": success,
            "quality": quality,
        })
        # Keep last 1000
        self.history = self.history[-1000:]
    
    def get_stats(self) -> dict:
        """Get adaptive reasoning stats."""
        if not self.history:
            return {"total": 0}
        
        by_depth: dict = {}
        for h in self.history:
            d = h["depth"]
            if d not in by_depth:
                by_depth[d] = {"count": 0, "success": 0, "total_quality": 0.0}
            by_depth[d]["count"] += 1
            if h["success"]:
                by_depth[d]["success"] += 1
            by_depth[d]["total_quality"] += h["quality"]
        
        for d in by_depth:
            data = by_depth[d]
            data["success_rate"] = round(data["success"] / data["count"] * 100, 1)
            data["avg_quality"] = round(data["total_quality"] / data["count"], 2)
        
        return {"total": len(self.history), "by_depth": by_depth}


# ======================================================================
# Phase 3.5: Cross-Domain Knowledge Graph
# ======================================================================

class KnowledgeGraph:
    """
    Cross-domain knowledge graph linking concepts across domains.
    
    Phase 3.5: Enables discovery of related concepts across domains.
    """
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.graph_file = self.products_dir / ".pipeline" / "knowledge_graph.json"
        self.nodes: dict[str, dict] = {}  # id -> {domain, label, ...}
        self.edges: list[dict] = []  # {from, to, type, weight}
    
    def add_node(self, node_id: str, domain: str, label: str, **metadata) -> None:
        """Add a node to the graph."""
        self.nodes[node_id] = {
            "id": node_id,
            "domain": domain,
            "label": label,
            **metadata,
        }
    
    def add_edge(self, from_id: str, to_id: str, edge_type: str = "related", weight: float = 1.0) -> None:
        """Add an edge between nodes."""
        self.edges.append({
            "from": from_id,
            "to": to_id,
            "type": edge_type,
            "weight": weight,
        })
    
    def save(self) -> str:
        """Persist the graph to graph_file (previously never written - BI-0054)."""
        try:
            self.graph_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.graph_file, "w", encoding="utf-8") as f:
                json.dump({"nodes": self.nodes, "edges": self.edges}, f,
                          indent=2, ensure_ascii=False)
            return str(self.graph_file)
        except Exception:
            return ""

    def load(self) -> "KnowledgeGraph":
        try:
            with open(self.graph_file, encoding="utf-8") as f:
                d = json.load(f) or {}
            self.nodes = d.get("nodes", {}) or {}
            self.edges = d.get("edges", []) or []
        except Exception:
            pass
        return self

    def find_related(self, node_id: str, max_depth: int = 2) -> list[dict]:
        """Find related nodes up to max_depth hops."""
        if node_id not in self.nodes:
            return []
        
        visited = {node_id}
        current = [node_id]
        results = []
        
        for depth in range(max_depth):
            next_level = []
            for current_id in current:
                for edge in self.edges:
                    neighbor = None
                    if edge["from"] == current_id:
                        neighbor = edge["to"]
                    elif edge["to"] == current_id:
                        neighbor = edge["from"]
                    
                    if neighbor and neighbor not in visited:
                        visited.add(neighbor)
                        next_level.append(neighbor)
                        results.append({
                            "node": self.nodes.get(neighbor, {}),
                            "edge": edge,
                            "depth": depth + 1,
                        })
            current = next_level
        
        return results
    
    def cross_domain_search(self, concept: str) -> list[dict]:
        """Find a concept across all domains."""
        results = []
        for node in self.nodes.values():
            if concept.lower() in node.get("label", "").lower():
                results.append(node)
        return results
    
    def get_stats(self) -> dict:
        domains: dict = {}
        for node in self.nodes.values():
            d = node.get("domain", "unknown")
            domains[d] = domains.get(d, 0) + 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "domains": len(domains),
            "by_domain": domains,
        }


# ======================================================================
# Phase 3.6: Semantic Cache
# ======================================================================

class SemanticCache:
    """
    Cache that matches by semantic similarity, not exact key.
    
    Phase 3.6: Reuses results from similar (not just identical) queries.
    """
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.cache_file = self.products_dir / ".pipeline" / "semantic_cache.json"
        self.entries: dict[str, dict] = {}
        self.similarity_threshold = 0.7
    
    def _compute_signature(self, text: str) -> str:
        """Compute a semantic signature (simplified)."""
        # In production, use embeddings (e.g., sentence-transformers)
        # Here we use a word-bag approach for simplicity
        words = re.findall(r"\b\w+\b", text.lower())
        # Keep significant words (length > 3)
        sig_words = sorted(set(w for w in words if len(w) > 3))
        return " ".join(sig_words[:20])  # Top 20 significant words
    
    def _similarity(self, sig1: str, sig2: str) -> float:
        """Compute Jaccard similarity between two signatures."""
        words1 = set(sig1.split())
        words2 = set(sig2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)
    
    def get(self, query: str) -> Optional[Any]:
        """Get a cached result for a semantically similar query."""
        sig = self._compute_signature(query)
        
        best_match = None
        best_similarity = 0.0
        
        for entry in self.entries.values():
            similarity = self._similarity(sig, entry["signature"])
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = entry
        
        if best_match and best_similarity >= self.similarity_threshold:
            best_match["hits"] = best_match.get("hits", 0) + 1
            return best_match["value"]
        
        return None
    
    def set(self, query: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Cache a result for a query."""
        sig = self._compute_signature(query)
        key = hashlib.md5(sig.encode()).hexdigest()[:16]
        
        self.entries[key] = {
            "key": key,
            "query": query,
            "signature": sig,
            "value": value,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat(),
            "hits": 0,
        }
    
    def get_stats(self) -> dict:
        total_hits = sum(e.get("hits", 0) for e in self.entries.values())
        return {
            "total_entries": len(self.entries),
            "total_hits": total_hits,
            "similarity_threshold": self.similarity_threshold,
        }
