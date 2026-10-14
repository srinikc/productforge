"""Merge backlog ITEM files by NEWEST version (repair a stale durable-state clobber).

Root cause it repairs: ``core/state_checkpoint.py`` copies the WHOLE durable tree
(``data/backlog/items``, ``history``, indexes, issues, id-blocks) from a session's
(possibly stale) runtime checkout into a fresh branch and ``git add -A``s it, so an
OLDER snapshot overwrites NEWER items on ``develop`` (last-writer-wins). Only the
derived files have a merge driver; item files (source) have no version guard.

This tool merges per item so the NEWEST wins - by ``(revision, updated_at)`` - restores
missing items, unions ``history/*.jsonl`` chronologically, and rebuilds the derived
indexes via ``core.backlog`` (the single writer). Idempotent.

Usage:
  python scripts/dev/backlog_item_merge.py --base <ref>            # dry-run (report)
  python scripts/dev/backlog_item_merge.py --base <ref> --apply    # write + reindex
"""
import argparse
import json
import os
import subprocess
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:  # executed as a script: seed the repo root, then retry (paths-contract pattern)
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_APP = str(_ROOT)

_BACKLOG_REL = "data/backlog"          # app-relative
_ITEMS_REL = _BACKLOG_REL + "/items"
_HIST_REL = _BACKLOG_REL + "/history"
_GIT_PREFIX = "product-forge/"         # repo-relative prefix (repo root is the parent clone)


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", _APP, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def _ref_paths(ref: str, rel_dir: str) -> list:
    out = _git("ls-tree", "-r", "--name-only", ref, "--", _GIT_PREFIX + rel_dir)
    prefix = _GIT_PREFIX + rel_dir + "/"
    return [ln[len(prefix):] for ln in out.splitlines() if ln.startswith(prefix)]


def _ref_file(ref: str, rel: str):
    txt = _git("show", f"{ref}:{_GIT_PREFIX}{rel}")
    try:
        return json.loads(txt)
    except Exception:
        return None


def _load(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _key(item: dict):
    if not isinstance(item, dict):
        return (-1, "")
    return (int(item.get("revision") or 0), str(item.get("updated_at") or ""))


def _write(path: str, item: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(item, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def _merge_history(ref: str, apply: bool) -> int:
    """Union ``history/*.jsonl`` from ``ref`` and the working tree (chronological), idempotently."""
    changed = 0
    hist_dir = os.path.join(_APP, _HIST_REL)
    os.makedirs(hist_dir, exist_ok=True)
    ref_files = set(_ref_paths(ref, _HIST_REL))
    work_files = {f for f in os.listdir(hist_dir)} if os.path.isdir(hist_dir) else set()
    for name in sorted(ref_files | work_files):
        rel = f"{_HIST_REL}/{name}"
        ref_lines = [ln for ln in _git("show", f"{ref}:{_GIT_PREFIX}{rel}").splitlines() if ln.strip()]
        path = os.path.join(hist_dir, name)
        work_lines = []
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                work_lines = [ln for ln in f.read().splitlines() if ln.strip()]

        def _ts(ln):
            try:
                return json.loads(ln).get("at", "")
            except Exception:
                return ""

        union = ref_lines + [ln for ln in work_lines if ln not in set(ref_lines)]
        merged = sorted(dict.fromkeys(union), key=_ts)
        if merged != work_lines:
            changed += 1
            if apply:
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write("\n".join(merged) + ("\n" if merged else ""))
    return changed


def _reindex() -> None:
    from core import backlog as _b
    op, cl = _b._load_all("product_forge", None)
    _b._write_indexes("product_forge", None, op, cl)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Merge backlog items by newest version (state-clobber repair)")
    ap.add_argument("--base", required=True, help="good reference ref (e.g. the pre-clobber develop tip)")
    ap.add_argument("--apply", action="store_true", help="write changes + rebuild indexes")
    a = ap.parse_args(argv)

    items_dir = os.path.join(_APP, _ITEMS_REL)
    ref_ids = {n[:-5] for n in _ref_paths(a.base, _ITEMS_REL) if n.endswith(".json")}
    work_ids = {n[:-5] for n in os.listdir(items_dir) if n.endswith(".json")} if os.path.isdir(items_dir) else set()

    restored, kept_base, kept_work = [], [], []
    for iid in sorted(ref_ids | work_ids):
        rel = f"{_ITEMS_REL}/{iid}.json"
        ref_it = _ref_file(a.base, rel)
        work_it = _load(os.path.join(items_dir, iid + ".json"))
        if work_it is None:
            chosen, why = ref_it, "restore(missing)"
        elif ref_it is None:
            chosen, why = work_it, "keep(new)"
        elif _key(ref_it) > _key(work_it):
            chosen, why = ref_it, "restore(newer)"
        else:
            chosen, why = work_it, "keep"
        if why == "restore(newer)" or why == "restore(missing)":
            restored.append(iid)
        elif why == "keep(new)":
            kept_work.append(iid)
        else:
            kept_base.append(iid)
        if a.apply and chosen is not None and chosen != work_it:
            _write(os.path.join(items_dir, iid + ".json"), chosen)

    hist = _merge_history(a.base, a.apply)
    print(f"backlog-item-merge: base={a.base} items={len(ref_ids | work_ids)} "
          f"restored={len(restored)} kept_new={len(kept_work)} unchanged={len(kept_base)} "
          f"history_files_changed={hist} ({'APPLIED' if a.apply else 'dry-run'})")
    if restored:
        print("  restored:", ", ".join(restored[:20]) + (" ..." if len(restored) > 20 else ""))
    if a.apply:
        _reindex()
        print("  indexes rebuilt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
