"""
Cost Modeling
Estimates cloud costs, infrastructure costs, and operational expenses
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict


@dataclass
class CloudCostEstimate:
    """Cloud cost estimate for a service"""
    service: str
    provider: str  # aws, gcp, azure
    instance_type: str
    quantity: int
    hours_per_month: int
    cost_per_hour: float
    monthly_cost: float
    annual_cost: float
    notes: str = ""


@dataclass
class InfrastructureCost:
    """Infrastructure cost breakdown"""
    compute: List[CloudCostEstimate] = field(default_factory=list)
    storage: List[CloudCostEstimate] = field(default_factory=list)
    database: List[CloudCostEstimate] = field(default_factory=list)
    networking: List[CloudCostEstimate] = field(default_factory=list)
    other: List[CloudCostEstimate] = field(default_factory=list)
    total_monthly: float = 0.0
    total_annual: float = 0.0

    def calculate_totals(self):
        """Calculate total costs"""
        all_costs = self.compute + self.storage + self.database + self.networking + self.other
        self.total_monthly = sum(c.monthly_cost for c in all_costs)
        self.total_annual = self.total_monthly * 12


class CostModeler:
    """Models and estimates costs for products"""

    def __init__(self):
        self.pricing_data = self._load_pricing_data()

    def _load_pricing_data(self) -> Dict[str, Any]:
        """Load cloud pricing data"""
        return {
            "aws": {
                "compute": {
                    "t3.micro": 0.0104,
                    "t3.small": 0.0208,
                    "t3.medium": 0.0416,
                    "t3.large": 0.0832,
                    "m5.large": 0.096,
                    "m5.xlarge": 0.192,
                    "c5.large": 0.085,
                    "c5.xlarge": 0.17
                },
                "storage": {
                    "gp2": 0.10,  # per GB/month
                    "io1": 0.125,
                    "s3_standard": 0.023,
                    "s3_ia": 0.0125
                },
                "database": {
                    "rds_t3_micro": 0.018,
                    "rds_t3_small": 0.036,
                    "rds_t3_medium": 0.073,
                    "rds_m5_large": 0.171,
                    "dynamodb": 0.00000125  # per RCU
                },
                "networking": {
                    "data_transfer": 0.09,  # per GB
                    "cloudfront": 0.085,
                    "route53": 0.50  # per hosted zone
                }
            },
            "gcp": {
                "compute": {
                    "e2_micro": 0.008,
                    "e2_small": 0.0167,
                    "e2_medium": 0.0335,
                    "n1_standard_1": 0.0475,
                    "n1_standard_2": 0.095
                },
                "storage": {
                    "pd_standard": 0.04,
                    "pd_ssd": 0.17,
                    "gcs_standard": 0.020
                },
                "database": {
                    "cloud_sql_f1_micro": 0.015,
                    "cloud_sql_g1_small": 0.035
                },
                "networking": {
                    "data_transfer": 0.08,
                    "cdn": 0.08
                }
            },
            "azure": {
                "compute": {
                    "b1s": 0.0104,
                    "b2s": 0.0416,
                    "b2ms": 0.0832,
                    "d2s_v3": 0.096,
                    "d4s_v3": 0.192
                },
                "storage": {
                    "standard_hdd": 0.040,
                    "standard_ssd": 0.12
                },
                "database": {
                    "sql_db_basic": 0.005,
                    "sql_db_s0": 0.020
                },
                "networking": {
                    "data_transfer": 0.087,
                    "cdn": 0.081
                }
            }
        }

    def estimate_compute_cost(self, provider: str, instance_type: str,
                              quantity: int = 1, hours_per_month: int = 730) -> CloudCostEstimate:
        """Estimate compute cost"""
        provider_data = self.pricing_data.get(provider, {})
        compute_pricing = provider_data.get("compute", {})
        cost_per_hour = compute_pricing.get(instance_type, 0.05)  # Default estimate

        monthly_cost = cost_per_hour * hours_per_month * quantity
        annual_cost = monthly_cost * 12

        return CloudCostEstimate(
            service="compute",
            provider=provider,
            instance_type=instance_type,
            quantity=quantity,
            hours_per_month=hours_per_month,
            cost_per_hour=cost_per_hour,
            monthly_cost=monthly_cost,
            annual_cost=annual_cost,
            notes=f"{quantity}x {instance_type} running {hours_per_month}h/month"
        )

    def estimate_storage_cost(self, provider: str, storage_type: str,
                              size_gb: int) -> CloudCostEstimate:
        """Estimate storage cost"""
        provider_data = self.pricing_data.get(provider, {})
        storage_pricing = provider_data.get("storage", {})
        cost_per_gb = storage_pricing.get(storage_type, 0.10)  # Default estimate

        monthly_cost = cost_per_gb * size_gb
        annual_cost = monthly_cost * 12

        return CloudCostEstimate(
            service="storage",
            provider=provider,
            instance_type=storage_type,
            quantity=size_gb,
            hours_per_month=730,
            cost_per_hour=cost_per_gb / 730,
            monthly_cost=monthly_cost,
            annual_cost=annual_cost,
            notes=f"{size_gb}GB of {storage_type}"
        )

    def estimate_database_cost(self, provider: str, instance_type: str,
                                quantity: int = 1, hours_per_month: int = 730) -> CloudCostEstimate:
        """Estimate database cost"""
        provider_data = self.pricing_data.get(provider, {})
        db_pricing = provider_data.get("database", {})
        cost_per_hour = db_pricing.get(instance_type, 0.05)  # Default estimate

        monthly_cost = cost_per_hour * hours_per_month * quantity
        annual_cost = monthly_cost * 12

        return CloudCostEstimate(
            service="database",
            provider=provider,
            instance_type=instance_type,
            quantity=quantity,
            hours_per_month=hours_per_month,
            cost_per_hour=cost_per_hour,
            monthly_cost=monthly_cost,
            annual_cost=annual_cost,
            notes=f"{quantity}x {instance_type} database"
        )

    def estimate_networking_cost(self, provider: str, data_transfer_gb: int) -> CloudCostEstimate:
        """Estimate networking cost"""
        provider_data = self.pricing_data.get(provider, {})
        net_pricing = provider_data.get("networking", {})
        cost_per_gb = net_pricing.get("data_transfer", 0.09)  # Default estimate

        monthly_cost = cost_per_gb * data_transfer_gb
        annual_cost = monthly_cost * 12

        return CloudCostEstimate(
            service="networking",
            provider=provider,
            instance_type="data_transfer",
            quantity=data_transfer_gb,
            hours_per_month=730,
            cost_per_hour=cost_per_gb / 730,
            monthly_cost=monthly_cost,
            annual_cost=annual_cost,
            notes=f"{data_transfer_gb}GB data transfer"
        )

    def estimate_product_costs(self, product_type: str, scale: str = "small") -> InfrastructureCost:
        """Estimate costs for a product based on type and scale"""
        cost = InfrastructureCost()

        # Define cost profiles based on product type and scale
        profiles = {
            "small": {
                "compute": [("t3.micro", 1, 730)],
                "storage": [("gp2", 20)],
                "database": [("rds_t3_micro", 1, 730)],
                "networking": [(10)]  # 10GB
            },
            "medium": {
                "compute": [("t3.medium", 2, 730), ("t3.large", 1, 730)],
                "storage": [("gp2", 100)],
                "database": [("rds_t3_medium", 1, 730)],
                "networking": [(100)]  # 100GB
            },
            "large": {
                "compute": [("m5.large", 4, 730), ("c5.xlarge", 2, 730)],
                "storage": [("gp2", 500), ("io1", 100)],
                "database": [("rds_m5_large", 2, 730)],
                "networking": [(1000)]  # 1TB
            }
        }

        profile = profiles.get(scale, profiles["small"])

        # Compute costs
        for instance_type, quantity, hours in profile["compute"]:
            estimate = self.estimate_compute_cost("aws", instance_type, quantity, hours)
            cost.compute.append(estimate)

        # Storage costs
        for storage_type, size_gb in profile["storage"]:
            estimate = self.estimate_storage_cost("aws", storage_type, size_gb)
            cost.storage.append(estimate)

        # Database costs
        for instance_type, quantity, hours in profile["database"]:
            estimate = self.estimate_database_cost("aws", instance_type, quantity, hours)
            cost.database.append(estimate)

        # Networking costs
        for data_gb in profile["networking"]:
            estimate = self.estimate_networking_cost("aws", data_gb)
            cost.networking.append(estimate)

        cost.calculate_totals()
        return cost

    def generate_cost_report(self, product_name: str, cost: InfrastructureCost) -> str:
        """Generate cost report"""
        report = f"""# {product_name} - Cost Analysis Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Executive Summary

