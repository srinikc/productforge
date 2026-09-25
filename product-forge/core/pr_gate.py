"""
PR merge gate.

Every merge to `develop` (and `develop -> main`) requires a PR that satisfies a
checklist BEFORE merge:
  - code_review            : reviewer (`code-review`) approved
  - review_changes_done    : requested review changes are resolved
  - db_tests               : DB-layer unit tests exist and pass
  - api_tests              : API-layer unit tests exist and pass
  - unit_tests             : unit suite passes
  - lint                   : lint/static checks clean
  - ui_e2e                 : minimal UI/E2E for the change passes (when product has UI)

Signals are taken from what the pipeline already stores (cycles, spec review,
defects, audit trail). Items that cannot be proven are `unknown` and DO NOT pass.

Override is **HIL-only** (`qa.override_merge`), recorded + audited.
"""
try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

_REPO = str(_PF_ROOT)
_TF = os.path.join(_REPO, "test-framework")

CHECKLIST = ["code_review", "review_changes_done", "db_tests", "api_tests",
             "unit_tests", "lint", "ui_e2e", "app_boot", "structure_contract"]
UI_KINDS = {"web", "desktop", "mobile"}


def _rj(p):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _categories_for_kind(project_dir: str, kind: str):
    try:
        from core.test_matrix import load, categories_for_kind
        return categories_for_kind(kind, load())
    except Exception:
        return []


def _cat_path(project_dir: str, category: str):
    rel = f"tests/{category}"
    try:
        from core.test_matrix import load
        rel = ((load().get("categories") or {}).get(category, {}) or {}).get("path") or rel
    except Exception:
        pass
    return os.path.join(project_dir, rel), rel


def _tests_exercise_app(project_dir: str, category: str, entrypoint: str) -> bool:
    """Do the category's tests actually import the app / drive an HTTP client?"""
    import re as _re
    roots = [os.path.join(project_dir, "tests", category), os.path.join(project_dir, "tests")]
    last = (entrypoint or "").split(".")[-1]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dp, _dn, fs in os.walk(root):
            for f in fs:
                if not f.endswith((".py", ".ts", ".js", ".tsx", ".jsx")):
                    continue
                try:
                    t = open(os.path.join(dp, f), encoding="utf-8", errors="ignore").read()
                except Exception:
                    continue
                if last and last in t:
                    return True
                if _re.search(r"TestClient|AsyncClient|supertest|httpx\.|requests\.|"
                              r"request\(app|page\.goto|playwright|\.get\(['\"]/|\.post\(", t):
                    return True
    return False


def _has_tests(d: str) -> bool:
    if not os.path.isdir(d):
        return False
    for _dp, _dn, fs in os.walk(d):
        for f in fs:
            if f.startswith("test") and f.endswith((".py", ".ts", ".js", ".tsx", ".jsx")):
                return True
            if f.endswith((".test.ts", ".test.js", ".spec.ts", ".spec.js")):
                return True
    return False


def _product_kind(project_dir: str) -> str:
    ts = _rj(os.path.join(project_dir, "docs", "tech-stack.json")) or {}
    try:
        from core.test_matrix import product_kind
        return product_kind(ts)
    except Exception:
        return "default"


def _last_cycle(project: str) -> Dict:
    d = os.path.join(_TF, "results", "test-cycles")
    best = None
    if os.path.isdir(d):
        for n in os.listdir(d):
            if n.startswith(project + "_") and n.endswith(".json"):
                c = _rj(os.path.join(d, n))
                if c and (best is None or c.get("started_at", "") > best.get("started_at", "")):
                    best = c
    return best or {}


def _audit_has(project: str, agent: str) -> bool:
    p = os.path.join(_REPO, "products", project, "audit-trail.json")
    data = _rj(p)
    if not isinstance(data, list):
        return False
    return any(str(e.get("agent")) == agent and str(e.get("action")) == "agent_complete" for e in data)


