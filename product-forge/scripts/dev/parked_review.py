"""Parked-item review prompts (BI-0020 tail).

Emits a `follow_up_due` event for every parked/explore backlog item whose weekly
follow-up is due and not snoozed (backlog.parked_review). Wire into cron/scheduler or
run ad hoc:  python scripts/dev/parked_review.py [--project <name>]

Supports snoozing: `backlog.set_follow_up(scope, project, id, snooze_days=N)`.
"""
import os
import sys
sys.path.insert(0, os.getcwd())


def main():
    from core import backlog, event_bus
    due = backlog.parked_review()
    for item in due:
        event_bus.emit("follow_up_due", item_id=item.get("id"),
                       scope=item.get("scope"), project=item.get("project"),
                       title=item.get("title", ""), label=item.get("label", ""))
    print(f"parked review: {len(due)} item(s) due")
    for i in due:
        print(f"  {i.get('id')} {i.get('label','')} :: {i.get('title','')[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
