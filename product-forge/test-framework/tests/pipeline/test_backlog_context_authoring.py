"""BI-PF-0563: the backlog creator derives implementable context from the body (no placeholder stubs)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")

from core import backlog  # noqa: E402

_BODY = (
    "## Problem / why\nProvider coupling hurts; core imports concrete providers.\n\n"
    "## Goal & value\nIntroduce gateway ports so core depends on abstractions.\n\n"
    "## In scope\n- core/gateways.py ports\n- config-driven provider selection\n\n"
    "## Acceptance criteria\n- no core module imports a concrete provider\n"
)


def test_structured_body_yields_real_context():
    ctx = backlog._draft_context("B2 gateways", _BODY,
                                 links={"backend_capability": ["module:core/gateways.py"]})
    assert ctx["brief"]["source"] == "authored"
    assert "Provider coupling" in ctx["brief"]["problem"]
    assert "gateway ports" in ctx["brief"]["what_adds"].lower()
    assert ctx["in_scope"] and ctx["acceptance_criteria"]
    assert "core/gateways.py" in " ".join(ctx["affected_files"])
    assert "no core module imports a concrete provider" in " ".join(ctx["verification"])


def test_empty_body_is_flagged_derived_without_placeholders():
    ctx = backlog._draft_context("x", "")
    assert ctx["brief"]["source"] == "derived"
    assert not any("(derived)" in str(v) for v in ctx.values())


def test_no_derived_sentinel_in_created_items():
    # BI-PF-1338: use the checker's VALUE-PATTERN regex (backlog_context_check._DERIVED), not a raw
    # "(derived)" substring, so legitimate prose (e.g. "materialized-but-regenerated (derived)") passes.
    import importlib.util
    import json
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "bcc", Path(__file__).resolve().parents[3] / "scripts" / "dev" / "backlog_context_check.py")
    bcc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bcc)
    for it in backlog.list_open("product_forge", None):
        blob = json.dumps({k: it.get(k) for k in ("brief", "approach", "verification", "affected_files")},
                          default=str)
        assert not bcc._DERIVED.search(blob), it["id"]
