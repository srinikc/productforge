"""BI-PF-0764 - merge/PR reconcile: RENUMBER duplicate backlog ids (the incoming side) and fix all references.

Run at merge/PR (wired into precheck before the id audit). For each duplicated id per scope, keeps the item
that is on ``origin/develop`` (else the earliest ``created_at``) and renumbers the other(s) to a fresh id from the
allocator, then updates every reference (deps/blocked_by/epic/parent/children/links) and regenerates indexes.
Dry-run by default; ``--write`` applies.
"""
import argparse
import glob
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

from core import backlog, id_allocator  # noqa: E402


def _scopes(include_all=True):
    out = [("product_forge", None)]
    try:
        from core.paths import PRODUCTS_DIR
        root = str(PRODUCTS_DIR)
        for n in sorted(os.listdir(root)) if os.path.isdir(root) else []:
            if not n.startswith(("_", ".")) and os.path.isdir(os.path.join(root, n, "backlog", "items")):
                out.append(("project", n))
    except Exception:
        pass
    return out


def _items_dir(scope, project):
    return os.path.join(backlog._dir(scope, project), "items")


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _on_base(path):
    """True if this item path already exists on origin/develop (the incoming side is the non-base one)."""
    rel = os.path.relpath(path, _ROOT).replace("\\", "/")
    try:
        r = subprocess.run(["git", "cat-file", "-e", f"origin/develop:{rel}"],
                           cwd=_ROOT, capture_output=True, text=True)
        return r.returncode == 0
    except Exception:
        return False


def _dups():
    for scope, project in _scopes():
        d = _items_dir(scope, project)
        seen = {}
        for f in glob.glob(os.path.join(d, "*.json")):
            it = _load(f) or {}
            seen.setdefault(str(it.get("id")), []).append(f)
        for iid, files in seen.items():
            if len(files) > 1:
                yield scope, project, iid, sorted(files)


def _max_num(scope, project):
    mx = 0
    for f in glob.glob(os.path.join(_items_dir(scope, project), "*.json")):
        it = _load(f) or {}
        mx = max(mx, backlog._num(str(it.get("id") or "")))
    return mx


def _rewrite_references(scope, project, mapping):
    d = _items_dir(scope, project)
    for f in glob.glob(os.path.join(d, "*.json")):
        it = _load(f)
        if not it:
            continue
        ch = False
        for fld in ("epic", "parent"):
            if it.get(fld) in mapping:
                it[fld] = mapping[it[fld]]
                ch = True
        for fld in ("deps", "blocked_by", "children"):
            if isinstance(it.get(fld), list):
                nv = [mapping.get(x, x) for x in it[fld]]
                if nv != it[fld]:
                    it[fld] = nv
                    ch = True
        L = it.get("links") or {}
        for k, v in list(L.items()):
            if isinstance(v, str) and v in mapping:
                L[k] = mapping[v]
                ch = True
            elif isinstance(v, list):
                nv = [mapping.get(x, x) for x in v]
                if nv != v:
                    L[k] = nv
                    ch = True
        if ch:
            with open(f, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(it, fh, indent=2, ensure_ascii=False)


def reconcile(write=False):
    moves = []
    for scope, project, iid, files in list(_dups()):
        keep = next((f for f in files if _on_base(f)), None)
        if keep is None:
            keep = min(files, key=lambda f: (_load(f) or {}).get("created_at") or "")
        losers = [f for f in files if f != keep]
        for lf in losers:
            it = _load(lf)
            if not it:
                continue
            n = id_allocator.alloc(scope, project, existing_max=_max_num(scope, project), session="reconcile")
            newid = f"BI-{str(it.get('tag') or 'GEN')}-{n:04d}"
            moves.append({"scope": scope, "project": project, "old": iid, "new": newid, "file": lf})
            if write:
                it["id"] = newid
                d = _items_dir(scope, project)
                newf = os.path.join(d, f"{newid}.json")
                with open(newf, "w", encoding="utf-8", newline="\n") as fh:
                    json.dump(it, fh, indent=2, ensure_ascii=False)
                os.remove(lf)
                hist = os.path.join(backlog._dir(scope, project), "history")
                old_h = os.path.join(hist, f"{iid}.jsonl")
                if os.path.exists(old_h):
                    os.replace(old_h, os.path.join(hist, f"{newid}.jsonl"))
    if write and moves:
        for scope, project in {(m["scope"], m["project"]) for m in moves}:
            mapping = {m["old"]: m["new"] for m in moves if (m["scope"], m["project"]) == (scope, project)}
            _rewrite_references(scope, project, mapping)
            op, cl = backlog._load_all(scope, project)
            backlog._write_indexes(scope, project, op, cl)
    return moves


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="apply the renumbering (default: report only)")
    a = ap.parse_args(argv)
    moves = reconcile(write=a.write)
    if not moves:
        print("backlog-reconcile: OK (no duplicate ids)")
        return 0
    verb = "RENUMBERED" if a.write else "would renumber"
    print(f"backlog-reconcile: {verb} {len(moves)} duplicate id(s)")
    for m in moves:
        print(f"   - {m['scope']}:{m['old']} -> {m['new']}")
    return 0 if a.write else 1


if __name__ == "__main__":
    raise SystemExit(main())
