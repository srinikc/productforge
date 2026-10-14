"""BI-PF-0395 (A6): language rule + undeclared-dep policy + drift guard - tests that can fail.

Acceptance criteria covered here:
  1. the policy flags a NEW shipped/sensitive Python module and an undeclared runtime dependency;
  2. compliant changes (Go additions, tooling, allowlisted governance, declared imports) pass.

Pure-function tests against injected policy dicts (no repo-state dependence); the gate script itself is a
thin git-scoped wrapper (exercised author-time + precheck + lane).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("PF_OFFLINE", "1")

from core import change_policy as cp  # noqa: E402

POL = {
    "shipped_roots": ["core/", "api/", "adapters/"],
    "sensitive_roots": ["core/licensing.py"],
    "allow_new_python": ["core/change_policy.py"],
    "legacy_exempt_roots": ["dashboard/"],
    "go_roots": ["go/"],
    "tooling_roots": ["scripts/", "config/", "data/", "docs/", "test-framework/"],
    "escape_env": "PF_ALLOW_PY_SHIPPED",
}


def test_classify_areas():
    assert cp.classify_file("core/newmod.py", POL)["area"] == "shipped"
    c = cp.classify_file("product-forge/core/licensing.py", POL)
    assert c["area"] == "shipped" and c["sensitive"] is True
    assert cp.classify_file("go/contract/main.go", POL)["area"] == "go"
    assert cp.classify_file("scripts/dev/x_check.py", POL)["area"] == "tooling"
    assert cp.classify_file("test-framework/tests/pipeline/test_x.py", POL)["area"] == "test"
    assert cp.classify_file("dashboard/server.py", POL)["area"] == "legacy"
    assert cp.classify_file("workergrid/wg.py", POL)["area"] in ("external", "unknown")
    assert cp.classify_file("weirdroot/x.py", POL)["area"] == "unknown"


def test_language_rule_flags_new_shipped_python():
    f = cp.language_rule_findings(["core/x.py"], ["core/x.py"], POL)
    assert len(f) == 1 and f[0]["rule"] == "language-rule" and f[0]["sensitive"] is False
    # EDITS to existing shipped Python (not in added) pass - they ship compiled (A3)
    assert cp.language_rule_findings(["core/licensing.py"], [], POL) == []
    # a new file under a sensitive root entry passes only via the FILE-level allowlist, not name similarity
    f3 = cp.language_rule_findings(["core/licensing_new.py"], ["core/licensing_new.py"], POL)
    assert f3 and f3[0]["sensitive"] is False
    # allowlisted governance module + Go additions pass; shipped __init__ fails closed (no exemption)
    assert cp.language_rule_findings([], ["core/change_policy.py"], POL) == []
    assert cp.language_rule_findings([], ["go/core/main.go"], POL) == []
    assert len(cp.language_rule_findings(["core/sub/__init__.py"], ["core/sub/__init__.py"], POL)) == 1


def test_unclassified_new_python_fails_closed():
    f = cp.unclassified_findings(["weirdroot/tool.py"], POL)
    assert len(f) == 1 and f[0]["rule"] == "unclassified-path"
    assert cp.unclassified_findings(["config/language-rule.json", "docs/x.md"], POL) == []


def test_undeclared_imports_flagged_and_declared_pass():
    src = {"core/_probe.py": "import json\nimport numpy\nimport yaml\nimport fastapi\n"
                             "from core.paths import ROOT\nfrom . import sibling\n"}
    declared = {"numpyx", "fastapi", "pyyaml"}  # numpy missing, yaml via pyyaml alias
    f = cp.undeclared_import_findings(src, POL, declared=declared)
    mods = {x["detail"] for x in f}
    assert any("'numpy'" in m for m in mods), f
    assert not any("'yaml'" in m for m in mods), f   # alias resolved
    assert not any("'fastapi'" in m for m in mods), f
    assert not any("'json'" in m for m in mods), f   # stdlib
    assert not any("sibling" in m for m in mods), f  # relative import
    # unparseable shipped file fails closed
    f2 = cp.undeclared_import_findings({"core/broken.py": "def ("}, POL, declared=set())
    assert f2 and f2[0]["rule"] == "undeclared-dep"
    # tooling/test files are exempt (out_of_scope: non-shipped build-time tooling may stay Python)
    assert cp.undeclared_import_findings({"scripts/dev/x.py": "import numpy"}, POL, declared=set()) == []


def test_drift_report_counts():
    findings = cp.check(["core/x.py"], ["core/x.py", "go/a.go", "core/change_policy.py"],
                        {"core/x.py": "import json\n"}, POL)
    d = cp.drift_report(["core/x.py", "go/a.go", "core/change_policy.py"], findings, POL)
    assert d["added_go"] == 1
    assert d["added_shipped_python_new"] == 1


def test_default_policy_loads_registered_config():
    pol = cp.policy(force_reload=True)
    assert "core/" in pol["shipped_roots"]
    assert "core/change_policy.py" in pol["allow_new_python"]
    assert "dashboard/" in pol["legacy_exempt_roots"]


# --- BI-PF-1338: large new logic added via EDITS to shipped Python -> Go ---
POL_EG = {**POL, "edit_growth": {"max_edit_added_lines": 60, "min_new_defs": 1,
                                 "min_new_branches": 5, "sensitive_edit_added_lines": 20, "allow": []}}


def test_edit_growth_flags_large_new_logic_in_shipped_edit():
    growth = {"core/contracts.py": {"added": 120, "removed": 5, "new_defs": 4, "new_branches": 9}}
    f = cp.edit_growth_findings(["core/contracts.py"], [], growth, POL_EG)
    assert len(f) == 1 and f[0]["rule"] == "language-rule-edit-growth" and f[0]["path"] == "core/contracts.py"


def test_edit_growth_ignores_refactor_small_and_tooling():
    # refactor/move (removed >= added, no new logic) not flagged
    assert cp.edit_growth_findings(["core/x.py"], [],
        {"core/x.py": {"added": 100, "removed": 100, "new_defs": 0, "new_branches": 0}}, POL_EG) == []
    # small edit under threshold not flagged
    assert cp.edit_growth_findings(["core/x.py"], [],
        {"core/x.py": {"added": 30, "removed": 0, "new_defs": 2, "new_branches": 3}}, POL_EG) == []
    # tooling is exempt
    assert cp.edit_growth_findings(["scripts/dev/x.py"], [],
        {"scripts/dev/x.py": {"added": 500, "removed": 0, "new_defs": 9, "new_branches": 9}}, POL_EG) == []


def test_edit_growth_sensitive_lower_bar_and_allowlist():
    g = {"core/licensing.py": {"added": 25, "removed": 0, "new_defs": 1, "new_branches": 0}}
    assert cp.edit_growth_findings(["core/licensing.py"], [], g, POL_EG)          # 25 < 60 but sensitive bar 20
    allow = {**POL_EG, "edit_growth": {**POL_EG["edit_growth"], "allow": ["core/contracts.py"]}}
    assert cp.edit_growth_findings(["core/contracts.py"], [],
        {"core/contracts.py": {"added": 120, "removed": 5, "new_defs": 4, "new_branches": 9}}, allow) == []


def test_check_threads_growth():
    growth = {"core/contracts.py": {"added": 120, "removed": 5, "new_defs": 4, "new_branches": 9}}
    findings = cp.check(["core/contracts.py"], [], {"core/contracts.py": "import json\n"}, POL_EG, growth)
    assert any(f["rule"] == "language-rule-edit-growth" for f in findings)
