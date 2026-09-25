"""
Budget Protection Test
Validates that the budget protection system prevents token exhaustion
and that knowledge routing respects budget limits.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'

passed = 0
failed = 0
errors = []

def test(name, func):
    global passed, failed
    try:
        result = func()
        if result:
            passed += 1
            print(f"  {GREEN}✓{RESET} {name}")
        else:
            failed += 1
            errors.append(name)
            print(f"  {RED}✗{RESET} {name}")
    except Exception as e:
        failed += 1
        errors.append(f"{name}: {e}")
        print(f"  {RED}✗{RESET} {name}: {e}")


print(f"\n{BOLD}{'='*70}{RESET}")
print(f"{BOLD}  BUDGET PROTECTION TEST{RESET}")
print(f"{BOLD}{'='*70}{RESET}")


# ============================================================================
# SECTION 1: Budget Manager Unit Tests
# ============================================================================
print(f"\n{CYAN}[1/6] Budget Manager Unit Tests{RESET}")

def test_budget_creation():
    """Test creating budgets."""
    from core.budget_protection import BudgetManager, BudgetType
    
    project = f"budget-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    mgr = BudgetManager(products_dir="products", project=project)
    
    budget = mgr.create_budget("test1", BudgetType.KNOWLEDGE_LOAD, max_tokens=1000)
    return budget is not None and budget.max_tokens == 1000

def test_budget_reservation():
    """Test token reservation."""
    from core.budget_protection import BudgetManager, BudgetType
    
    project = f"budget-reserve-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    mgr = BudgetManager(products_dir="products", project=project)
    
    budget = mgr.create_budget("test", BudgetType.KNOWLEDGE_LOAD, max_tokens=1000)
    assert budget.reserve(500) == True
    assert budget.reserved_tokens == 500
    assert budget.remaining == 500
    return True

def test_budget_overage_denied():
    """Test that over-budget requests are denied."""
    from core.budget_protection import BudgetManager, BudgetType
    
    project = f"budget-deny-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    mgr = BudgetManager(products_dir="products", project=project)
    
    budget = mgr.create_budget("test", BudgetType.KNOWLEDGE_LOAD, max_tokens=1000)
    assert budget.reserve(800) == True
    # Now try to reserve 500 more (would exceed)
    assert budget.reserve(500) == False
    return True

def test_budget_commit():
    """Test committing reserved tokens."""
    from core.budget_protection import BudgetManager, BudgetType
    
    project = f"budget-commit-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    mgr = BudgetManager(products_dir="products", project=project)
    
    budget = mgr.create_budget("test", BudgetType.KNOWLEDGE_LOAD, max_tokens=1000)
    budget.reserve(500)
    assert budget.commit(500) == True
    assert budget.used_tokens == 500
    assert budget.reserved_tokens == 0
    return True

def test_budget_status():
    """Test budget status calculation."""
    from core.budget_protection import BudgetManager, BudgetType, BudgetStatus
    
    project = f"budget-status-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    mgr = BudgetManager(products_dir="products", project=project)
    
    budget = mgr.create_budget("test", BudgetType.KNOWLEDGE_LOAD, max_tokens=1000)
    budget.reserve(500)
    budget.commit(500)  # 50% used
    
    assert budget.status == BudgetStatus.HEALTHY, f"Expected healthy, got {budget.status.value}"
    
    # Reserve and commit more to reach 80%
    budget.reserve(300)
    budget.commit(300)  # Now 80% used
    
    assert budget.status == BudgetStatus.WARNING, f"Expected warning, got {budget.status.value}"
    
    return True

test("Budget creation", test_budget_creation)
test("Token reservation", test_budget_reservation)
test("Over-budget request denied", test_budget_overage_denied)
test("Token commit", test_budget_commit)
test("Budget status calculation", test_budget_status)


# ============================================================================
# SECTION 2: Knowledge Router Budget Enforcement
# ============================================================================
print(f"\n{CYAN}[2/6] Knowledge Router Budget Enforcement{RESET}")

def test_knowledge_router_respects_budget():
    """Test that knowledge router respects max_tokens budget."""
    from core.knowledge_router import KnowledgeRouter
    
    router = KnowledgeRouter()
    
    # With very small budget, should select fewer resources
    result_small = router.route(
        task="Build a SaaS web application with React and PostgreSQL",
        agent="design",
        max_tokens=500  # Very small budget
    )
    
    result_large = router.route(
        task="Build a SaaS web application with React and PostgreSQL",
        agent="design",
        max_tokens=5000  # Larger budget
    )
    
    # Small budget should select fewer or equal resources
    return len(result_small.selected_resources) <= len(result_large.selected_resources)

def test_safe_knowledge_route():
    """Test safe_knowledge_route wrapper."""
    from core.knowledge_router import KnowledgeRouter
    from core.budget_protection import BudgetManager, BudgetType, safe_knowledge_route
    
    project = f"safe-route-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    router = KnowledgeRouter()
    mgr = BudgetManager(products_dir="products", project=project)
    
    result = safe_knowledge_route(
        router,
        task="Build a marketplace application",
        budget_manager=mgr,
        budget_id="test_knowledge",
        max_tokens=2000,
        agent="design"
    )
    
    return result.total_tokens <= 2000

def test_safe_route_budget_exhaustion():
    """Test that safe_route returns empty when budget is exhausted."""
    from core.knowledge_router import KnowledgeRouter
    from core.budget_protection import BudgetManager, BudgetType, safe_knowledge_route
    
    project = f"budget-exhaust-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    router = KnowledgeRouter()
    mgr = BudgetManager(products_dir="products", project=project)
    
    # Use up the budget first
    mgr.create_budget("test", BudgetType.KNOWLEDGE_LOAD, max_tokens=100)
    mgr.request_tokens("test", 100)  # Use all tokens
    
    # Now try to route - should return empty due to budget
    result = safe_knowledge_route(
        router,
        task="Build a SaaS app",
        budget_manager=mgr,
        budget_id="test",  # Same budget, now exhausted
        max_tokens=5000,
        agent="design"
    )
    
    # Should be empty or very small
    return len(result.selected_resources) == 0

test("Router respects max_tokens budget", test_knowledge_router_respects_budget)
test("safe_knowledge_route wrapper works", test_safe_knowledge_route)
test("safe_route returns empty when budget exhausted", test_safe_route_budget_exhaustion)


# ============================================================================
# SECTION 3: Pipeline Budget Protection
# ============================================================================
print(f"\n{CYAN}[3/6] Pipeline Budget Protection{RESET}")

def test_pipeline_has_budgets():
    """Test that pipeline executor creates budgets."""
    from core.pipeline_executor import PipelineExecutor
    
    project = f"pipeline-budget-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    executor = PipelineExecutor(products_dir="products", project=project)
    
    # Should have created pipeline_total and knowledge_default budgets
    pipeline_budget = executor.budget_manager.get_budget("pipeline_total")
    knowledge_budget = executor.budget_manager.get_budget("knowledge_default")
    
    return pipeline_budget is not None and knowledge_budget is not None

def test_pipeline_knowledge_uses_budget():
    """Test that pipeline knowledge routing uses budget."""
    from core.pipeline_executor import PipelineExecutor
    
    project = f"pipeline-knowledge-budget-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    executor = PipelineExecutor(products_dir="products", project=project)
    executor.load_pipeline("test-pipeline-definition.json")
    executor.execute_pipeline()
    
    # Check that knowledge budgets were used
    statuses = executor.budget_manager.get_all_statuses()
    knowledge_budgets = [s for s in statuses if s["budget_type"] == "knowledge_load"]
    
    # At least the default knowledge budget should be tracked
    return len(knowledge_budgets) > 0

def test_pipeline_stage_budgets_created():
    """Test that pipeline creates budgets for each stage."""
    from core.pipeline_executor import PipelineExecutor
    
    project = f"pipeline-stage-budgets-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    executor = PipelineExecutor(products_dir="products", project=project)
    executor.load_pipeline("test-pipeline-definition.json")
    executor.execute_pipeline()
    
    # Check that stage budgets were created
    statuses = executor.budget_manager.get_all_statuses()
    stage_budgets = [s for s in statuses if s["budget_type"] == "stage_total"]
    
    return len(stage_budgets) >= 4  # Should have one per stage (ideation, design, architecture, etc.)

test("Pipeline creates budgets on init", test_pipeline_has_budgets)
test("Pipeline knowledge routing uses budget", test_pipeline_knowledge_uses_budget)
test("Pipeline creates stage budgets", test_pipeline_stage_budgets_created)


# ============================================================================
# SECTION 4: Budget Doesn't Overload System
# ============================================================================
print(f"\n{CYAN}[4/6] Budget Doesn't Overload System{RESET}")

def test_total_tokens_capped():
    """Test that total tokens are capped by budget."""
    from core.pipeline_executor import PipelineExecutor
    
    project = f"budget-cap-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    executor = PipelineExecutor(products_dir="products", project=project)
    executor.load_pipeline("test-pipeline-definition.json")
    executor.execute_pipeline()
    
    # Total used should be within total max
    total = executor.budget_manager.get_total_usage()
    return total["total_used"] <= total["total_max"]

def test_knowledge_load_capped():
    """Test that individual knowledge loads are capped."""
    from core.knowledge_router import KnowledgeRouter
    
    router = KnowledgeRouter()
    
    # Even with huge task description, result should be capped
    huge_task = "SaaS marketplace fintech healthtech edtech " * 50  # Very long task
    result = router.route(task=huge_task, max_tokens=1000)
    
    return result.total_tokens <= 1000

def test_no_resource_explosion():
    """Test that we don't select too many resources."""
    from core.knowledge_router import KnowledgeRouter
    
    router = KnowledgeRouter()
    
    # Route with normal task and budget
    result = router.route(
        task="Build a web application",
        max_tokens=3000
    )
    
    # Should select at most 5-6 resources with 3K token budget
    # (each resource is ~200-500 tokens)
    return len(result.selected_resources) <= 10

