"""Cross-Project Learning - shares insights, patterns, and lessons across projects.

Extracts reusable knowledge from completed projects and applies them to new ones.
Complements agent_memory.py with project-level aggregation and transfer.
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ProjectInsight:
    insight_id: str
    project: str
    insight_type: str  # pattern, anti_pattern, lesson, shortcut, tool_recommendation
    category: str  # code, design, architecture, testing, deployment, process
    title: str
    description: str
    evidence: str  # What happened that led to this insight
    impact: str  # high, medium, low
    confidence: float  # 0-1
    reusable: bool = True
    tags: List[str] = field(default_factory=list)
    created_at: str = ""


@dataclass
class ProjectSummary:
    project: str
    status: str  # completed, active, archived
    total_cost: float = 0.0
    total_tokens: int = 0
    stages_completed: int = 0
    agents_used: List[str] = field(default_factory=list)
    key_decisions: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)
    duration_days: float = 0.0
    success_rating: float = 0.0  # 0-10


@dataclass
class LearningState:
    insights: List[ProjectInsight] = field(default_factory=list)
    project_summaries: List[ProjectSummary] = field(default_factory=list)
    patterns_catalog: Dict[str, List[str]] = field(default_factory=dict)
    anti_patterns_catalog: Dict[str, List[str]] = field(default_factory=dict)


def extract_insights_from_project(project_dir: str) -> List[ProjectInsight]:
    """Extract insights from a completed project's artifacts and memory."""
    insights = []
    project_name = os.path.basename(project_dir)

    # Check for memory files
    memory_dir = os.path.join(project_dir, "memory")
    if os.path.isdir(memory_dir):
        for fname in os.listdir(memory_dir):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(memory_dir, fname), "r", encoding="utf-8") as f:
                        memories = json.load(f)
                    if isinstance(memories, list):
                        for mem in memories:
                            if isinstance(mem, dict):
                                content = mem.get("content", "")
                                mem_type = mem.get("type", "")
                                if mem_type == "failure":
                                    insights.append(ProjectInsight(
                                        insight_id=f"{project_name}-failure-{len(insights)}",
                                        project=project_name,
                                        insight_type="anti_pattern",
                                        category="process",
                                        title=f"Failure in {mem.get('source', 'unknown')}",
                                        description=content[:200],
                                        evidence=content,
                                        impact="medium",
                                        confidence=0.8,
                                        tags=[mem.get("source", ""), "failure"],
                                        created_at=mem.get("timestamp", ""),
                                    ))
                                elif mem_type == "decision":
                                    insights.append(ProjectInsight(
                                        insight_id=f"{project_name}-decision-{len(insights)}",
                                        project=project_name,
                                        insight_type="lesson",
                                        category="process",
                                        title=f"Decision: {content[:80]}",
                                        description=content[:200],
                                        evidence=content,
                                        impact="medium",
                                        confidence=0.7,
                                        tags=["decision"],
                                        created_at=mem.get("timestamp", ""),
                                    ))
                except Exception:
                    pass

    # Check for budget data
    budget_file = os.path.join(project_dir, "pipeline.json")
    if os.path.exists(budget_file):
        try:
            with open(budget_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            agents = list(config.get("agents", {}).keys())
            if agents:
                insights.append(ProjectInsight(
                    insight_id=f"{project_name}-agents-{len(insights)}",
                    project=project_name,
                    insight_type="pattern",
                    category="process",
                    title=f"Used {len(agents)} agents",
                    description=f"Agents: {', '.join(agents[:5])}",
                    evidence=json.dumps(agents),
                    impact="low",
                    confidence=0.9,
                    tags=["agents", "process"],
                ))
        except Exception:
            pass

    return insights


def build_learning_index(products_dir: str) -> LearningState:
    """Build a cross-project learning index from all projects."""
    state = LearningState()

    if not os.path.isdir(products_dir):
        return state

    for entry in os.listdir(products_dir):
        project_dir = os.path.join(products_dir, entry)
        if os.path.isdir(project_dir) and not entry.startswith("."):
            insights = extract_insights_from_project(project_dir)
            state.insights.extend(insights)

            # Build project summary
            summary = ProjectSummary(
                project=entry,
                status="completed" if insights else "unknown",
            )
            state.project_summaries.append(summary)

    # Build patterns catalog
    for insight in state.insights:
        if insight.reusable:
            key = f"{insight.category}:{insight.insight_type}"
            if key not in state.patterns_catalog:
                state.patterns_catalog[key] = []
            state.patterns_catalog[key].append(insight.title)

    return state


def get_relevant_insights(
    state: LearningState,
    category: str,
    insight_type: Optional[str] = None,
    limit: int = 10,
) -> List[ProjectInsight]:
    """Get relevant insights for a given category."""
    results = []
    for insight in state.insights:
        if insight.category == category and insight.reusable:
            if insight_type is None or insight.insight_type == insight_type:
                results.append(insight)
    results.sort(key=lambda x: x.confidence * (1.0 if x.impact == "high" else 0.7 if x.impact == "medium" else 0.4), reverse=True)
    return results[:limit]


def suggest_for_project(
    state: LearningState,
    project_type: str,
    tech_stack: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Suggest patterns and anti-patterns for a new project."""
    patterns = []
    anti_patterns = []
    tools = []

    for insight in state.insights:
        if not insight.reusable:
            continue
        if insight.insight_type == "pattern":
            patterns.append({"title": insight.title, "description": insight.description, "confidence": insight.confidence})
        elif insight.insight_type == "anti_pattern":
            anti_patterns.append({"title": insight.title, "description": insight.description, "evidence": insight.evidence})
        elif insight.insight_type == "tool_recommendation":
            tools.append({"title": insight.title, "description": insight.description})

    return {
        "project_type": project_type,
        "suggested_patterns": patterns[:5],
        "avoid_anti_patterns": anti_patterns[:5],
        "recommended_tools": tools[:3],
        "total_insights": len(state.insights),
        "total_projects_analyzed": len(state.project_summaries),
    }


def learning_to_dict(state: LearningState) -> Dict[str, Any]:
    return {
        "total_insights": len(state.insights),
        "total_projects": len(state.project_summaries),
        "patterns_catalog": {k: len(v) for k, v in state.patterns_catalog.items()},
        "insights_by_type": {},
        "insights_by_category": {},
        "recent_insights": [
            {"title": i.title, "type": i.insight_type, "project": i.project, "confidence": i.confidence}
            for i in sorted(state.insights, key=lambda x: x.created_at, reverse=True)[:20]
        ],
    }
