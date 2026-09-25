"""Dashboard Archetypes - Reusable layout templates for different dashboard types.

Provides 4 standard archetypes:
- Executive: Headline KPIs → Trends → Business drivers → Exceptions → Details
- Operational: Current status → Alerts → Work queue → Performance → Historical
- Sales/Pipeline: Pipeline summary → Stage distribution → Movement → Priority → Forecast
- Analytics: KPIs → Trend → Segmentation → Comparison → Drill-down

Agents should select the appropriate archetype based on the product design spec.
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


@dataclass
class ArchetypeSection:
    """A section in a dashboard archetype."""
    name: str
    description: str
    position: str  # top, middle, bottom, sidebar
    priority: int  # 1=highest
    component_type: str  # kpi, chart, table, list, action, alert


@dataclass
class DashboardArchetype:
    """A dashboard archetype definition."""
    id: str
    name: str
    description: str
    sections: List[ArchetypeSection] = field(default_factory=list)
    layout: str = "grid"  # grid, flex, sidebar
    grid_columns: int = 12
    responsive_breakpoints: Dict[str, int] = field(default_factory=dict)
    design_principles: List[str] = field(default_factory=list)
    things_to_avoid: List[str] = field(default_factory=list)


# Standard archetypes
ARCHETYPES = {
    "executive": DashboardArchetype(
        id="executive",
        name="Executive Dashboard",
        description="High-level overview for decision makers. Focus on KPIs, trends, and exceptions.",
        sections=[
            ArchetypeSection("Headline KPIs", "Key performance indicators at a glance", "top", 1, "kpi"),
            ArchetypeSection("Trends", "Performance over time", "middle", 2, "chart"),
            ArchetypeSection("Business Drivers", "Factors affecting performance", "middle", 3, "chart"),
            ArchetypeSection("Exceptions", "Items requiring attention", "middle", 4, "alert"),
            ArchetypeSection("Details", "Drill-down data", "bottom", 5, "table"),
        ],
        layout="grid",
        grid_columns=12,
        responsive_breakpoints={"mobile": 4, "tablet": 8, "desktop": 12},
        design_principles=[
            "Lead with numbers, not charts",
            "Show variance from targets",
            "Highlight what changed since last view",
            "Progressive disclosure - summary first, details on click",
        ],
        things_to_avoid=[
            "Too many metrics on one screen",
            "Charts without clear labels",
            "Data dumps without context",
            "Missing time comparisons",
        ],
    ),
    
    "operational": DashboardArchetype(
        id="operational",
        name="Operational Dashboard",
        description="Real-time monitoring for operations teams. Focus on current status and alerts.",
        sections=[
            ArchetypeSection("Current Status", "Live system status", "top", 1, "kpi"),
            ArchetypeSection("Alerts / Exceptions", "Items needing immediate attention", "top", 2, "alert"),
            ArchetypeSection("Work Queue", "Pending tasks and items", "middle", 3, "list"),
            ArchetypeSection("Performance", "Real-time metrics", "middle", 4, "chart"),
            ArchetypeSection("Historical Trends", "Performance over time", "bottom", 5, "chart"),
        ],
        layout="grid",
        grid_columns=12,
        responsive_breakpoints={"mobile": 4, "tablet": 8, "desktop": 12},
        design_principles=[
            "Real-time data refresh",
            "Color-code status (green/yellow/red)",
            "Prominent alerts and notifications",
            "Quick action buttons for common tasks",
        ],
        things_to_avoid=[
            "Stale data without timestamps",
            "Buried critical alerts",
            "Too much historical data",
            "Complex navigation",
        ],
    ),
    
    "sales_pipeline": DashboardArchetype(
        id="sales_pipeline",
        name="Sales Pipeline Dashboard",
        description="Pipeline management for sales teams. Focus on opportunities and forecast.",
        sections=[
            ArchetypeSection("Pipeline Summary", "Total pipeline value and metrics", "top", 1, "kpi"),
            ArchetypeSection("Stage Distribution", "Opportunities by stage", "middle", 2, "chart"),
            ArchetypeSection("Pipeline Movement", "Deals moving between stages", "middle", 3, "chart"),
            ArchetypeSection("Priority Opportunities", "High-value deals to focus on", "middle", 4, "list"),
            ArchetypeSection("Forecast", "Revenue forecast", "bottom", 5, "chart"),
            ArchetypeSection("Opportunity Details", "Full opportunity list", "bottom", 6, "table"),
        ],
        layout="grid",
        grid_columns=12,
        responsive_breakpoints={"mobile": 4, "tablet": 8, "desktop": 12},
        design_principles=[
            "Show pipeline value prominently",
            "Highlight deal velocity",
            "Color-code by probability",
            "Enable quick deal updates",
        ],
        things_to_avoid=[
            "Cluttered opportunity lists",
            "Missing win/loss rates",
            "No time-based trends",
            "Hidden bottlenecks",
        ],
    ),
    
    "analytics": DashboardArchetype(
        id="analytics",
        name="Analytics Dashboard",
        description="Data exploration for analysts. Focus on trends, segments, and comparisons.",
        sections=[
            ArchetypeSection("KPIs", "Key metrics with targets", "top", 1, "kpi"),
            ArchetypeSection("Trend", "Performance over time", "middle", 2, "chart"),
            ArchetypeSection("Segmentation", "Data by category", "middle", 3, "chart"),
            ArchetypeSection("Comparison", "Period-over-period or category comparison", "middle", 4, "chart"),
            ArchetypeSection("Drill-down", "Detailed data exploration", "bottom", 5, "table"),
        ],
        layout="grid",
        grid_columns=12,
        responsive_breakpoints={"mobile": 4, "tablet": 8, "desktop": 12},
        design_principles=[
            "Enable data exploration",
            "Provide filters and date ranges",
            "Show statistical significance",
            "Support drill-down to raw data",
        ],
        things_to_avoid=[
            "Overwhelming with too many charts",
            "Missing data labels",
            "No clear narrative",
            "Charts that don't communicate insights",
        ],
    ),
}


def get_archetype(archetype_id: str) -> Optional[DashboardArchetype]:
    """Get an archetype by ID."""
    return ARCHETYPES.get(archetype_id)


def list_archetypes() -> List[Dict[str, str]]:
    """List all available archetypes."""
    return [{"id": a.id, "name": a.name, "description": a.description} for a in ARCHETYPES.values()]


def select_archetype(product_goal: str, primary_user: str, dashboard_type: str = "") -> str:
    """Select the best archetype based on product characteristics."""
    # Simple keyword-based selection
    goal_lower = product_goal.lower()
    user_lower = primary_user.lower()
    
    if any(kw in goal_lower for kw in ["executive", "overview", "summary", "c-level"]):
        return "executive"
    elif any(kw in goal_lower for kw in ["monitor", "status", "alert", "real-time", "operations"]):
        return "operational"
    elif any(kw in goal_lower for kw in ["sales", "pipeline", "deal", "revenue", "crm"]):
        return "sales_pipeline"
    elif any(kw in goal_lower for kw in ["analytics", "analysis", "report", "insight", "data"]):
        return "analytics"
    elif any(kw in user_lower for kw in ["executive", "ceo", "cfo", "manager"]):
        return "executive"
    elif any(kw in user_lower for kw in ["analyst", "data", "researcher"]):
        return "analytics"
    else:
        return "operational"  # Default


def archetype_to_dict(archetype: DashboardArchetype) -> Dict:
    """Convert archetype to dict for serialization."""
    return {
        "id": archetype.id,
        "name": archetype.name,
        "description": archetype.description,
        "sections": [{"name": s.name, "description": s.description, "position": s.position, "priority": s.priority, "component_type": s.component_type} for s in archetype.sections],
        "layout": archetype.layout,
        "grid_columns": archetype.grid_columns,
        "responsive_breakpoints": archetype.responsive_breakpoints,
        "design_principles": archetype.design_principles,
        "things_to_avoid": archetype.things_to_avoid,
    }


def generate_archetype_report(archetype_id: str, project: str, products_dir: str = "products") -> str:
    """Generate an archetype report for a project."""
    archetype = get_archetype(archetype_id)
    if not archetype:
        return f"Unknown archetype: {archetype_id}"
    
    report = f"""# Dashboard Archetype: {archetype.name}

