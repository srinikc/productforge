"""Verify generated docs are fresh (BI-PF-0258).

Always FAILS on unclassified docs (`gen_docs_index.py --check`) and on generator errors. Stale
DERIVED docs (BACKLOG-SUMMARY/documentation-index/README) race a moving `develop`, so they are a WARN by
default and FATAL only with `--strict` (run in the full/scheduled sweep). Run from product-forge/.
"""
import os
import re
import subprocess
import sys

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

_GEN = re.compile(r"Generated |GENERATED ")
_REL = ("docs/documentation-index.html", "docs/README.md",
        "docs/BACKLOG-SUMMARY.md")  # relative to product-forge/


def _root() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True).stdout.strip() or os.getcwd()
    except Exception:
        return os.getcwd()


def _strip(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return "\n".join(ln for ln in f.read().splitlines() if not _GEN.search(ln))
    except Exception:
        return ""


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    strict = "--strict" in argv
    rc = 0
    r = subprocess.run([sys.executable, "scripts/dev/gen_docs_index.py", "--check"])
    if r.returncode != 0:
        print("[FAIL] gen_docs_index --check (unclassified docs)")
        rc = 1
    for gen in ("scripts/dev/gen_docs_index.py", "scripts/dev/gen_backlog_summary.py"):
        gr = subprocess.run([sys.executable, gen])
        if gr.returncode != 0:
            print(f"[FAIL] generator failed: {gen} (exit {gr.returncode})")
            rc = 1
    root = _root()
    pf = os.path.basename(os.getcwd())  # "product-forge"
    for rel in _REL:
        gf = os.path.join(pf, rel)
        head = subprocess.run(["git", "show", f"HEAD:{gf}"], cwd=root,
                              capture_output=True, text=True).stdout
        head = "\n".join(ln for ln in head.splitlines() if not _GEN.search(ln))
        work = _strip(os.path.join(root, gf))
        if head and head != work:
            # Derived docs (BACKLOG-SUMMARY/documentation-index/README) race a moving `develop`, so a
            # per-change run WARNS; the full/scheduled sweep enforces with --strict (BI-PF-1374).
            if strict:
                print(f"[FAIL] stale generated doc: {gf} (regenerate + commit)")
                rc = 1
            else:
                print(f"[warn] stale generated doc: {gf} (derived; enforced by --strict in the full sweep)")
    print("docs-fresh:", "OK" if rc == 0 else "STALE")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