def evaluate(project: str, project_dir: str) -> Dict[str, Any]:
    """Return per-item status: pass | fail | unknown | skip (+ detail)."""
    kind = _product_kind(project_dir)
    cycle = _last_cycle(project)
    runs = cycle.get("test_runs", []) or []
    frameworks = " ".join(str(r.get("framework", "")) for r in runs).lower()
    any_failed = any(str(r.get("status")) == "failed" for r in runs)
    cyc_passed = str(cycle.get("status")) == "passed"

    spec = _rj(os.path.join(_TF, "results", project, "spec-review.json")) or {}
    blocking = (spec.get("summary") or {}).get("blocking_open", 0)

    items: Dict[str, Dict[str, str]] = {}

    # code_review: reviewer agent completed
    items["code_review"] = ({"status": "pass", "detail": "code-review completed"}
                            if _audit_has(project, "code-review")
                            else {"status": "unknown", "detail": "no code-review record"})

    # review_changes_done: no blocking review findings
    items["review_changes_done"] = ({"status": "pass", "detail": "no blocking findings"}
                                    if blocking == 0 and spec
                                    else {"status": "unknown", "detail": "no spec-review record"})

    # db_tests / api_tests: layer unit tests exist AND the latest cycle passed
    kind_cats = _categories_for_kind(project_dir, kind)
    for cat, key in (("db", "db_tests"), ("api", "api_tests")):
        if cat not in kind_cats:
            items[key] = {"status": "skip", "detail": f"no {cat} layer for kind={kind}"}
            continue
        try:
            from core.test_matrix import has_category_tests
            has = has_category_tests(project_dir, cat)
        except Exception:
            d, _rel = _cat_path(project_dir, cat)
            has = _has_tests(d)
        d, rel = _cat_path(project_dir, cat)
        if has and cyc_passed:
            items[key] = {"status": "pass", "detail": f"{cat} tests passed"}
        elif has and cycle and not cyc_passed:
            items[key] = {"status": "fail", "detail": f"{cat} tests failed"}
        else:
            items[key] = {"status": "unknown", "detail": f"no {cat} tests or cycle"}

    # app_boot: the app entrypoint must import/start (catches import-time errors)
    try:
        from core.app_smoke import detect_entrypoint, boot_check
        ep = detect_entrypoint(project_dir)
    except Exception:
        ep = None
    if not ep:
        items["app_boot"] = {"status": "skip", "detail": "no app entrypoint"}
    else:
        b = boot_check(project_dir)
        if b.get("ok") is False:
            items["app_boot"] = {"status": "fail", "detail": str(b.get("error", ""))[:160]}
        elif b.get("ok") and cyc_passed:
            items["app_boot"] = {"status": "pass", "detail": f"{ep} imports; cycle passed"}
        else:
            items["app_boot"] = {"status": "unknown", "detail": f"{ep} imports; no passing cycle"}

    # Dependency: if the app does not boot, dependent categories can't be "passed".
    if items.get("app_boot", {}).get("status") == "fail":
        for _k in ("api_tests", "ui_e2e", "db_tests", "unit_tests", "lint"):
            if items.get(_k, {}).get("status") == "pass":
                items[_k] = {"status": "fail",
                             "detail": "app does not boot -> dependent tests are not valid"}

    # unit_tests: latest cycle passed
    items["unit_tests"] = ({"status": "pass", "detail": cycle.get("cycle_id", "")}
                           if cyc_passed else
                           ({"status": "fail", "detail": "latest cycle failed"} if cycle else
                            {"status": "unknown", "detail": "no cycle run"}))

    # lint: latest cycle had no failures + a build exists
    build = _rj(os.path.join(project_dir, "build-info.json")) or {}
    items["lint"] = ({"status": "pass", "detail": "no failures in latest cycle"}
                     if cyc_passed and not any_failed and build.get("build_id") else
                     ({"status": "fail", "detail": "failures present"} if any_failed else
                      {"status": "unknown", "detail": "no lint/build signal"}))

    # ui_e2e: UI products need an e2e/bdd run that passed
    if kind in UI_KINDS:
        ui_ok = ("playwright" in frameworks or "bdd" in frameworks) and not any_failed
        items["ui_e2e"] = ({"status": "pass", "detail": "ui e2e/bdd passed"}
                           if ui_ok and cyc_passed else
                           {"status": "unknown", "detail": "no ui e2e run"})
    else:
        items["ui_e2e"] = {"status": "skip", "detail": f"no UI for kind={kind}"}

    # structure_contract: Product Forge structure rules hold (naming + store registry)
    try:
        import subprocess
        reg = os.path.join(_REPO, "config", "store-registry.json")
        audit = os.path.join(_REPO, "scripts", "dev", "wired_audit.py")
        if os.path.exists(reg) and os.path.exists(audit):
            r = subprocess.run(["python", audit], cwd=_REPO, capture_output=True,
                               text=True, timeout=180)
            items["structure_contract"] = (
                {"status": "pass", "detail": "naming + store registry clean"}
                if r.returncode == 0 else
                {"status": "fail", "detail": "wired_audit violations (see output)"})
        else:
            items["structure_contract"] = {"status": "unknown",
                                           "detail": "store-registry/wired_audit missing"}
    except Exception as e:
        items["structure_contract"] = {"status": "unknown", "detail": f"audit error: {e}"}

    return {"project": project, "product_kind": kind, "items": items,
            "generated_at": datetime.now().isoformat()}


