#!/usr/bin/env python3
"""
Approval CLI - Human-in-the-Loop approval for pipeline agents.

Usage:
    python approve.py --project <project> --stage <stage> --agent <agent> --approve [--notes "..."]
    python approve.py --project <project> --stage <stage> --agent <agent> --reject [--notes "..."]
    python approve.py --project <project> --stage <stage> --agent <agent> --changes --notes "..."
    python approve.py --project <project> --stage <stage> --agent <agent> --regenerate
    python approve.py --project <project> --stage <stage> --agent <agent> --skip
    python approve.py --project <project> --stage <stage> --agent <agent> --abort
    python approve.py --project <project> --stage <stage> --agent <agent> --conditions "..."
    python approve.py --project <project> --stage <stage> --agent <agent> --snooze <minutes>
    python approve.py --project <project> --stage <stage> --agent <agent> --wait-minutes <minutes>
    python approve.py --project <project> --stage <stage> --agent <agent> --wait-indefinite
    python approve.py --project <project> --list
    python approve.py --project <project> --status <stage> <agent>

Examples:
    python approve.py --project myworld --stage 2 --agent architect --approve
    python approve.py --project myworld --stage 2 --agent architect --approve --notes "Looks good"
    python approve.py --project myworld --stage 1 --agent gate-AG-scope-change --approve
    python approve.py --project myworld --list
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path


def find_project_dir(project_name: str, products_dir: str = "products") -> Path:
    """Find project directory."""
    project_dir = Path(products_dir) / project_name
    if not project_dir.exists():
        # Try to find it
        for p in Path(products_dir).iterdir():
            if p.is_dir() and project_name in p.name:
                return p
        raise FileNotFoundError(f"Project not found: {project_name}")
    return project_dir


def list_pending_approvals(project_dir: Path):
    """List all pending approval requests."""
    approvals_dir = project_dir / "approvals"
    if not approvals_dir.exists():
        print("No approvals directory found.")
        return
    
    pending = []
    for stage_dir in approvals_dir.iterdir():
        if stage_dir.is_dir():
            for approval_file in stage_dir.glob("*-approval.json"):
                try:
                    with open(approval_file, 'r', encoding='utf-8') as f:
                        request = json.load(f)
                    if request.get("status") == "pending":
                        pending.append(request)
                except Exception:
                    pass
    
    if not pending:
        print("No pending approvals.")
        return
    
    print(f"\n{'='*70}")
    print(f"PENDING APPROVALS ({len(pending)})")
    print(f"{'='*70}")
    
    for req in pending:
        print(f"\n  Request ID: {req['request_id']}")
        print(f"  Stage: {req['stage_id']}")
        print(f"  Agent: {req['agent_id']}")
        if req.get('gate_id'):
            print(f"  Gate: {req['gate_id']}")
        print(f"  Created: {req['created_at']}")
        print(f"  Artifacts: {len(req.get('artifacts', []))}")
        print(f"  Instructions: {req.get('review_instructions', 'None')}")
        
        # Show artifact paths
        for artifact in req.get('artifacts', []):
            print(f"    - {artifact}")
    
    print(f"\nTo approve:            python approve.py --project <project> --stage <stage> --agent <agent> --approve")
    print(f"To approve w/ conds:   python approve.py ... --approve --conditions \"...\"")
    print(f"To request changes:    python approve.py ... --changes --notes \"...\"")
    print(f"To regenerate:         python approve.py ... --regenerate")
    print(f"To skip:               python approve.py ... --skip")
    print(f"To reject:             python approve.py ... --reject")
    print(f"To abort pipeline:     python approve.py ... --abort")
    print(f"To snooze:             python approve.py ... --snooze <minutes>")
    print(f"To wait further:       python approve.py ... --wait-minutes <minutes>")
    print(f"To wait indefinitely:  python approve.py ... --wait-indefinite")


def get_approval_status(project_dir: Path, stage_id: str, agent_id: str):
    """Get status of an approval request."""
    approval_file = project_dir / "approvals" / stage_id / f"{agent_id}-approval.json"
    
    if not approval_file.exists():
        print(f"No approval request found for stage {stage_id}, agent {agent_id}")
        return
    
    with open(approval_file, 'r', encoding='utf-8') as f:
        request = json.load(f)
    
    print(f"\nApproval Request Status:")
    print(f"  Request ID: {request['request_id']}")
    print(f"  Stage: {request['stage_id']}")
    print(f"  Agent: {request['agent_id']}")
    print(f"  Status: {request['status'].upper()}")
    print(f"  Created: {request['created_at']}")
    
    if request.get('approved_by'):
        print(f"  Approved by: {request['approved_by']}")
        print(f"  Approved at: {request['approved_at']}")
        if request.get('notes'):
            print(f"  Notes: {request['notes']}")
    
    # Show artifacts
    print(f"\n  Artifacts to review:")
    for artifact in request.get('artifacts', []):
        print(f"    - {artifact}")
        if os.path.exists(artifact):
            # Show first 500 chars of artifact
            try:
                with open(artifact, 'r', encoding='utf-8') as f:
                    content = f.read(500)
                print(f"      Preview: {content[:200]}...")
            except Exception:
                print(f"      (could not read preview)")


def resolve_approval(project_dir: Path, stage_id: str, agent_id: str, status: str,
                     notes: str = "", conditions: str = "", extra: dict = None,
                     resolved_by: str = "human"):
    """Apply a decision to a pending approval request.

    `status` is the resulting request status (approved, approved_with_conditions,
    changes, regenerate, skip, rejected, abort, snoozed, waiting, expired).
    `extra` carries side fields (snooze_until / wait_until / wait_indefinite).
    """
    approval_file = project_dir / "approvals" / stage_id / f"{agent_id}-approval.json"

    if not approval_file.exists():
        print(f"Error: No approval request found for stage {stage_id}, agent {agent_id}")
        return False

    with open(approval_file, 'r', encoding='utf-8') as f:
        request = json.load(f)

    if request['status'] != 'pending':
        print(f"Error: Request already {request['status']}")
        return False

    # Update request
    request['status'] = status
    request['approved_by'] = resolved_by
    request['approved_at'] = datetime.now().isoformat()
    request['notes'] = notes
    if conditions:
        request['conditions'] = conditions
    if extra:
        request.update(extra)

    # Save updated request
    with open(approval_file, 'w', encoding='utf-8') as f:
        json.dump(request, f, indent=2, ensure_ascii=False)

    print(f"\nDECISION [{status.upper()}]: {agent_id} in stage {stage_id}")
    print(f"  Request ID: {request['request_id']}")
    print(f"  Resolved by: {resolved_by}")
    if notes:
        print(f"  Notes: {notes}")
    if conditions:
        print(f"  Conditions: {conditions}")
    for k in ("snooze_until", "wait_until", "wait_indefinite"):
        if extra and k in extra:
            print(f"  {k}: {extra[k]}")

    return True


def approve_or_reject(project_dir: Path, stage_id: str, agent_id: str,
                      approve: bool, notes: str = "", resolved_by: str = "human"):
    """Approve or reject an approval request (back-compat wrapper)."""
    return resolve_approval(project_dir, stage_id, agent_id,
                            "approved" if approve else "rejected",
                            notes=notes, resolved_by=resolved_by)


def main():
    parser = argparse.ArgumentParser(description="Pipeline Approval CLI")
    parser.add_argument("--project", "-p", required=True, help="Project name")
    parser.add_argument("--stage", "-s", help="Stage ID")
    parser.add_argument("--agent", "-a", help="Agent ID")
    parser.add_argument("--approve", action="store_true", help="Approve the request")
    parser.add_argument("--reject", action="store_true", help="Reject the request")
    parser.add_argument("--changes", action="store_true",
                        help="Request changes (agent re-runs with --notes, bounded, then re-asks)")
    parser.add_argument("--regenerate", action="store_true",
                        help="Re-run the agent as-is (bounded), then re-ask")
    parser.add_argument("--skip", action="store_true", help="Skip the agent/stage and continue")
    parser.add_argument("--abort", action="store_true", help="Abort the whole pipeline")
    parser.add_argument("--conditions", default="",
                        help="Approve with conditions (implies approved_with_conditions)")
    parser.add_argument("--snooze", type=int, default=None,
                        help="Defer the decision by N minutes")
    parser.add_argument("--wait-minutes", type=int, default=None, dest="wait_minutes",
                        help="Wait further: extend the approval deadline by N minutes")
    parser.add_argument("--wait-indefinite", action="store_true", dest="wait_indefinite",
                        help="Wait indefinitely for the decision")
    parser.add_argument("--notes", "-n", default="", help="Notes for the decision")
    parser.add_argument("--list", "-l", action="store_true", help="List pending approvals")
    parser.add_argument("--status", action="store_true", help="Show status of a specific request")
    parser.add_argument("--products-dir", default="products", help="Products directory")
    
    args = parser.parse_args()
    
    try:
        project_dir = find_project_dir(args.project, args.products_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    
    if args.list:
        list_pending_approvals(project_dir)
        return 0
    
    if args.status:
        if not args.stage or not args.agent:
            print("Error: --status requires --stage and --agent")
            return 1
        get_approval_status(project_dir, args.stage, args.agent)
        return 0
    
    if not args.stage or not args.agent:
        print("Error: --stage and --agent are required")
        return 1
    
    actions = [name for name, on in (
        ("--approve", args.approve),
        ("--reject", args.reject),
        ("--changes", args.changes),
        ("--regenerate", args.regenerate),
        ("--skip", args.skip),
        ("--abort", args.abort),
        ("--conditions", bool(args.conditions)),
        ("--snooze", args.snooze is not None),
        ("--wait-minutes", args.wait_minutes is not None),
        ("--wait-indefinite", args.wait_indefinite),
    ) if on]

    status = None
    extra = {}
    if set(actions) == {"--approve", "--conditions"}:
        status = "approved_with_conditions"
    elif len(actions) == 1:
        only = actions[0]
        status = {
            "--approve": "approved",
            "--reject": "rejected",
            "--changes": "changes",
            "--regenerate": "regenerate",
            "--skip": "skip",
            "--abort": "abort",
            "--conditions": "approved_with_conditions",
            "--snooze": "snoozed",
            "--wait-minutes": "waiting",
            "--wait-indefinite": "waiting",
        }[only]
    else:
        print("Error: exactly one decision flag is required "
              "(--approve | --reject | --changes | --regenerate | --skip | --abort | "
              "--conditions | --snooze | --wait-minutes | --wait-indefinite)")
        return 1

    if status == "snoozed":
        extra["snooze_until"] = (datetime.now() + timedelta(minutes=args.snooze)).isoformat()
    elif status == "waiting":
        if args.wait_indefinite:
            extra["wait_indefinite"] = True
        else:
            extra["wait_until"] = (datetime.now() + timedelta(minutes=args.wait_minutes)).isoformat()

    success = resolve_approval(
        project_dir, args.stage, args.agent,
        status=status,
        notes=args.notes,
        conditions=args.conditions,
        extra=extra,
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
