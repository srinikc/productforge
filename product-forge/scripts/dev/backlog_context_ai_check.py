"""BI-PF-0565 (advisory): AI (LLM) review of open backlog context.

Asks a model whether each open item is implementable (what/why/how/where) via ``core.context_review``.
Advisory by default (always exits 0); ``--strict`` exits 1 if any item is judged NOT implementable.
When the reviewer is unavailable it reports ``no-validator`` (never a false verdict).
Run: ``python scripts/dev/backlog_context_ai_check.py [--strict]``.
"""
import argparse
import os
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import backlog, context_review  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    items = backlog.list_open("product_forge", None)
    ok = thin = novalidator = 0
    thins = []
    for it in items:
        r = context_review.review(it)
        if r["ok"] is None:
            novalidator += 1
            tag = "?UNKNOWN"
        elif r["ok"]:
            ok += 1
            tag = "OK"
        else:
            thin += 1
            thins.append(it["id"])
            tag = "THIN"
        print(f"  {it['id']:<12} {tag:<9} missing={r.get('missing')} {str(r.get('reason') or '')[:70]}")
    print(f"ai-context: {ok} implementable, {thin} thin, {novalidator} no-validator (of {len(items)})")
    if a.strict and thins:
        print("ai-context: FAIL (--strict): thin items:", ", ".join(thins))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