test("Total tokens capped by budget", test_total_tokens_capped)
test("Knowledge load capped per request", test_knowledge_load_capped)
test("No resource explosion in routing", test_no_resource_explosion)


# ============================================================================
# SECTION 5: Budget Alerts
# ============================================================================
print(f"\n{CYAN}[5/6] Budget Alerts{RESET}")

def test_budget_alerts_created():
    """Test that alerts are created when budget is near limit."""
    from core.budget_protection import BudgetManager, BudgetType
    
    project = f"alerts-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    mgr = BudgetManager(products_dir="products", project=project)
    
    budget = mgr.create_budget("test", BudgetType.KNOWLEDGE_LOAD, max_tokens=100)
    budget.reserve(95)  # Reserve 95% 
    mgr.commit_tokens("test", 95)  # Commit - should trigger critical alert
    
    alerts = mgr.get_alerts()
    return len(alerts) > 0

def test_budget_denial_creates_alert():
    """Test that denied requests create alerts."""
    from core.budget_protection import BudgetManager, BudgetType
    
    project = f"denial-alert-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    mgr = BudgetManager(products_dir="products", project=project)
    
    budget = mgr.create_budget("test", BudgetType.KNOWLEDGE_LOAD, max_tokens=100)
    budget.reserve(100)  # Use all
    mgr.request_tokens("test", 50)  # Should be denied
    
    alerts = mgr.get_alerts()
    return len(alerts) > 0

