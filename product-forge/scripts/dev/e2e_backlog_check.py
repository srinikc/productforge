"""E2E wiring check for the backlog backbone (Step 12).

Chain: adapter intake -> conversation -> BacklogItem -> plan feature -> iteration(item_ids)
       -> defect -> bug item -> done.  Scratch project only (`products/_e2e_backlog/`).

Run: python scripts/dev/e2e_backlog_check.py
"""
import os
import sys
sys.path.insert(0, os.getcwd())

PROJ = "_e2e_backlog"
ok = True


def check(label, cond, extra=""):
    global ok
    print(f"  [{'PASS' if cond else 'FAIL'}] {label} {extra}")
    ok = ok and bool(cond)


def main():
    import shutil
    shutil.rmtree(os.path.join("products", PROJ), ignore_errors=True)

    from core import intake, backlog, backlog_link
    from core.product_plan import ProductPlan
    from core.iteration_planner import plan_iterations

    # 1) intake -> item (origin=intake)
    it = intake.ingest("generic", {"title": "Add CSV export", "scope": "project",
                                   "project": PROJ, "kind": "enhancement", "value": 4})
    check("intake -> BacklogItem", bool(it.get("id")), f"{it.get('id')} {it.get('label','')}")
    check("item origin=intake", it.get("origin") == "intake")

    # 2) feature -> item (origin=pipeline) + reverse index
    plan = ProductPlan(PROJ, "products")
    plan.add_module("core", "Core", 1)
    plan.add_feature("F-1", "CSV export", "core", "must-have", 1)
    plan.save()
    feat = plan.get_feature("F-1")
    item_f = backlog_link.ensure_feature_item(PROJ, feat)
    check("feature -> BacklogItem", bool(item_f and item_f.get("id")), str(item_f and item_f.get("id")))
    check("item.links.feature_id", (item_f or {}).get("links", {}).get("feature_id") == "F-1")

    # 3) feature status mirrors to item
    plan.update_feature_status("F-1", "completed", agent="implement")
    f2 = plan.get_feature("F-1")
    mirrored = backlog.get_epic("project", PROJ, f2.backlog_id) if f2.backlog_id else None
    check("feature.backlog_id set", bool(f2.backlog_id), str(f2.backlog_id))
    check("status mirror completed->verifying", (mirrored or {}).get("status") == "verifying",
          str((mirrored or {}).get("status")))

    # 4) iteration carries item_ids
    iters = plan_iterations([{"id": "F-1", "title": "CSV export", "priority": "must-have",
                              "backlog_id": f2.backlog_id}])
    check("iteration.item_ids", bool(iters and iters[0].item_ids), str(iters and iters[0].item_ids))

    # 5) defect -> bug item; resolve -> done
    bug = backlog_link.link_defect(PROJ, "F-1", "D-9", title="CSV has wrong delimiter")
    check("defect -> bug item", bool(bug and bug.get("type") == "bug"), str(bug and bug.get("id")))
    resolved = backlog_link.resolve_defect(PROJ, "D-9")
    check("defect resolved -> item done", (resolved or {}).get("status") == "done",
          str((resolved or {}).get("status")))

    # 6) parked idea via intake (explore) -> follow-up
    idea = intake.ingest("generic", {"title": "Voice notes someday", "scope": "pipeline", "kind": "idea"})
    full = backlog.get_epic("product_forge", None, idea.get("id")) if idea.get("id") else None
    check("explore idea parked + follow_up", bool(full and full.get("status") == "parked"
                                                  and full.get("follow_up")), str((full or {}).get("status")))

    # cleanup: scratch project + the parked test idea only
    if idea.get("id"):
        backlog.update("product_forge", None, idea["id"], status="done", _note="e2e cleanup")
    shutil.rmtree(os.path.join("products", PROJ), ignore_errors=True)

    print("\nE2E:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
