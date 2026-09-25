"""APPEND requirement context to thin OPEN backlog items - never overwrite.

Safety: the item's existing `body` (its captured detail) is PRESERVED verbatim under
`## Original (as captured)`; sourced context is APPENDED below it. Nothing is ever replaced,
and every change is journalled (before/after) by core/backlog.py.

Sources (resolved via the item's links / external_id), all authoritative:
  1. design spec     : links.feature_id -> artifacts/1 - Design/features/F-x-functional.md
  2. ideation line   : feature_id not designed -> artifacts/0 - Ideation/ideation-output.md  ("F-x: ...")
  3. paired item     : links.paired_with / backend_ref -> the counterpart item's body (real context)
  4. discovery       : links.discovery_question (P##) -> discovery artifact mention

Usage:
  python scripts/dev/backfill_item_context.py --project ProductForge-Dashboard [--dry-run] [--id BI-0001] [--force]
"""
import os
import re
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core import backlog  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RICH = 200


def _proj_dir(project):
    return os.path.join(REPO, "products", project)


def _feature_id(it):
    f = (it.get("links") or {}).get("feature_id")
    if f:
        return str(f)
    m = re.search(r"(F-\d+)", str(it.get("external_id") or ""))
    return m.group(1) if m else ""


def _parse_sections(text):
    h2, secs, cur = "", {}, None
    for ln in text.splitlines():
        m = re.match(r"^(#{2,3})\s+(.*)$", ln)
        if m:
            if len(m.group(1)) == 2:
                h2 = m.group(2).strip()
            cur = m.group(2).strip()
            secs[cur] = []
        else:
            if cur is None:
                cur, secs[cur] = "_top", []
            secs[cur].append(ln)
    return h2, {k: "\n".join(v).strip() for k, v in secs.items()}


def _pick(secs, *names):
    low = {k.lower(): v for k, v in secs.items()}
    for n in names:
        if low.get(n.lower()):
            return low[n.lower()]
    return ""


def _blk(title, text):
    return f"## {title}\n{text.strip()}\n\n" if (text or "").strip() else ""


def _from_spec(project, fid):
    hits = glob.glob(os.path.join(_proj_dir(project), "artifacts", "1 - Design", "features",
                                  f"{fid}-functional.md"))
    if not hits:
        return None, None
    sp = hits[0]
    h2, secs = _parse_sections(open(sp, encoding="utf-8", errors="ignore").read())
    rel = os.path.relpath(sp, REPO).replace("\\", "/")
    parts = [_blk("Context (from feature design spec)", secs.get(h2) or _pick(secs, "Overview")),
             f"## Source\n`{rel}` - feature **{h2 or fid}**\n\n",
             _blk("In scope (from the feature spec)", _pick(secs, "Requirements")),
             _blk("Acceptance criteria (from the feature spec)", _pick(secs, "Acceptance Criteria")),
             f"## Links\n- feature_id: {fid}\n- spec: {rel}\n"]
    return "".join(parts).strip() + "\n", rel


def _from_ideation(project, fid):
    f = os.path.join(_proj_dir(project), "artifacts", "0 - Ideation", "ideation-output.md")
    if not os.path.exists(f):
        return None, None
    for ln in open(f, encoding="utf-8", errors="ignore"):
        if re.search(rf"F-{re.escape(fid.split('-')[1])}\b", ln) and ":" in ln:
            rel = os.path.relpath(f, REPO).replace("\\", "/")
            return (f"## Context (from ideation)\n{ln.strip().lstrip('- ').strip()}\n\n"
                    f"## Links\n- feature_id: {fid}\n- source: {rel}\n"), rel
    return None, None


def _from_paired(it):
    links = it.get("links") or {}
    for key in ("paired_with", "backend_ref", "backend_item", "capability_ref"):
        refs = links.get(key)
        refs = refs if isinstance(refs, list) else ([refs] if refs else [])
        for ref in refs:
            other = backlog.get_by_ref(ref)
            if other and (other.get("body") or "").strip():
                return (f"## Context (from linked item {ref})\n{other.get('body').strip()}\n\n"
                        f"## Links\n- {key}: {ref}\n"), str(ref)
    return None, None


def build_context(project, it):
    fid = _feature_id(it)
    if fid:
        ctx, src = _from_spec(project, fid)
        if ctx:
            return ctx, src
        ctx, src = _from_ideation(project, fid)
        if ctx:
            return ctx, src
    ctx, src = _from_paired(it)
    if ctx:
        return ctx, src
    return None, f"no source (feature_id={fid or '-'})"


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="APPEND sourced context to thin OPEN items (never overwrite).")
    ap.add_argument("--project", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--id", default="")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    op = backlog.list_open("project", a.project, order=False)
    done = skipped = 0
    for it in op:
        if a.id and it["id"] != a.id:
            continue
        cur = it.get("body") or ""
        if len(cur) >= RICH and not a.force and not a.id:
            continue
        ctx, src = build_context(a.project, it)
        if not ctx:
            print(f"  SKIP {it['id']}: {src}")
            skipped += 1
            continue
        merged = (f"## Original (as captured)\n{cur.strip()}\n\n" if cur.strip() else "") + ctx
        print(f"  {'DRY ' if a.dry_run else 'SET '}{it['id']} <- {src}  "
              f"(body {len(cur)} -> {len(merged)} chars, original preserved)")
        if not a.dry_run:
            backlog.update("project", a.project, it["id"], body=merged,
                           _note=f"context appended from {src} (original preserved)")
        done += 1
    print(f"\n{'DRY-RUN ' if a.dry_run else ''}appended={done} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
