"""ENG-8: merge enforcement / integration queue.

A merge to the integration branch is allowed only when the change is provably green:
  * ``core.pr_gate.can_merge`` (product checklist), AND
  * a **PASS** validation run (FEATURE_PR or INTEGRATION) recorded in ``validation-runs.json``.

If either is not satisfied the merge is BLOCKED (fail-closed). This is the local counterpart of CI requiring the
full precheck + branch protection (see .github/workflows + ENG-8 item). No new store: reads canonical owners.
"""
from typing import Any

_PASS_PROFILES = ("FEATURE_PR", "INTEGRATION")


def evaluate(project: str, project_dir: str, scope: str = "project") -> dict[str, Any]:
    checks: dict[str, Any] = {}

    try:
        from core import pr_gate
        cm = pr_gate.can_merge(project, project_dir)
        checks["pr_gate"] = {"ok": bool(cm.get("can_merge")), "unmet": cm.get("unmet", []),
                             "reason": cm.get("reason", "")}
    except Exception as e:
        checks["pr_gate"] = {"ok": False, "reason": f"error: {type(e).__name__}"}

    try:
        from core import validation_engine
        rows = validation_engine.list_runs(scope, project if scope == "project" else None)
        passing = [r for r in rows if str(r.get("result")) == "PASS" and str(r.get("profile")) in _PASS_PROFILES]
        latest = passing[-1] if passing else None
        checks["validation"] = {"ok": bool(passing), "runs": len(rows), "passing": len(passing),
                                "run_id": (latest or {}).get("run_id", ""),
                                "profile": (latest or {}).get("profile", "")}
    except Exception as e:
        checks["validation"] = {"ok": False, "reason": f"error: {type(e).__name__}"}

    can_merge = all(c.get("ok") for c in checks.values())
    unmet = [k for k, c in checks.items() if not c.get("ok")]
    return {"project": project, "can_merge": can_merge, "checks": checks, "unmet": unmet,
            "reason": "all merge checks passed" if can_merge else "merge blocked: " + ", ".join(unmet)}


def queue(scope: str, project: str = "") -> list[dict[str, Any]]:
    """Integration queue: PR records with their current merge-gate decision."""
    from core import github
    p = project or None
    try:
        prs = github.list_prs(scope, p)
    except Exception:
        prs = []
    out: list[dict[str, Any]] = []
    for pr in prs:
        proj = str(pr.get("project") or p or "")
        pdir = pr.get("project_dir") or ""
        ev = evaluate(proj or "_", pdir, scope=scope) if pdir else {"can_merge": None}
        out.append({"pr": pr.get("number") or pr.get("url") or "", "branch": pr.get("branch", ""),
                    "base": pr.get("base", ""), "status": pr.get("status", ""),
                    "can_merge": ev.get("can_merge"), "unmet": ev.get("unmet", [])})
    return out
