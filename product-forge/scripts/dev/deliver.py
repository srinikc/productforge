#!/usr/bin/env python3
"""BI-PF-0421: run the optimistic delivery lane (drain the `verifying` queue).

Recovery / manual runner for the async delivery triggered on assignment complete. Processes items in status
``verifying`` one landing at a time (push+PR -> validate -> rebase -> merge -> push -> set_delivery).

Usage: ``python scripts/dev/deliver.py [--scope S] [--project P] [--limit N]``.
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


def main(argv=None) -> int:
    from core import delivery
    ap = argparse.ArgumentParser(description="Drain the delivery queue (BI-PF-0421)")
    ap.add_argument("--scope", default="product_forge")
    ap.add_argument("--project", default="")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    res = delivery.drain(a.scope, a.project or None, limit=a.limit)
    print(json.dumps(res, indent=2))
    return 0 if all(d.get("ok") for d in res.get("delivered", [])) else 1


if __name__ == "__main__":
    raise SystemExit(main())
