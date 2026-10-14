"""BI-PF-1176 (steps 1-2) + BI-PF-1290 (step 3): git MERGE DRIVER for the DERIVED backlog artifacts.

Registered as ``merge.pf-derived.driver`` and attached in the repo ``.gitattributes`` to:

  - ``**/backlog/{open,closed}.json``   -> REGENERATE the lean index from ``items/`` (the truth);
  - ``**/backlog/counters.json``        -> MAX-merge each counter across the three inputs (label/seq safety);
  - ``product-forge/docs/BACKLOG-SUMMARY.md`` + ``documentation-index.html`` -> REGENERATE from the backlog.

Whole-file JSON/HTML is never text-merged (that is exactly what conflicts). Git invokes
``pf_merge_driver.py %O %A %B %P`` -> the merged result must land in ``%A``; exit 0 = resolved. **``%P`` is the
real pathname** (git passes temp files for %O/%A/%B), so the driver uses ``%P`` - never %A - to know which file
it is resolving. A non-derived path returns exit 1 so git keeps its normal conflict.

Append-only ``history/*.jsonl`` uses the built-in ``merge=union`` instead (see ``.gitattributes``)."""
import json
import os
import shutil
import subprocess
import sys

_INDEX_FILES = ("open.json", "closed.json")
_COUNTER_FILES = ("counters.json",)
_DOC_FILES = ("BACKLOG-SUMMARY.md", "documentation-index.html")
_ITEM_DIR = "/backlog/items/"


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
    """Return (scope, project) for a backlog index/counter path, else (None, None)."""
    p = path.replace("\\", "/")
    base = p.rsplit("/", 1)[-1]
    if base not in _INDEX_FILES + _COUNTER_FILES or "/backlog/" not in p:
        return None, None
    pre = p.split("/backlog/")[0]
    if "/products/" in pre:
        project = pre.rsplit("/products/", 1)[1].split("/")[0]
        return "project", project
    if pre.endswith("product-forge") or pre.endswith("data"):
        return "product_forge", None
    return None, None


def is_doc(path: str) -> bool:
    """True for the generated backlog docs (regenerate-on-merge)."""
    return path.replace("\\", "/").rsplit("/", 1)[-1] in _DOC_FILES


def is_item(path: str) -> bool:
    """True for a backlog WORK ITEM file (source; pf-item = newest-version wins)."""
    p = path.replace("\\", "/")
    return _ITEM_DIR in p and p.endswith(".json")


def _item_key(item) -> tuple:
    if not isinstance(item, dict):
        return (-1, "")
    return (int(item.get("revision") or 0), str(item.get("updated_at") or ""))


def _newest_item(paths: list) -> str:
    """Return the path holding the NEWEST item version (max revision, then updated_at)."""
    best, best_key = "", None
    for p in paths:
        if not p:
            continue
        k = _item_key(_load(p))
        if best_key is None or k > best_key:
            best, best_key = p, k
    return best


def _load(p: str) -> dict:
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _max_merge(paths: list) -> dict:
    """Recursively merge JSON dicts, taking the MAX for numeric leaves (counter safety)."""

    def merge(a: dict, b: dict) -> dict:
        out = dict(a)
        for k, v in (b or {}).items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = merge(out[k], v)
            elif (isinstance(v, (int, float)) and not isinstance(v, bool)
                  and isinstance(out.get(k), (int, float)) and not isinstance(out.get(k), bool)):
                out[k] = max(out[k], v)
            elif k not in out:
                out[k] = v
        return out

    merged: dict = {}
    for p in paths:
        if p:
            merged = merge(merged, _load(p))
    return merged


def _copy_result(dst: str, src: str) -> None:
    """Write the resolved content into ``%A`` (git passes a temp file, not the real path)."""
    if os.path.abspath(dst) != os.path.abspath(src):
        shutil.copyfile(src, dst)


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    base = argv[1] if len(argv) > 1 else ""      # %O (merge base temp)
    ours = argv[2] if len(argv) > 2 else ""      # %A (write the result here)
    theirs = argv[3] if len(argv) > 3 else ""    # %B (theirs temp)
    path = argv[4] if len(argv) > 4 else ours    # %P (the REAL pathname; fall back to %A)
    if not ours:
        return 1
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    root = _find_pf_root(path)
    # 1. DERIVED generated docs -> regenerate from the backlog (items/ is the truth), then copy into %A
    if is_doc(path):
        if not root:
            return 1
        try:
            for s in ("scripts/dev/gen_backlog_summary.py", "scripts/dev/gen_docs_index.py"):
                subprocess.run([sys.executable, s], cwd=root, check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _copy_result(ours, os.path.join(root, "docs", name))
        except Exception as e:  # noqa: BLE001
            print(f"pf-merge-driver: doc regeneration failed ({type(e).__name__}: {e})", file=sys.stderr)
            return 1
        return 0
    # 3b. WORK ITEM file -> NEWEST version wins (never let a stale snapshot clobber newer state).
    if is_item(path):
        newest = _newest_item([base, ours, theirs])
        if not newest:
            return 1
        _copy_result(ours, newest)
        return 0
    scope, project = scope_from_path(path)
    if scope is None:
        return 1
    if root and root not in sys.path:
        sys.path.insert(0, root)
    # 2. shared label/id counters -> max-merge (never text-merge)
    if name in _COUNTER_FILES:
        try:
            merged = _max_merge([base, ours, theirs])
            with open(ours, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2)
                f.write("\n")
        except Exception as e:  # noqa: BLE001
            print(f"pf-merge-driver: counters merge failed ({type(e).__name__})", file=sys.stderr)
            return 1
        return 0
    # 3. DERIVED lean indexes -> regenerate from items/, then copy the matching index into %A
    try:
        from core import backlog
        op, cl = backlog._load_all(scope, project)
        backlog._write_indexes(scope, project, op, cl)   # regenerate from items/ (the truth)
        _d, _of, _cf, _h, _c = backlog._paths(scope, project)
        _copy_result(ours, _of if name == "open.json" else _cf)
    except Exception as e:  # noqa: BLE001
        print(f"pf-merge-driver: regeneration failed ({type(e).__name__})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
