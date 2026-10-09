"""DOGFOOD Phase 1 (BI-PF-0458): API-first auto dogfood for GENERATED products.

Composes existing owners only (no new engine/store):

  * ``core.project_store``      - seed idea + ``auto_mode``/``auto_approve`` + tier + caps
  * ``core.run_entry``          - enqueue the run (the ONE submission path; no direct executor call)
  * ``core.run_guard`` / ``core.log_router`` - run + stage/agent observability
  * ``core.validation_engine`` / ``core.issues`` - validation results + defects
  * ``core.vcs`` / ``core.close_loop`` - delivery assertions

A dogfood is a product-generation run (scope ``project``); it does NOT use the worker plane.
"""
import contextlib
import os
from typing import Any, Optional

from core.paths import PRODUCTS_DIR


def _products_dir(products_dir: Optional[str] = None) -> str:
    return str(products_dir or PRODUCTS_DIR)


def _valid_project(project: str) -> str:
    p = str(project or "").strip()
    if not p or "/" in p or "\\" in p or p in (".", ".."):
        raise ValueError("invalid project name")
    return p


def _tail(path: str, n: int = 60) -> list:
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return [ln.rstrip("\n") for ln in f.readlines()[-n:]]
    except Exception:
        return []


def start(idea: str, project: str, *, tier: str = "kctier", auto: bool = True,
          caps: Optional[dict] = None, target: str = "", products_dir: Optional[str] = None) -> dict:
    """Seed a dogfood project (idea + auto + tier + caps) and enqueue the run. Returns the run id."""
    from core import project_store, run_entry
    p = _valid_project(project)
    pd = _products_dir(products_dir)
    project_store.ensure(p, pd)
    project_store.update(p, pd, name=p, idea=str(idea or ""), model_tier=str(tier or "kctier"),
                         auto_mode=bool(auto), auto_approve=bool(auto),
                         mode=("auto" if auto else "manual"))
    if caps or target:
        with contextlib.suppress(Exception):
            project_store.update_section(p, "dogfood",
                                         {"caps": dict(caps or {}), "target": str(target or "")}, pd)
    entry = run_entry.enqueue(p, pd, tier=str(tier or ""), source="dogfood", actor="dogfood")
    rid = str((entry or {}).get("run_id") or "")
    return {"project": p, "run_id": rid, "tier": str(tier or "kctier"), "auto": bool(auto),
            "caps": dict(caps or {}), "target": str(target or ""), "enqueued": entry}


def status(project: str, run_id: str = "", *, products_dir: Optional[str] = None) -> dict:
    """Aggregate run + stages/agents (events) + log tail + defects + validation + delivery."""
    from core import issues, log_router, run_guard, validation_engine
    p = _valid_project(project)
    pd = _products_dir(products_dir)
    project_dir = os.path.join(pd, p)
    out: dict[str, Any] = {"project": p, "run_id": run_id, "exists": os.path.isdir(project_dir)}
    try:
        out["active_run"] = run_guard.active_run(p, pd)
    except Exception as e:  # noqa: BLE001
        out["active_run"] = {"error": type(e).__name__}
    try:
        out["events"] = _tail(log_router.run_events_path(project_dir), 60)
    except Exception:
        out["events"] = []
    out["log_tail"] = _tail(os.path.join(project_dir, "pipeline-run.log"), 60)
    try:
        out["defects"] = [i.get("id") for i in issues.list_open("project", p)]
    except Exception:
        out["defects"] = []
    try:
        out["validation"] = [{"run_id": r.get("run_id"), "profile": r.get("profile"), "result": r.get("result")}
                             for r in validation_engine.list_runs("project", p)]
    except Exception:
        out["validation"] = []
    out["delivery"] = assert_delivery(project_dir)
    return out


def assert_delivery(project_dir: str) -> dict:
    """Fail-closed delivery assertions: repo + commits + (a passing validation OR a verified close-loop)."""
    from core.vcs import VCSManager
    checks: dict[str, Any] = {}
    reasons: list[str] = []
    v = VCSManager(project_dir)
    checks["is_repo"] = v.is_repo()
    if not checks["is_repo"]:
        return {"delivered": False, "checks": checks, "reasons": ["not a git repository"]}
    commits = v.checkins(50)
    checks["commits"] = len(commits)
    if not commits:
        reasons.append("no commits")
    try:
        from core import validation_engine
        runs = validation_engine.list_runs("project", os.path.basename(os.path.normpath(project_dir)))
        checks["validation_pass"] = any(str(r.get("result")) == "PASS" for r in runs)
    except Exception:
        checks["validation_pass"] = False
    try:
        from core import close_loop
        checks["close_loop"] = bool(close_loop.verify_run(project_dir).get("verified"))
    except Exception:
        checks["close_loop"] = False
    delivered = bool(checks.get("commits")) and bool(checks.get("validation_pass") or checks.get("close_loop"))
    if not delivered:
        reasons.append("no passing validation and no verified close-loop")
    return {"delivered": delivered, "checks": checks, "reasons": reasons}


def trends(project: str, *, limit: int = 20, products_dir: Optional[str] = None) -> dict:
    """Read-only trend + regression view over recorded DOGFOOD validation runs (no new store)."""
    from core import validation_engine
    p = _valid_project(project)
    runs = [r for r in validation_engine.list_runs("project", p, profile="DOGFOOD") if r.get("result")]
    series = [{"run_id": r.get("run_id"), "result": r.get("result"),
               "at": r.get("finished_at") or r.get("started_at")} for r in runs[-limit:]]
    counts: dict[str, int] = {}
    for r in runs:
        k = str(r.get("result"))
        counts[k] = counts.get(k, 0) + 1
    regression = bool(series) and str(series[-1].get("result")) != "PASS" \
        and any(str(s.get("result")) == "PASS" for s in series[:-1])
    return {"project": p, "series": series, "counts": counts, "regression": regression, "total": len(runs)}
