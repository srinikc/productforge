"""PIDL-1 gate (BI-PF-0376): the context resolver is relevant-subset, deterministic, read-only, decoupled.

Asserts: the resolver returns the contract keys; it is deterministic (two calls equal); it selects
area-relevant review lenses; a consequential action flips ``approval_required``; it degrades gracefully
(never raises) with no sources; and ``core/pidl.py`` does not import the worker layer (orchestration owns
PIDL - workers never do).
Run: ``python scripts/dev/pidl_check.py``.
"""
import os
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

FAILS = []
_KEYS = {"scope", "project", "profile_version", "applicable_rules", "applicable_principles",
         "applicable_preferences", "prior_decisions", "review_lenses", "execution_policy",
         "consequential", "evidence", "context_size"}


def _check(cond, msg):
    if not cond:
        FAILS.append(msg)


def main() -> int:
    from core import pidl

    _check(bool(pidl.load_profile()), "pidl profile loads")
    _check(pidl.load_profile().get("version"), "profile has a version")

    ctx = pidl.resolve_context("product_forge", None, action="add endpoint", area="api",
                               components=["api"])
    _check(set(ctx) >= _KEYS, f"context keys present (missing {_KEYS - set(ctx)})")
    _check(isinstance(ctx["execution_policy"], dict), "execution_policy is structured")
    _check(int(ctx["profile_version"]) >= 1, "profile_version resolved")

    # deterministic
    ctx2 = pidl.resolve_context("product_forge", None, action="add endpoint", area="api", components=["api"])
    _check(ctx == ctx2, "resolver is deterministic")

    # relevant subset: security area selects the security lens
    sec = pidl.resolve_context("product_forge", None, area="security", components=["security"])
    _check("security" in sec["review_lenses"], "security area -> security lens")

    # consequential action requires approval
    cons = pidl.resolve_context("product_forge", None, action="drop production database schema")
    _check(cons["consequential"] is True, "consequential action detected")
    _check(cons["execution_policy"]["approval_required"] is True, "consequential -> approval_required")
    benign = pidl.resolve_context("product_forge", None, action="add a doc paragraph", area="doc")
    _check(benign["execution_policy"]["approval_required"] is False, "benign action -> no approval")

    # graceful degradation (unknown scope/project, empty sources)
    empty = pidl.resolve_context("project", "_pidl_check_scratch")
    _check(set(empty) >= _KEYS, "degrades to empty context without raising")
    _check(isinstance(pidl.render_context(empty), str), "render_context returns text")

    # PIDL-2: decision engine - structured contract + deterministic precedence
    d_auto = pidl.decide("product_forge", None, action="add a doc paragraph", area="doc")
    _check(set(d_auto) >= {"decision", "confidence", "risk", "recommendation", "evidence",
                           "conflicts", "approval", "next_action"}, "decision contract keys present")
    _check(d_auto["decision"]["action"] == "AUTO_PROCEED", "benign -> AUTO_PROCEED")
    _check(d_auto["decision"]["action"] in pidl.ACTIONS, "action in the closed set")
    _check(pidl.decide("product_forge", None, action="add a doc paragraph", area="doc") == d_auto,
           "decision is deterministic")
    _check(pidl.decide("product_forge", None, action="drop production schema")["decision"]["action"]
           == "APPROVAL_REQUIRED", "consequential -> APPROVAL_REQUIRED")
    _check(pidl.decide("product_forge", None, action="x", conflicts=[{"a": 1}])["decision"]["action"]
           == "CORRECT", "conflicts -> CORRECT")
    _check(pidl.decide("product_forge", None, action="x", result={"ok": False, "status": "failed"}
                       )["decision"]["action"] == "REVIEW", "failed result -> REVIEW")
    _check(pidl.decide("product_forge", None, action="x", failures=5)["decision"]["action"]
           == "ESCALATE", "repeated failures -> ESCALATE")
    _check(0.0 <= d_auto["confidence"]["overall"] <= 1.0, "overall confidence bounded")

    # decoupling: PIDL must not import the worker layer
    with open(os.path.join(str(_ROOT), "core", "pidl.py"), encoding="utf-8") as f:
        src = f.read()
    for bad in ("core.worker", "worker_registry", "worker_adapters", "work_pull", "dispatcher"):
        _check(bad not in src, f"pidl.py must not import worker layer ({bad})")

    if FAILS:
        print("pidl: FAIL")
        for f in FAILS:
            print("   -", f)
        return 1
    print("pidl: OK (context resolver: subset, deterministic, read-only, decoupled)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
