"""
Test Selector - AI-driven test selection based on product type and domain
"""

from typing import Dict, List, Any, Optional
from enum import Enum

class ProductType(Enum):
    EXPLORATION = "exploration"
    LEARNING = "learning"
    FUN = "fun"
    PROTOTYPE = "prototype"
    PERSONAL = "personal"
    INTERNAL = "internal"
    PRODUCT = "product"
    BUSINESS = "business"

class ProductDomain(Enum):
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    ECOMMERCE = "ecommerce"
    EDUCATION = "education"
    SOCIAL = "social"
    GOVERNMENT = "government"
    IOT = "iot"
    AI_ML = "ai_ml"
    BLOCKCHAIN = "blockchain"
    PRODUCTIVITY = "productivity"
    GAMING = "gaming"
    GENERAL = "general"

class TestSelector:
    """AI-driven test selection based on product characteristics"""
    
    def __init__(self):
        # Test category requirements by product type
        self.type_requirements = {
            ProductType.EXPLORATION: {
                "unit": True,
                "api": True,
                "integration": False,
                "e2e": False,
                "visual": False,
                "performance": False,
                "security": False,
                "install": False,
                "load": False,
                "stress": False,
                "db": False
            },
            ProductType.LEARNING: {
                "unit": True,
                "api": True,
                "integration": True,
                "e2e": True,
                "visual": False,
                "performance": False,
                "security": False,
                "install": False,
                "load": False,
                "stress": False,
                "db": False
            },
            ProductType.FUN: {
                "unit": True,
                "api": True,
                "integration": False,
                "e2e": True,
                "visual": True,
                "performance": False,
                "security": False,
                "install": False,
                "load": False,
                "stress": False,
                "db": False
            },
            ProductType.PROTOTYPE: {
                "unit": True,
                "api": True,
                "integration": True,
                "e2e": True,
                "visual": True,
                "performance": False,
                "security": False,
                "install": True,
                "load": False,
                "stress": False,
                "db": True
            },
            ProductType.PERSONAL: {
                "unit": True,
                "api": True,
                "integration": True,
                "e2e": True,
                "visual": True,
                "performance": False,
                "security": False,
                "install": True,
                "load": False,
                "stress": False,
                "db": True
            },
            ProductType.INTERNAL: {
                "unit": True,
                "api": True,
                "integration": True,
                "e2e": True,
                "visual": True,
                "performance": True,
                "security": False,
                "install": True,
                "load": False,
                "stress": False,
                "db": True
            },
            ProductType.PRODUCT: {
                "unit": True,
                "api": True,
                "integration": True,
                "e2e": True,
                "visual": True,
                "performance": True,
                "security": True,
                "install": True,
                "load": True,
                "stress": False,
                "db": True
            },
            ProductType.BUSINESS: {
                "unit": True,
                "api": True,
                "integration": True,
                "e2e": True,
                "visual": True,
                "performance": True,
                "security": True,
                "install": True,
                "load": True,
                "stress": True,
                "db": True
            }
        }
        
        # Domain-specific additional requirements
        self.domain_requirements = {
            ProductDomain.FINANCE: {
                "security": True,
                "performance": True,
                "stress": True,
                "compliance": ["PCI-DSS", "SOC2"]
            },
            ProductDomain.HEALTHCARE: {
                "security": True,
                "compliance": ["HIPAA", "GDPR"]
            },
            ProductDomain.ECOMMERCE: {
                "performance": True,
                "load": True,
                "security": True
            },
            ProductDomain.GOVERNMENT: {
                "security": True,
                "compliance": ["FISMA", "FedRAMP"]
            },
            ProductDomain.IOT: {
                "performance": True,
                "stress": True
            },
            ProductDomain.AI_ML: {
                "performance": True,
                "stress": True
            },
            ProductDomain.BLOCKCHAIN: {
                "security": True,
                "performance": True
            },
            ProductDomain.GAMING: {
                "performance": True,
                "visual": True
            }
        }
    
    def select_tests(self, product_type: str, product_domain: str,
                     has_database: bool = False, has_api: bool = True) -> Dict[str, Any]:
        """Select test categories based on product characteristics"""
        
        # Get base requirements from product type
        try:
            ptype = ProductType(product_type)
            base_tests = self.type_requirements.get(ptype, self.type_requirements[ProductType.GENERAL]).copy()
        except ValueError:
            base_tests = self.type_requirements[ProductType.GENERAL].copy()
        
        # Get domain-specific requirements
        try:
            pdomain = ProductDomain(product_domain)
            domain_tests = self.domain_requirements.get(pdomain, {})
        except ValueError:
            domain_tests = {}
        
        # Merge requirements (domain overrides type)
        for category, required in domain_tests.items():
            if isinstance(required, bool):
                base_tests[category] = required
        
        # Adjust based on product characteristics
        if not has_database:
            base_tests["db"] = False
            base_tests["integration"] = False
        
        if not has_api:
            base_tests["api"] = False
        
        # Calculate priority order for test execution
        priority_order = self._calculate_priority_order(base_tests, product_type, product_domain)
        
        # Estimate test duration
        duration_estimate = self._estimate_duration(base_tests)
        
        # Get recommended test suites
        recommended_suites = self._get_recommended_suites(base_tests, product_type)
        
        return {
            "product_type": product_type,
            "product_domain": product_domain,
            "test_categories": base_tests,
            "priority_order": priority_order,
            "duration_estimate": duration_estimate,
            "recommended_suites": recommended_suites,
            "compliance_requirements": domain_tests.get("compliance", []),
            "reasoning": self._generate_reasoning(product_type, product_domain, base_tests)
        }
    
    def _calculate_priority_order(self, tests: Dict[str, bool], 
                                  product_type: str, product_domain: str) -> List[str]:
        """Calculate priority order for test execution"""
        enabled = [cat for cat, enabled in tests.items() if enabled]
        
        # Base priority order
        priority = ["unit", "api", "db", "integration", "e2e", "visual", 
                    "performance", "load", "stress", "security", "install"]
        
        # Sort by priority, keeping only enabled tests
        return [cat for cat in priority if cat in enabled]
    
    def _estimate_duration(self, tests: Dict[str, bool]) -> str:
        """Estimate total test duration"""
        duration_map = {
            "unit": 5,
            "api": 10,
            "db": 10,
            "integration": 20,
            "e2e": 30,
            "visual": 15,
            "performance": 30,
            "load": 45,
            "stress": 60,
            "security": 20,
            "install": 25
        }
        
        total_minutes = sum(duration_map.get(cat, 10) for cat, enabled in tests.items() if enabled)
        
        if total_minutes < 60:
            return f"{total_minutes} minutes"
        else:
            hours = total_minutes // 60
            mins = total_minutes % 60
            return f"{hours} hours {mins} minutes"
    
    def _get_recommended_suites(self, tests: Dict[str, bool], product_type: str) -> List[str]:
        """Get recommended test suites"""
        suites = []
        
        # Always recommend smoke
        if tests.get("unit") or tests.get("api"):
            suites.append("smoke")
        
        # Sanity for more complete testing
        if tests.get("integration"):
            suites.append("sanity")
        
        # Daily for comprehensive
        if tests.get("e2e"):
            suites.append("daily")
        
        # Weekly for non-functional
        if tests.get("performance") or tests.get("security"):
            suites.append("weekly")
        
        # Full for production-ready
        if product_type in ["product", "business"]:
            suites.append("full")
        
        return suites
    
    def _generate_reasoning(self, product_type: str, product_domain: str,
                           tests: Dict[str, bool]) -> str:
        """Generate reasoning for test selection"""
        reasons = []
        
        # Type-based reasoning
        type_reasons = {
            "exploration": "Minimal testing needed for exploration projects",
            "learning": "Core functionality testing for learning projects",
            "fun": "Visual and E2E testing important for fun projects",
            "prototype": "Prototype needs basic validation and deployment tests",
            "personal": "Personal projects need standard testing",
            "internal": "Internal tools need performance testing",
            "product": "Products need comprehensive testing including security",
            "business": "Business applications need full test coverage"
        }
        
        reasons.append(type_reasons.get(product_type, "Standard testing"))
        
        # Domain-based reasoning
        domain_reasons = {
            "finance": "Financial apps require security and performance testing",
            "healthcare": "Healthcare apps require security and compliance",
            "ecommerce": "E-commerce needs performance and load testing",
            "government": "Government apps require security and compliance",
            "gaming": "Gaming apps need performance and visual testing"
        }
        
        if product_domain in domain_reasons:
            reasons.append(domain_reasons[product_domain])
        
        return "; ".join(reasons)
    
    def get_test_config_for_product(self, project_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate test configuration for a product based on its config"""
        product_type = project_config.get("type", "general")
        product_domain = project_config.get("domain", "general")
        
        # Detect characteristics from config
        has_database = "db" in str(project_config).lower() or "database" in str(project_config).lower()
        has_api = "api" in str(project_config).lower() or project_config.get("apps", {}).get("api")
        
        return self.select_tests(product_type, product_domain, has_database, has_api)
