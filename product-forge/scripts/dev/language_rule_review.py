"""BI-PF-1262: plan-time language-rule assessment for a backlog item.

Runs the SAME policy that precheck uses (``core/change_policy``) over an item's planned ``affected_files``,
so the language decision - new logic in **Go** vs **edits** to existing shipped Python vs **new shipped
Python needing an allowlist** - is made at **Gate 1 / backlog review, before implementation**, and cited in
the reconciliation/impact review. This avoids the late "language-rule" re-ask during implementation.

Planning aid only; the ENFORCING gate remains ``scripts/dev/language_rule_check.py`` (precheck fast band +
delivery validation). Files that do not yet exist are treated as planned NEW files (added); existing files
are planned EDITS (changed) - edits to shipped Python are allowed.

Usage:
  python scripts/dev/language_rule_review.py BI-PF-1264
  python scripts/dev/language_rule_review.py BI-PF-1264 --json
"""
import argparse
import json
import os
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _exists(rel: str) -> bool:
    from core import change_policy
    n = change_policy.normalize(rel)
    return os.path.isfile(os.path.join(_ROOT, *n.split("/"))) if n else False


def assess(item_id: str, scope: str = "product_forge", project: str = "") -> dict:
    from core import backlog, change_policy
    it = backlog.get_epic(scope, project or None, item_id) or {}
    files = it.get("affected_files") or []
    changed, added = [], []
    for f in files:
        (changed if _exists(f) else added).append(f)
    pol = change_policy.policy()
    shipped_py = [p for p in set(changed) if change_policy.normalize(p).endswith(".py")]
    sources = {}
    for p in shipped_py:
        n = change_policy.normalize(p)
        try:
            sources[n] = open(os.path.join(_ROOT, *n.split("/")), encoding="utf-8", errors="ignore").read()
        except Exception:
            sources[n] = ""  # unreadable -> fail-closed parse path
    findings = change_policy.check(changed, added, sources, pol)
    drift = change_policy.drift_report(added, findings, pol)
    return {"item": item_id, "changed": changed, "added": added, "drift": drift, "findings": findings}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Plan-time language-rule assessment (BI-PF-1262)")
    ap.add_argument("item")
    ap.add_argument("--scope", default="product_forge")
    ap.add_argument("--project", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    from core import backlog
    if not backlog.get_epic(a.scope, a.project or None, a.item):
        print(f"item {a.item} not found in this tree's backlog - run in the runtime tree that owns the item")
        return 2
    r = assess(a.item, a.scope, a.project)
    if a.json:
        print(json.dumps(r, ensure_ascii=False))
        return 1 if r["findings"] else 0
    print(f"language-rule assessment (plan-time) for {r['item']}: "
          f"{len(r['changed'])} planned edit(s) / {len(r['added'])} planned new file(s)")
    for f in r["findings"]:
        print(f"   - [{f['rule']}] {f['path']}: {f['detail']}")
    if r["findings"]:
        print("   => language-rule: FAIL - planned NEW shipped Python must be Go or allowlisted "
              "(edits to existing shipped Python are allowed)")
        return 1
    print("   => language-rule: OK (no new shipped Python; edits allowed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