**Total Monthly Cost:** ${cost.total_monthly:,.2f}
**Total Annual Cost:** ${cost.total_annual:,.2f}

## Cost Breakdown

### Compute Services
"""
        for c in cost.compute:
            report += f"- **{c.instance_type}** (x{c.quantity}): ${c.monthly_cost:,.2f}/month, ${c.annual_cost:,.2f}/year\n"
            report += f"  - {c.notes}\n"

        report += "\n### Storage Services\n"
        for s in cost.storage:
            report += f"- **{s.instance_type}** ({s.quantity}GB): ${s.monthly_cost:,.2f}/month, ${s.annual_cost:,.2f}/year\n"
            report += f"  - {s.notes}\n"

        report += "\n### Database Services\n"
        for d in cost.database:
            report += f"- **{d.instance_type}** (x{d.quantity}): ${d.monthly_cost:,.2f}/month, ${d.annual_cost:,.2f}/year\n"
            report += f"  - {d.notes}\n"

        report += "\n### Networking Services\n"
        for n in cost.networking:
            report += f"- **{n.instance_type}** ({n.quantity}GB): ${n.monthly_cost:,.2f}/month, ${n.annual_cost:,.2f}/year\n"
            report += f"  - {n.notes}\n"

        report += f"""
## Cost Optimization Recommendations