def required(project_dir: str, product_kind: str = "") -> List[str]:
    kind = product_kind or _product_kind(project_dir)
    cats = _categories_for_kind(project_dir, kind)
    out = []
    for c in CHECKLIST:
        if c == "ui_e2e" and kind not in UI_KINDS:
            continue
        if c == "db_tests" and "db" not in cats:
            continue
        if c == "api_tests" and "api" not in cats:
            continue
        if c == "app_boot":
            try:
                from core.app_smoke import detect_entrypoint
                if not detect_entrypoint(project_dir):
                    continue
            except Exception:
                continue
        out.append(c)
    return out


def can_merge(project: str, project_dir: str) -> Dict[str, Any]:
    """Merge allowed iff every required item passes, or a HIL override is recorded."""
    ev = evaluate(project, project_dir)
    req = required(project_dir, ev["product_kind"])
    unmet = [c for c in req if ev["items"].get(c, {}).get("status") != "pass"]
    override = _override(project_dir)
    ok = (not unmet) or bool(override.get("approved"))
    return {"can_merge": ok, "unmet": unmet, "override": override, "evaluation": ev,
            "reason": ("all checklist items passed" if not unmet
                       else ("HIL override: " + str(override.get("reason", "")) if override.get("approved")
                             else "merge blocked: " + ", ".join(unmet)))}


def _override(project_dir: str) -> Dict:
    cfg = _rj(os.path.join(project_dir, "project.json")) or {}
    return (cfg.get("qa") or {}).get("override_merge") or {}


def request_override(project_dir: str, project: str, reason: str, requested_by: str = "orchestrator") -> Dict:
    """Record a HIL override REQUEST (does not auto-approve; HIL must approve)."""
    try:
        project = project or os.path.basename(os.path.normpath(project_dir))
        from core.project_store import update_section
        update_section(project, "qa", {"override_merge": {
            "requested": True, "reason": reason, "requested_by": requested_by,
            "approved": False,  # approval is HIL
            "at": datetime.now().isoformat()}}, products_dir=os.path.dirname(project_dir) or "products")
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "pending_hil": True}


def approve_override(project_dir: str, approved_by: str = "HIL") -> Dict:
    """HIL approves the override (this is the only path that sets approved=True)."""
    try:
        project = os.path.basename(os.path.normpath(project_dir))
        from core.project_store import read_section, update_section
        products_dir = os.path.dirname(project_dir) or "products"
        ov = read_section(project, "qa", products_dir=products_dir).get("override_merge", {}) or {}
        ov.update({"approved": True, "approved_by": approved_by,
                   "approved_at": datetime.now().isoformat()})
        update_section(project, "qa", {"override_merge": ov}, products_dir=products_dir)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "approved": True}
