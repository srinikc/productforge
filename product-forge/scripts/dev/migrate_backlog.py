"""Idempotent backlog migration (Step 12).

Backfills backlog items for existing projects + Product Forge from their current stores:
  * product-plan features      -> BacklogItem(type=feature, origin=pipeline)  [core/backlog_link]
  * open defects               -> BacklogItem(type=bug, origin=pipeline)      [core/backlog_link]
  * intake conversations       -> BacklogItem(origin=intake)                  [core/backlog_link.promote_conversation]
Also ensures the Product Forge scope dir/files exist (plan.json/state.json).

Safe to re-run: every write is keyed by `external_id` (ensure_item) and deduped.
Run: python scripts/dev/migrate_backlog.py [--dry-run]
"""
import os
import sys
sys.path.insert(0, os.getcwd())

DRY = "--dry-run" in sys.argv
REPO = os.getcwd()
PRODUCTS = os.path.join(REPO, "products")


def _projects():
    out = []
    try:
        for name in sorted(os.listdir(PRODUCTS)):
            p = os.path.join(PRODUCTS, name)
            if os.path.isdir(p) and not name.startswith((".", "_")):
                out.append(name)
    except Exception:
        pass
    return out


def migrate_project(project: str) -> dict:
    from core import backlog, backlog_link
    created = {"features": 0, "defects": 0, "conversations": 0}
    # 1) product-plan features
    try:
        from core.product_plan import ProductPlan
        plan = ProductPlan(project, "products")
        for mod in (plan.get_modules() or []):
            for feat in (getattr(mod, "features", []) or []):
                if DRY:
                    continue
                if backlog_link.ensure_feature_item(project, feat):
                    created["features"] += 1
    except Exception:
        pass
    # 2) open defects
    try:
        from core.defect_loop import tracker
        tr = tracker(project)
        for d in (tr.get_open_defects() or []):
            feats = getattr(d, "affected_features", None) or []
            if DRY:
                continue
            if backlog_link.link_defect(project, (feats or [""])[0], d.defect_id,
                                        title=getattr(d, "title", ""),
                                        severity=getattr(getattr(d, "severity", ""), "value", "")):
                created["defects"] += 1
    except Exception:
        pass
    # 3) intake conversations are GLOBAL -> promoted once in main(), not per project
    return created


def ensure_forge():
    from core import forge_store
    if DRY:
        return
    if not os.path.exists(forge_store.plan_path()):
        forge_store.write_plan(forge_store.read_plan())
    if not os.path.exists(forge_store.state_path()):
        forge_store.write_state(forge_store.read_state())


def main():
    print(f"migrate_backlog {'(dry-run)' if DRY else ''}")
    ensure_forge()
    total = {"features": 0, "defects": 0, "conversations": 0}
    for pr in _projects():
        r = migrate_project(pr)
        if any(r.values()):
            print(f"  {pr}: {r}")
        for k in total:
            total[k] += r.get(k, 0)
    # conversations are global: promote ONCE (idempotent by conversation id)
    try:
        from core import backlog_link
        from core.conversation_models import ConversationStore
        n = 0
        for conv in (ConversationStore().list_conversations() or []):
            if DRY:
                continue
            if backlog_link.promote_conversation(conv):
                n += 1
        total["conversations"] = n
        print(f"  conversations promoted (global, once): {n}")
    except Exception as e:
        print(f"  conversations skipped: {e}")
    print(f"totals: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
