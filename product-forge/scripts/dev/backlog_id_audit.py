"""BI-PF-0457 fail-closed gate: no duplicate backlog ids within any scope.

Root cause of the 0455 collision: backlog ids are allocated from a LOCAL per-worktree counter, so two concurrent
sessions can compute the same next id and only discover it on merge/push. This gate catches a duplicate id at
--full precheck / merge time (and CI), so a collided id can never land on the integration branch.

Scopes are independent (a project's BI-0001 != product_forge's BI-0001), so uniqueness is per-scope.
"""
import glob
import json
import os
import sys

try:
    from core.paths import PRODUCTS_DIR, ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    PRODUCTS_DIR = os.path.join(_ROOT, "products")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _item_dirs():
    out = [("product_forge", os.path.join(str(_ROOT), "data", "backlog", "items"))]
    root = str(PRODUCTS_DIR)
    for n in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if n.startswith(("_", ".")):
            continue
        p = os.path.join(root, n, "backlog", "items")
        if os.path.isdir(p):
            out.append((f"project:{n}", p))
    return out


def duplicates():
    dups = []
    for label, d in _item_dirs():
        seen = {}
        for f in glob.glob(os.path.join(d, "*.json")):
            try:
                with open(f, encoding="utf-8") as fh:
                    it = json.load(fh)
            except Exception:
                continue
            iid = str(it.get("id") or os.path.basename(f)[:-5])
            seen.setdefault(iid, []).append(os.path.basename(f))
        for iid, files in seen.items():
            if len(files) > 1:
                dups.append(f"{label}:{iid} -> {sorted(files)}")
    return dups


def main(argv=None) -> int:
    dups = duplicates()
    n = sum(len(glob.glob(os.path.join(d, "*.json"))) for _, d in _item_dirs())
    if dups:
        print(f"backlog-ids: FAIL ({len(dups)} duplicate id(s) across {n} items) - resolve the collision "
              "(renumber the newer item) before merging")
        for x in dups[:20]:
            print("   -", x)
        return 1
    print(f"backlog-ids: OK ({n} items, all ids unique per scope)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