1. **Reserved Instances:** Save up to 75% by committing to 1-3 year terms
2. **Spot Instances:** Save up to 90% for fault-tolerant workloads
3. **Auto Scaling:** Scale down during off-peak hours
4. **Storage Optimization:** Use appropriate storage classes for access patterns
5. **Data Transfer:** Minimize cross-region transfer costs
6. **Monitoring:** Use CloudWatch/Cloud Monitoring to identify waste
7. **Right Sizing:** Regularly review and downsize over-provisioned resources
8. **Cleanup:** Remove unused resources (snapshots, volumes, IPs)

## Scaling Projections

### Current (Baseline)
- Monthly: ${cost.total_monthly:,.2f}
- Annual: ${cost.total_annual:,.2f}

### 2x Growth
- Monthly: ${cost.total_monthly * 2:,.2f}
- Annual: ${cost.total_annual * 2:,.2f}

### 5x Growth
- Monthly: ${cost.total_monthly * 5:,.2f}
- Annual: ${cost.total_annual * 5:,.2f}

### 10x Growth
- Monthly: ${cost.total_monthly * 10:,.2f}
- Annual: ${cost.total_annual * 10:,.2f}

## Cost Monitoring

### Key Metrics
- Daily cost spend
- Monthly cost trend
- Cost per customer
- Cost per transaction
- Cost anomalies

### Alerts
- Daily spend > $X
- Monthly spend > $X
- Unusual spikes
- Budget exceeded

## Best Practices

1. **Tag Everything:** Use cost allocation tags
2. **Monitor Daily:** Set up dashboards and alerts
3. **Review Monthly:** Identify optimization opportunities
4. **Automate Cleanup:** Remove unused resources automatically
5. **Use Spot/Reserved:** For predictable workloads
6. **Right Size:** Continuously optimize instance types
7. **Multi-Cloud:** Consider multi-cloud for cost arbitrage
8. **FinOps Culture:** Make cost everyone's responsibility
"""

        return report
