"""BI-PF-1066 (E3) - non-LLM high-risk-pattern scan over CHANGED files (advisory by default).

A cheap, mechanical safety-net beneath the LLM reviewer: flags the most dangerous code patterns in the change
(vs merge-base with ``develop`` + the working tree), so production-risk review is not purely LLM judgement.
Findings are ADVISORY (exit 0) unless ``--strict`` (exit 1 on any finding). Framework-agnostic; no dashboard.
"""
import argparse
import os
import re
import subprocess
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

INTEGRATION = "develop"
_SQL_KW = r"(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|UNION)"
PATTERNS = [
    ("sqli_fstring", re.compile(r"(execute|executemany|query)\s*\(\s*f[\"'].*?" + _SQL_KW, re.I),
     "SQL built from an f-string (possible injection) - use parameterized queries"),
    ("sqli_concat", re.compile(r"(execute|executemany|query)\s*\([^)]*\)?\s*\+.*?" + _SQL_KW, re.I),
     "SQL built by string concatenation (possible injection) - use parameterized queries"),
    ("eval_exec", re.compile(r"\b(eval|exec)\s*\("), "eval/exec on input - avoid; parse/validate instead"),
    ("shell_true", re.compile(r"shell\s*=\s*True"), "subprocess shell=True - injection/portability risk"),
    ("os_system", re.compile(r"\bos\.system\s*\("), "os.system - use subprocess with an arg list"),
    ("pickle_load", re.compile(r"\bpickle\.loads?\s*\("), "pickle load - unsafe deserialization"),
    ("yaml_load", re.compile(r"\byaml\.load\s*\("), "yaml.load - use yaml.safe_load"),
    ("delete_no_where", re.compile(r"\bDELETE\s+FROM\s+\w+", re.I), "DELETE - confirm a WHERE clause / bounded scope"),
]
SCAN_EXT = (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb", ".java", ".php", ".sql")
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "workergrid", "vendor", "dist", "build"}


def _git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=_ROOT, capture_output=True, text=True)
    return (r.stdout or "").strip()


def changed_files() -> list:
    files = set()
    base = _git("merge-base", INTEGRATION, "HEAD")
    if base:
        files |= set(_git("diff", "--name-only", base, "HEAD").splitlines())
    files |= set(_git("diff", "--name-only", "HEAD").splitlines())
    out = []
    for f in files:
        f = f.replace("\\", "/").strip()
        if not f.endswith(SCAN_EXT) or any(x in f for x in SKIP_DIRS):
            continue
        out.append(f)
    return out


def scan_text(text: str) -> list:
    """Return [(pattern_name, linenumber, message)] for a text blob."""
    hits = []
    for i, line in enumerate((text or "").splitlines(), 1):
        for name, rx, msg in PATTERNS:
            if rx.search(line):
                hits.append((name, i, msg))
    return hits


def _iter_targets():
    for rel in changed_files():
        p = os.path.join(_ROOT, rel)
        if os.path.isfile(p):
            yield rel, p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit 1 on any finding (fatal)")
    a = ap.parse_args(argv)
    findings = []
    for rel, p in _iter_targets():
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                txt = f.read()
        except Exception:
            continue
        for name, ln, msg in scan_text(txt):
            findings.append(f"{rel}:{ln}: [{name}] {msg}")
    if findings:
        print(f"review-static: {len(findings)} high-risk finding(s) [{'FATAL' if a.strict else 'advisory'}]")
        for x in findings[:20]:
            print("   -", x)
        return 1 if a.strict else 0
    print("review-static: OK (no high-risk patterns in changed files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
