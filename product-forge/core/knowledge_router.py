"""
Knowledge Router - Phase 2.3

Intelligently routes knowledge/skill requests to the most relevant
resources based on the current task, agent, and stage.

Phase 2.3 (IMPORTANT): Knowledge Router - reduces context bloat by
loading only relevant knowledge for each task.
"""
import json
import re
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict
from collections import Counter


@dataclass
class KnowledgeResource:
    """A knowledge resource that can be loaded."""
    id: str
    title: str
    path: str
    domain: str  # "frontend", "backend", "security", etc.
    tags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    priority: int = 50
    size_tokens: int = 0
    last_used: Optional[str] = None
    use_count: int = 0
    last_verified: Optional[str] = None
    file_valid: bool = True


@dataclass
class RoutingDecision:
    """A decision on what knowledge to load."""
    task_description: str
    selected_resources: list[str]  # Resource IDs
    total_tokens: int
    confidence: float
    reasoning: str
    excluded: list[str] = field(default_factory=list)
    stage: Optional[str] = None
    agent: Optional[str] = None
    freshness_warnings: list[str] = field(default_factory=list)


class KnowledgeRouter:
    """
    Routes knowledge requests to relevant resources.
    
    Phase 2.3: Smart skill loading based on task context.
    
    Enhancements (Phase E):
    - stage and agent context parameters for task-aware routing
    - Pipeline-definition-aware routing (can filter by pipeline type)
    - Configurable token budget (not just class constant)
    - Knowledge freshness tracking (last_verified timestamp)
    - Basic knowledge validation (check if file exists, is readable)
    """
    
    INDEX_FILE = "knowledge_index.json"
    MAX_TOKENS_PER_LOAD = 10000
    MIN_CONFIDENCE = 0.1
    FRESHNESS_THRESHOLD_DAYS = 30
    
    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.index_file = self.products_dir / ".pipeline" / self.INDEX_FILE
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.index_file.exists():
            self._initialize()
        
        self.resources: dict[str, KnowledgeResource] = self._load()
    
    def _initialize(self) -> None:
        """Initialize with discovered resources."""
        resources = self._auto_discover()
        data = {
            "resources": [asdict(r) for r in resources],
            "created_at": datetime.utcnow().isoformat(),
        }
        self.index_file.write_text(json.dumps(data, indent=2, default=str))
    
    def _auto_discover(self) -> list[KnowledgeResource]:
        """Auto-discover knowledge resources from guidelines."""
        resources = []
        guidelines_dir = self.products_dir.parent / "docs" / "guidelines"
        
        if not guidelines_dir.exists():
            return resources
        
        for md_file in guidelines_dir.rglob("*.md"):
            if md_file.name == "README.md":
                continue
            
            try:
                content = md_file.read_text(encoding="utf-8")
                tokens = len(content) // 4
                
                rel_path = md_file.relative_to(guidelines_dir)
                parts = rel_path.parts
                domain = parts[0] if parts else "general"
                
                keywords = []
                for line in content.split("\n")[:50]:
                    if line.startswith("#"):
                        words = re.findall(r"\b\w+\b", line.lower())
                        keywords.extend([w for w in words if len(w) > 3])
                
                resource = KnowledgeResource(
                    id=str(rel_path).replace("\\", "/").replace("/", ".").replace(".md", ""),
                    title=md_file.stem.replace("-", " ").replace("_", " ").title(),
                    path=str(md_file.relative_to(self.products_dir.parent)),
                    domain=domain,
                    tags=parts[:-1] if len(parts) > 1 else [],
                    keywords=list(set(keywords))[:20],
                    priority=50,
                    size_tokens=tokens,
                    last_verified=datetime.utcnow().isoformat(),
                    file_valid=True,
                )
                resources.append(resource)
            except (OSError, UnicodeDecodeError):
                continue
        
        return resources
    
    def _load(self) -> dict[str, KnowledgeResource]:
        """Load resources from index."""
        try:
            data = json.loads(self.index_file.read_text())
            result = {}
            for r in data.get("resources", []):
                try:
                    result[r["id"]] = KnowledgeResource(**r)
                except TypeError:
                    # Handle old format without new fields
                    r.setdefault("last_verified", None)
                    r.setdefault("file_valid", True)
                    result[r["id"]] = KnowledgeResource(**r)
            return result
        except (json.JSONDecodeError, OSError, TypeError):
            self._initialize()
            return {r.id: r for r in self._auto_discover()}
    
    def _save(self) -> None:
        """Save index to disk."""
        data = {
            "resources": [asdict(r) for r in self.resources.values()],
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.index_file.write_text(json.dumps(data, indent=2, default=str))
    
    def register_resource(self, resource: KnowledgeResource) -> None:
        """Register a new knowledge resource."""
        self.resources[resource.id] = resource
        self._save()
    
    def validate_resource(self, resource: KnowledgeResource) -> bool:
        """
        Validate that a resource's underlying file exists and is readable.
        
        Returns True if valid, False otherwise. Updates resource.file_valid.
        """
        full_path = self.products_dir.parent / resource.path
        try:
            if not full_path.exists():
                resource.file_valid = False
                return False
            if not full_path.is_file():
                resource.file_valid = False
                return False
            # Try to read a small portion to confirm readability
            with open(full_path, "r", encoding="utf-8") as f:
                f.read(1024)
            resource.file_valid = True
            return True
        except (OSError, UnicodeDecodeError, PermissionError):
            resource.file_valid = False
            return False
    
    def validate_all_resources(self) -> dict[str, bool]:
        """
        Validate all registered resources. Returns a dict of resource_id -> valid.
        Also updates last_verified timestamp for validated resources.
        """
        results = {}
        now = datetime.utcnow().isoformat()
        for resource_id, resource in self.resources.items():
            is_valid = self.validate_resource(resource)
            if is_valid:
                resource.last_verified = now
            results[resource_id] = is_valid
        self._save()
        return results
    
    def get_stale_resources(self, max_age_days: Optional[int] = None) -> list[KnowledgeResource]:
        """
        Get resources that haven't been verified within the threshold.
        
        Args:
            max_age_days: Override the default freshness threshold
            
        Returns:
            List of stale KnowledgeResource objects
        """
        threshold = max_age_days or self.FRESHNESS_THRESHOLD_DAYS
        now = datetime.utcnow()
        stale = []
        
        for resource in self.resources.values():
            if resource.last_verified is None:
                stale.append(resource)
                continue
            try:
                verified_dt = datetime.fromisoformat(resource.last_verified)
                age_days = (now - verified_dt).days
                if age_days > threshold:
                    stale.append(resource)
            except (ValueError, TypeError):
                stale.append(resource)
        
        return stale
    
    def _score_resource(
        self,
        resource: KnowledgeResource,
        task: str,
        domain: Optional[str] = None,
        tags: Optional[list[str]] = None,
        stage: Optional[str] = None,
        agent: Optional[str] = None,
        pipeline_type: Optional[str] = None,
    ) -> float:
        """Score a resource's relevance to a task."""
        score = 0.0
        task_lower = task.lower()
        
        # Domain match
        if domain and resource.domain == domain:
            score += 0.3
        
        # Tag match
        if tags:
            tag_overlap = len(set(tags) & set(resource.tags))
            score += 0.1 * tag_overlap
        
        # Keyword match in task
        for keyword in resource.keywords:
            if keyword in task_lower:
                score += 0.05
        
        # Title match
        title_words = resource.title.lower().split()
        for word in title_words:
            if word in task_lower and len(word) > 3:
                score += 0.1
        
        # Stage-aware scoring: boost resources whose domain matches stage context
        if stage:
            stage_lower = stage.lower()
            if resource.domain in stage_lower or stage_lower in resource.domain:
                score += 0.15
            # Boost stage-specific keywords
            for keyword in resource.keywords:
                if keyword in stage_lower:
                    score += 0.05
        
        # Agent-aware scoring: boost resources whose domain matches agent role
        if agent:
            agent_lower = agent.lower()
            if resource.domain in agent_lower or agent_lower in resource.domain:
                score += 0.15
            for keyword in resource.keywords:
                if keyword in agent_lower:
                    score += 0.05
        
        # Pipeline-type filtering: penalize resources unrelated to pipeline type
        if pipeline_type:
            pt_lower = pipeline_type.lower()
            # If resource domain has no overlap with pipeline type, reduce score
            if pt_lower not in resource.domain and resource.domain not in pt_lower:
                score *= 0.7  # 30% penalty for unrelated domains
        
        # Priority boost
        score += resource.priority / 1000
        
        # Recent use boost
        if resource.use_count > 0:
            score += min(0.1, resource.use_count * 0.01)
        
        # Freshness penalty: reduce score for unverified resources
        if resource.last_verified is None:
            score -= 0.05  # Never verified: small flat penalty
        elif resource.file_valid is False:
            score *= 0.5  # Known invalid: 50% penalty
        
        return min(1.0, score)
    
    def route(
        self,
        task: str,
        domain: Optional[str] = None,
        tags: Optional[list[str]] = None,
        max_tokens: Optional[int] = None,
        stage: Optional[str] = None,
        agent: Optional[str] = None,
        pipeline_type: Optional[str] = None,
    ) -> RoutingDecision:
        """
        Route a task to the most relevant knowledge resources.
        
        Args:
            task: Task description
            domain: Preferred domain (e.g., "frontend")
            tags: Tags to match
            max_tokens: Max tokens to load (defaults to MAX_TOKENS_PER_LOAD)
            stage: Current pipeline stage (e.g., "4a", "implement")
            agent: Current agent name (e.g., "implement", "design")
            pipeline_type: Filter by pipeline type (e.g., "web", "mobile", "api")
        
        Returns:
            Routing decision with selected resources
        """
        # Allow configurable token budget, fall back to class constant
        token_budget = max_tokens if max_tokens is not None else self.MAX_TOKENS_PER_LOAD
        
        if not self.resources:
            return RoutingDecision(
                task_description=task,
                selected_resources=[],
                total_tokens=0,
                confidence=0.0,
                reasoning="No resources available",
                stage=stage,
                agent=agent,
            )
        
        # Score all resources with context
        scored = [
            (r, self._score_resource(r, task, domain, tags, stage, agent, pipeline_type))
            for r in self.resources.values()
        ]
        
        # Sort by score desc
        scored.sort(key=lambda x: -x[1])
        
        # Select until budget exhausted
        selected = []
        total_tokens = 0
        excluded = []
        freshness_warnings = []
        
        for resource, score in scored:
            if score < self.MIN_CONFIDENCE:
                excluded.append(resource.id)
                continue
            
            if total_tokens + resource.size_tokens > token_budget:
                excluded.append(resource.id)
                continue
            
            # Warn about stale resources
            if resource.last_verified is None:
                freshness_warnings.append(
                    f"{resource.id}: never verified"
                )
            else:
                try:
                    verified_dt = datetime.fromisoformat(resource.last_verified)
                    age_days = (datetime.utcnow() - verified_dt).days
                    if age_days > self.FRESHNESS_THRESHOLD_DAYS:
                        freshness_warnings.append(
                            f"{resource.id}: verified {age_days}d ago"
                        )
                except (ValueError, TypeError):
                    freshness_warnings.append(
                        f"{resource.id}: invalid last_verified"
                    )
            
            selected.append(resource)
            total_tokens += resource.size_tokens
            resource.use_count += 1
            resource.last_used = datetime.utcnow().isoformat()
        
        self._save()
        
        # Calculate confidence
        if selected:
            avg_score = sum(
                self._score_resource(r, task, domain, tags, stage, agent, pipeline_type)
                for r in selected
            ) / len(selected)
            confidence = avg_score
        else:
            confidence = 0.0
        
        # Build reasoning string
        context_parts = []
        if stage:
            context_parts.append(f"stage={stage}")
        if agent:
            context_parts.append(f"agent={agent}")
        if pipeline_type:
            context_parts.append(f"pipeline={pipeline_type}")
        context_str = f" with context [{', '.join(context_parts)}]" if context_parts else ""
        
        return RoutingDecision(
            task_description=task,
            selected_resources=[r.id for r in selected],
            total_tokens=total_tokens,
            confidence=round(confidence, 2),
            reasoning=f"Selected {len(selected)} resources from {len(self.resources)} available based on {domain or 'task'}-based scoring{context_str}",
            excluded=excluded[:10],
            stage=stage,
            agent=agent,
            freshness_warnings=freshness_warnings,
        )
    
    def get_stats(self) -> dict:
        """Get knowledge router statistics."""
        domains = Counter(r.domain for r in self.resources.values())
        total_size = sum(r.size_tokens for r in self.resources.values())
        used = sum(1 for r in self.resources.values() if r.use_count > 0)
        valid = sum(1 for r in self.resources.values() if r.file_valid)
        stale = len(self.get_stale_resources())
        
        return {
            "total_resources": len(self.resources),
            "total_tokens": total_size,
            "by_domain": dict(domains),
            "used_resources": used,
            "unused_resources": len(self.resources) - used,
            "valid_resources": valid,
            "invalid_resources": len(self.resources) - valid,
            "stale_resources": stale,
            "freshness_threshold_days": self.FRESHNESS_THRESHOLD_DAYS,
        }
    
    def get_resource_content(self, resource_id: str) -> Optional[str]:
        """Get actual content of a knowledge resource."""
        resource = self.resources.get(resource_id)
        if not resource:
            return None
        
        try:
            with open(resource.path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None
    
    def get_routing_content(self, decision: RoutingDecision, max_tokens: int = 5000) -> str:
        """Get actual content for routing decision.
        
        Args:
            decision: RoutingDecision with selected resource IDs
            max_tokens: Maximum tokens to return
            
        Returns:
            Combined content from selected resources
        """
        combined_content = []
        total_tokens = 0
        
        for resource_id in decision.selected_resources:
            content = self.get_resource_content(resource_id)
            if content:
                tokens = len(content) // 4
                if total_tokens + tokens > max_tokens:
                    # Truncate to fit
                    remaining = (max_tokens - total_tokens) * 4
                    content = content[:remaining] + "\n...[truncated to fit token budget]"
                    combined_content.append(content)
                    break
                
                combined_content.append(content)
                total_tokens += tokens
        
        return "\n\n---\n\n".join(combined_content)
