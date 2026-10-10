"""A6 gate (BI-PF-0395): language rule + undeclared runtime deps, scoped to CHANGED files.

Enforces the LOCKED delivery baseline (BI-PF-0387 / ADR BI-PF-0388) at author time and in precheck:

* language rule   - a NEW ``.py`` under a shipped root (core/ api/ adapters/) fails unless the file is a
                    declared allowlist entry (config/language-rule.json); new Go is always fine; edits to
                    existing shipped Python pass (they ship compiled via A3).
* undeclared deps - a changed shipped ``.py`` importing a third-party module not declared in pyproject
                    fails (stdlib / first-party / declared+aliases pass). Complements dependency-catalog
                    (BI-PF-0443: new DECLARED deps need a tool-catalog entry; this covers undeclared ones).
* drift guard     - a NEW ``.py`` under an unrecognized top-level path fails (placement, AGENTS.md #5)
                    and the run prints an advisory drift line (added Go vs new shipped Python vs deps).

Policy lives in core/change_policy.py (single reader of config/language-rule.json); this script only does
git scoping (mirrors store_check.py: merge-base with develop + working tree + untracked) and reporting.

Usage:
  python scripts/dev/language_rule_check.py                 # check (exit 1 on violation)
  python scripts/dev/language_rule_check.py --json          # machine-readable findings
  python scripts/dev/language_rule_check.py --files a,b --added c,d   # explicit scope (tests/manual)
Escape hatch: PF_ALLOW_PY_SHIPPED=1 (mirrors PF_ALLOW_UNCATALOGUED) - downgrades violations to warnings.
"""
import argparse
import json
import os
import subprocess
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_INTEGRATION = "develop"


def _git(*args):
    r = subprocess.run(["git", *args], cwd=_ROOT, capture_output=True, text=True, timeout=120)
    return (r.stdout or "").splitlines()


def _merge_base():
    for ref in ("origin/develop", "develop"):
        mb = _git("merge-base", ref, "HEAD")
        if mb and mb[0].strip():
            return mb[0].strip()
    return "HEAD"


def git_scope():
    """(changed, added) repo paths vs merge-base, incl. working tree + untracked (mirrors store_check)."""
    base = _merge_base()
    changed = [l.strip() for l in _git("diff", "--name-only", base) if l.strip()]
    added = [l.strip() for l in _git("diff", "--name-only", "--diff-filter=A", base) if l.strip()]
    untracked = [l.strip() for l in _git("ls-files", "--others", "--exclude-standard") if l.strip()]
    return sorted(set(changed + untracked)), sorted(set(added + untracked))


def load_sources(shipped_py_paths):
    """Read the (normalized) shipped .py files that the undeclared-dep check must parse."""
    from core import change_policy
    sources = {}
    for p in shipped_py_paths:
        n = change_policy.normalize(p)
        if not n.endswith(".py"):
            continue
        fp = os.path.join(_ROOT, *n.split("/")) if n else ""
        try:
            if os.path.isfile(fp):
                sources[n] = open(fp, encoding="utf-8", errors="ignore").read()
        except Exception:
            sources[n] = ""  # unreadable -> parse error path flags it (fail-closed)
    return sources


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--files", default="", help="explicit changed list (comma-separated), skip git")
    ap.add_argument("--added", default="", help="explicit added list (comma-separated), implies --files")
    ap.add_argument("--json", action="store_true", help="emit machine-readable findings")
    a = ap.parse_args(argv)

    from core import change_policy
    pol = change_policy.policy()

    if a.files or a.added:
        changed = [x.strip() for x in a.files.split(",") if x.strip()]
        added = [x.strip() for x in a.added.split(",") if x.strip()] or changed
    else:
        changed, added = git_scope()

    shipped_py = [p for p in set(changed) if change_policy.normalize(p).endswith(".py")]
    findings = change_policy.check(changed, added, load_sources(shipped_py), pol)
    drift = change_policy.drift_report(added, findings, pol)
    escape = bool(os.environ.get(pol.get("escape_env", "PF_ALLOW_PY_SHIPPED")))

    if a.json:
        print(json.dumps({"result": ("warn" if findings and escape else "fail" if findings else "pass"),
                          "changed": len(changed), "added": len(added),
                          "drift": drift, "findings": findings}))
    else:
        print(f"language-rule: {len(changed)} changed / {len(added)} added files in scope | "
              f"drift: go_added={drift['added_go']} new_shipped_py_violations="
              f"{drift['added_shipped_python_new']} undeclared_deps={drift['undeclared_deps']} "
              f"unclassified={drift['unclassified']}")
        for f in findings:
            print(f"   - [{f['rule']}] {f['path']}: {f['detail']}")
        if findings and escape:
            print(f"language-rule: WARN ({len(findings)} violation(s)) - {pol.get('escape_env')} escape set")
            return 0
        if findings:
            print(f"language-rule: FAIL ({len(findings)} violation(s)) - "
                  "new shipped Python must be Go / imports must be declared (BI-PF-0387/0395)")
            return 1
        print("language-rule: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
