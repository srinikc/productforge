"""Tests API (API-3): test-matrix plan/gaps + recent test-cycle summaries.

Read-models over ``core.test_matrix`` (catalogue/plan) and the canonical test-cycle results written by
``test-framework`` (``test-framework/results/test-cycles/<project>_*.json``). No shadow store.
"""

import json
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate
from ..envelope import from_request
from . import _common

router = APIRouter(prefix="/tests", tags=["tests"])


def _tech_stack(project_dir: str) -> Optional[Dict[str, Any]]:
    p = os.path.join(project_dir, "docs", "tech-stack.json")
    try:
        with open(p, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def _read_cycles(project: str, limit: int) -> List[Dict[str, Any]]:
    from core import paths
    base = os.path.join(paths.ROOT, "test-framework", "results", "test-cycles")
    out: List[Dict[str, Any]] = []
    if os.path.isdir(base):
        prefix = project + "_"
        for n in sorted(os.listdir(base)):
            if not n.startswith(prefix) or not n.endswith("." + "json"):
                continue
            try:
                with open(os.path.join(base, n), encoding="utf-8-sig") as f:
                    j = json.load(f)
            except Exception:
                continue
            if not isinstance(j, dict):
                continue
            out.append({"cycle_id": j.get("cycle_id") or n[:-len("." + "json")],
                        "status": j.get("status"), "mode": j.get("mode"),
                        "started_at": j.get("started_at"), "total": j.get("total"),
                        "passed": j.get("passed"), "failed": j.get("failed"),
                        "skipped": j.get("skipped")})
    out.sort(key=lambda r: str(r.get("started_at") or ""))
    return out[-max(1, int(limit)):]


@router.get("/matrix", dependencies=[Depends(authenticate)])
def matrix(project: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import test_matrix
    d = _common.project_dir(project)
    ts = _tech_stack(d)
    kind = test_matrix.product_kind(ts)
    m = test_matrix.load()
    cats = test_matrix.categories_for_kind(kind, m)
    return from_request(request, {"product_kind": kind, "categories": cats,
                                  "plan": test_matrix.plan(d, cats, ts),
                                  "missing": test_matrix.missing_categories(d, cats, ts)},
                        resource="test", resource_id=project)


@router.get("/cycles", dependencies=[Depends(authenticate)])
def cycles(project: str, request: Request, limit: int = 20,
           ctx: Dict[str, Any] = Depends(authenticate)):
    _common.project_dir(project)
    return from_request(request, _read_cycles(project, limit),
                        resource="test", resource_id=project)
