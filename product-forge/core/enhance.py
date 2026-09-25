"""
Enhance mode.

Given an existing built project and a goal (e.g. "enterprise/production ready"),
analyze the code/design/architecture/tests, produce an ENHANCEMENT PLAN
(gaps, redesign suggestions, production concerns, risks, staged plan), ask the
user to accept/adjust (or auto in auto mode), then re-run the pipeline end-to-end
(from Stage 0) with the enhanced scope.

API/CLI: `run_pipeline.py enhance <project> --goal "..." [--no-run] [--auto]`
"""
import os
from typing import Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def plan(executor, goal: str):
    """Have the strategist agent produce docs/ENHANCEMENT-PLAN.md from existing artifacts."""
    task = (f"Analyze the CURRENT project's code, design, architecture, tests and docs, and produce an "
            f"ENHANCEMENT PLAN to make it: {goal}.\n\n"
            "Include: (1) gaps/weaknesses vs the goal, (2) proposed changes/redesign, "
            "(3) production/enterprise suggestions (security, scaling/HA, observability, multi-tenancy, "
            "compliance, CI/CD, SLOs), (4) risks/tradeoffs, (5) a staged plan with priorities. "
            "Write `docs/ENHANCEMENT-PLAN.md` (concise, actionable). Do NOT write product code.")
    try:
        return executor.execute_agent("strategist", "enhance", task)
    except Exception as e:
        print(f"[Enhance] plan error: {e}")
        return None


def apply_and_run(executor, auto: bool = False) -> int:
    """Invalidate all stages and run the pipeline end-to-end with the enhanced scope."""
    try:
        executor.invalidate_for_rerun(from_stage="0")
        print("[Enhance] scope invalidated; re-running from Stage 0 …")
    except Exception as e:
        print(f"[Enhance] invalidate: {e}")
    try:
        return 0 if executor.execute_pipeline() else 1
    except Exception as e:
        print(f"[Enhance] run error: {e}")
        return 1


def enhance(project: str, goal: str, accept: bool = True, products_dir: str = "products",
            auto: bool = False) -> int:
    from core.pipeline_executor import PipelineExecutor
    executor = PipelineExecutor(products_dir=products_dir, project=project)
    print(f"[Enhance] goal: {goal}")
    p = plan(executor, goal)
    try:
        plan_path = os.path.join(executor.project_dir, "docs", "ENHANCEMENT-PLAN.md")
        print(f"[Enhance] plan -> {plan_path} (exists={os.path.exists(plan_path)})")
        # Step 8: Product Forge scope keeps its own plan truth (single writer).
        if str(project) in ("product-forge", "product_forge"):
            from core import forge_store
            forge_store.add_goal(title=goal[:200], body=plan_path)
            forge_store.update_state(status="enhancing", goal=goal[:200])
    except Exception:
        pass
    if not accept:
        print("[Enhance] plan-only (--no-run); review the plan, then re-run with accept.")
        return 0
    if not auto:
        ans = ""
        try:
            import sys
            from core import interactive as _interactive
            if _interactive.enabled() or sys.stdin.isatty():
                ans = (_interactive.ask(
                    "[Enhance] Accept this plan and re-run E2E from Stage 0? [y/N] ", "n",
                    project_dir=executor.project_dir, kind="confirm") or "").strip().lower()
        except Exception:
            ans = ""
        if ans not in ("y", "yes"):
            print("[Enhance] not accepted; plan saved for review.")
            return 0
    return apply_and_run(executor, auto=auto)