test("Alerts created at critical threshold", test_budget_alerts_created)
test("Alerts created on denied requests", test_budget_denial_creates_alert)


# ============================================================================
# SECTION 6: Final Report Includes Budget
# ============================================================================
print(f"\n{CYAN}[6/6] Final Report Includes Budget{RESET}")

def test_final_report_has_budget():
    """Test that final pipeline report includes budget info."""
    from core.pipeline_executor import PipelineExecutor
    
    project = f"report-budget-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    executor = PipelineExecutor(products_dir="products", project=project)
    executor.load_pipeline("test-pipeline-definition.json")
    executor.execute_pipeline()
    
    # Read final report
    report_file = Path(f"products/{project}/pipeline-execution-report.json")
    if not report_file.exists():
        return False
    
    with open(report_file, 'r') as f:
        report = json.load(f)
    
    return (
        "budget_summary" in report and
        "budget_statuses" in report
    )

test("Final report includes budget summary", test_final_report_has_budget)


# ============================================================================
# SUMMARY
# ============================================================================
print(f"\n{BOLD}{'='*70}{RESET}")
print(f"{BOLD}  BUDGET PROTECTION TEST RESULTS{RESET}")
print(f"{BOLD}{'='*70}{RESET}")
print(f"  {GREEN}Passed: {passed}{RESET}")
print(f"  {RED}Failed: {failed}{RESET}")
print(f"  Total:  {passed + failed}")
print(f"  Rate:   {passed/(passed+failed)*100:.1f}%")

if errors:
    print(f"\n{RED}  Failed tests:{RESET}")
    for err in errors:
        print(f"    - {err}")

print(f"\n{'='*70}")

if failed == 0:
    print(f"{GREEN}{BOLD}  ✅ ALL BUDGET TESTS PASSED - System protected from token exhaustion!{RESET}")
    print(f"\n  {CYAN}Verified:{RESET}")
    print(f"    ✓ Budget creation and tracking")
    print(f"    ✓ Token reservation and commit")
    print(f"    ✓ Over-budget requests denied")
    print(f"    ✓ Knowledge router respects max_tokens")
    print(f"    ✓ safe_knowledge_route protects budget")
    print(f"    ✓ Pipeline creates per-stage budgets")
    print(f"    ✓ Total tokens capped at budget limit")
    print(f"    ✓ No resource explosion")
    print(f"    ✓ Alerts created on critical/exceeded budgets")
    print(f"    ✓ Final report includes budget summary")
else:
    print(f"{RED}{BOLD}  ❌ SOME TESTS FAILED - Review needed{RESET}")

print(f"{'='*70}\n")

sys.exit(0 if failed == 0 else 1)
