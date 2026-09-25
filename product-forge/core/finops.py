"""
FinOps
Cost optimization, budget management, and financial insights
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class CostItem:
    """Individual cost item"""
    service: str
    resource: str
    cost: float
    date: str
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class Budget:
    """Budget allocation and tracking"""
    name: str
    amount: float
    period: str  # monthly, quarterly, annually
    start_date: str
    end_date: str
    spent: float = 0.0
    alerts: List[float] = field(default_factory=list)  # percentage thresholds

    @property
    def remaining(self) -> float:
        return self.amount - self.spent

    @property
    def utilization(self) -> float:
        if self.amount == 0:
            return 0.0
        return (self.spent / self.amount) * 100

    @property
    def is_over_budget(self) -> bool:
        return self.spent > self.amount


@dataclass
class OptimizationRecommendation:
    """Cost optimization recommendation"""
    title: str
    description: str
    category: str  # rightsizing, scheduling, cleanup, reserved, spot
    estimated_savings: float
    priority: str  # critical, high, medium, low
    effort: str  # low, medium, high
    implementation_steps: List[str] = field(default_factory=list)


class FinOpsManager:
    """Manages FinOps, cost optimization, and budgets"""

    def __init__(self, products_dir: str = "products"):
        self.products_dir = Path(products_dir)
        self.cost_items: List[CostItem] = []
        self.budgets: List[Budget] = []

    def add_cost_item(self, item: CostItem):
        """Add a cost item"""
        self.cost_items.append(item)

    def get_costs_by_service(self) -> Dict[str, float]:
        """Get total costs by service"""
        by_service = {}
        for item in self.cost_items:
            by_service[item.service] = by_service.get(item.service, 0) + item.cost
        return by_service

    def get_costs_by_tag(self, tag_key: str) -> Dict[str, float]:
        """Get costs by tag value"""
        by_tag = {}
        for item in self.cost_items:
            tag_value = item.tags.get(tag_key, "untagged")
            by_tag[tag_value] = by_tag.get(tag_value, 0) + item.cost
        return by_tag

    def create_budget(self, budget: Budget):
        """Create a budget"""
        self.budgets.append(budget)

    def update_budget_spend(self, budget_name: str, amount: float):
        """Update budget spend"""
        for budget in self.budgets:
            if budget.name == budget_name:
                budget.spent += amount
                break

    def get_budget_status(self) -> List[Dict[str, Any]]:
        """Get status of all budgets"""
        statuses = []
        for budget in self.budgets:
            status = {
                "name": budget.name,
                "amount": budget.amount,
                "spent": budget.spent,
                "remaining": budget.remaining,
                "utilization": budget.utilization,
                "is_over_budget": budget.is_over_budget
            }
            statuses.append(status)
        return statuses

    def generate_optimization_recommendations(self) -> List[OptimizationRecommendation]:
        """Generate cost optimization recommendations"""
        recommendations = []

        # Check for high costs
        costs_by_service = self.get_costs_by_service()
        for service, cost in costs_by_service.items():
            if cost > 1000:  # Threshold for review
                recommendations.append(OptimizationRecommendation(
                    title=f"Right-size {service} resources",
                    description=f"High spend detected on {service} (${cost:,.2f}). Review instance sizes and usage patterns.",
                    category="rightsizing",
                    estimated_savings=cost * 0.20,
                    priority="high",
                    effort="low",
                    implementation_steps=[
                        f"Analyze {service} usage metrics",
                        f"Identify over-provisioned resources",
                        f"Downsize to appropriate instance types",
                        f"Monitor performance after change"
                    ]
                ))

        # Check for budgets
        for budget in self.budgets:
            if budget.utilization > 80:
                recommendations.append(OptimizationRecommendation(
                    title=f"Budget alert: {budget.name}",
                    description=f"Budget '{budget.name}' is {budget.utilization:.1f}% utilized. Review spending.",
                    category="cleanup",
                    estimated_savings=budget.remaining * 0.10,
                    priority="critical" if budget.is_over_budget else "high",
                    effort="low",
                    implementation_steps=[
                        "Review recent cost increases",
                        "Identify cost drivers",
                        "Implement spending controls",
                        "Set up alerts"
                    ]
                ))

        # General recommendations
        recommendations.append(OptimizationRecommendation(
            title="Use Reserved Instances",
            description="Purchase 1-year Reserved Instances for predictable workloads to save up to 40%.",
            category="reserved",
            estimated_savings=500.0,
            priority="medium",
            effort="low",
            implementation_steps=[
                "Analyze usage patterns",
                "Identify baseline workload",
                "Purchase Reserved Instances",
                "Monitor utilization"
            ]
        ))

        recommendations.append(OptimizationRecommendation(
            title="Implement Auto Scaling",
            description="Scale resources based on demand to reduce idle capacity costs.",
            category="scheduling",
            estimated_savings=300.0,
            priority="medium",
            effort="medium",
            implementation_steps=[
                "Set up auto scaling policies",
                "Define scaling triggers",
                "Test scaling behavior",
                "Monitor cost impact"
            ]
        ))

        return recommendations

    def generate_finops_report(self) -> str:
        """Generate FinOps report"""
        report = f"""# FinOps Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Cost Summary

**Total Costs Tracked:** ${sum(item.cost for item in self.cost_items):,.2f}

### Costs by Service

"""
        costs_by_service = self.get_costs_by_service()
        for service, cost in sorted(costs_by_service.items(), key=lambda x: x[1], reverse=True):
            report += f"- **{service}:** ${cost:,.2f}\n"

        report += "\n## Budget Status\n\n"
        for status in self.get_budget_status():
            report += f"### {status['name']}\n"
            report += f"- **Amount:** ${status['amount']:,.2f}\n"
            report += f"- **Spent:** ${status['spent']:,.2f}\n"
            report += f"- **Remaining:** ${status['remaining']:,.2f}\n"
            report += f"- **Utilization:** {status['utilization']:.1f}%\n"
            if status['is_over_budget']:
                report += f"- **Status:** OVER BUDGET\n"
            report += "\n"

        report += "## Optimization Recommendations\n\n"
        recommendations = self.generate_optimization_recommendations()
        for i, rec in enumerate(recommendations, 1):
            report += f"### {i}. {rec.title}\n\n"
            report += f"**Category:** {rec.category}\n"
            report += f"**Priority:** {rec.priority}\n"
            report += f"**Effort:** {rec.effort}\n"
            report += f"**Estimated Savings:** ${rec.estimated_savings:,.2f}/month\n\n"
            report += f"{rec.description}\n\n"
            if rec.implementation_steps:
                report += "**Implementation Steps:**\n"
                for step in rec.implementation_steps:
                    report += f"1. {step}\n"
                report += "\n"

        return report
