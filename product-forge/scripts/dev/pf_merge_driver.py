"""BI-PF-1176 (step 2): git MERGE DRIVER for the DERIVED backlog lean indexes.

Registered as ``merge.pf-derived.driver`` and attached to ``**/backlog/{open,closed}.json`` in .gitattributes.
Instead of text-merging whole-file JSON (which conflicts), it REGENERATES the index from ``items/`` (the truth).
Git invokes: ``pf_merge_driver.py %O %A %B`` -> the merged result must end up in ``%A``; exit 0 = resolved.

Append-only ``history/*.jsonl`` uses the built-in ``merge=union`` instead (see .gitattributes). ``counters.json``
is NOT auto-driven (label safety) - step 3."""
import os
import sys

_INDEX_FILES = ("open.json", "closed.json")


def _find_pf_root(ours: str) -> str:
    """Locate the ``product-forge`` dir from the conflict path (%A), fall back to cwd walk."""
    p = ours.replace("\\", "/")
    idx = p.find("product-forge/")
    if idx >= 0:
        return p[: idx + len("product-forge")]
    cwd = os.getcwd()
    for _ in range(5):
        cand = os.path.join(cwd, "product-forge")
        if os.path.isfile(os.path.join(cand, "core", "paths.py")):
            return cand
        cwd = os.path.dirname(cwd)
    return ""


def scope_from_path(path: str):
    """Return (scope, project) for a backlog index path, else (None, None)."""
    p = path.replace("\\", "/")
    base = p.rsplit("/", 1)[-1]
    if base not in _INDEX_FILES or "/backlog/" not in p:
        return None, None
    pre = p.split("/backlog/")[0]
    if "/products/" in pre:
        project = pre.rsplit("/products/", 1)[1].split("/")[0]
        return "project", project
    if pre.endswith("product-forge") or pre.endswith("data"):
        return "product_forge", None
    return None, None


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    ours = argv[2] if len(argv) > 2 else ""
    scope, project = scope_from_path(ours)
    if scope is None:
        return 1                                   # not a derived index -> let git keep the conflict
    root = _find_pf_root(ours)
    if root and root not in sys.path:
        sys.path.insert(0, root)
    try:
        from core import backlog
        d, _of, _cf, _h, _c = backlog._paths(scope, project)
        op, cl = backlog._load_all(scope, project)
        backlog._write_indexes(scope, project, op, cl)   # regenerate from items/ (the truth)
    except Exception as e:  # noqa: BLE001
        print(f"pf-merge-driver: regeneration failed ({type(e).__name__})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