## Project: {project}

## Description
{archetype.description}

## Layout
- Type: {archetype.layout}
- Grid Columns: {archetype.grid_columns}
- Responsive Breakpoints: {archetype.responsive_breakpoints}

## Sections

"""
    for section in sorted(archetype.sections, key=lambda s: s.priority):
        report += f"### {section.name} (Priority {section.priority})\n"
        report += f"- **Description:** {section.description}\n"
        report += f"- **Position:** {section.position}\n"
        report += f"- **Component Type:** {section.component_type}\n\n"
    
    report += "## Design Principles\n\n"
    for principle in archetype.design_principles:
        report += f"- {principle}\n"
    
    report += "\n## Things to Avoid\n\n"
    for item in archetype.things_to_avoid:
        report += f"- {item}\n"
    
    report += f"\n---\n*Generated by Dashboard Archetypes module*\n"
    
    return report


if __name__ == "__main__":
    # Test archetypes
    print("Available archetypes:")
    for arch in list_archetypes():
        print(f"  - {arch['id']}: {arch['name']}")
    
    # Test selection
    archetype_id = select_archetype("Build a sales pipeline tracker", "sales manager")
    print(f"\nSelected archetype: {archetype_id}")
    
    # Generate report
    report = generate_archetype_report(archetype_id, "test-project")
    print(f"\nReport generated ({len(report)} chars)")
