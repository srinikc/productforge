#!/usr/bin/env python3
"""
Portfolio CLI (GLOBAL tier) — manage/supervise multiple project pipelines.

  python scripts/run_portfolio.py add <project> [--idea "..."] [--tier <tier>] [--priority N]
  python scripts/run_portfolio.py list
  python scripts/run_portfolio.py status
  python scripts/run_portfolio.py start [--max-concurrent N] [--no-watch] [--dry]
  python scripts/run_portfolio.py pause|resume|stop <project>|--all

Adding from any session attaches to a running supervisor via the shared registry
(products/portfolio-registry.json): the supervisor watches it and launches new projects.
"""
try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import argparse
import os
import sys

sys.path.insert(0, str(_PF_ROOT))
from core import portfolio as pf


def main():
    ap = argparse.ArgumentParser(description="Product Forge — Portfolio Manager")
    sub = ap.add_subparsers(dest="cmd")

    a = sub.add_parser("add")
    a.add_argument("project")
    a.add_argument("--idea", default="")
    a.add_argument("--tier", default="")
    a.add_argument("--priority", type=int, default=100)
    a.add_argument("--force", action="store_true", help="ignore max_created_projects")

    sub.add_parser("list")
    sub.add_parser("status")

    s = sub.add_parser("start")
    s.add_argument("--max-concurrent", type=int, default=1)
    s.add_argument("--no-watch", action="store_true")
    s.add_argument("--dry", action="store_true")
    s.add_argument("--mode", default="process", choices=["process", "queue"],
                   help="A=process (supervisor+children) | B=queue (workers)")
    s.add_argument("--workers", type=int, default=2, help="worker count for --mode queue")

    w = sub.add_parser("worker")
    w.add_argument("--once", action="store_true", help="claim and run a single job")
    w.add_argument("--dry", action="store_true", help="claim without running")
    w.add_argument("--max-jobs", type=int, default=0)

    sub.add_parser("queue")
    sub.add_parser("capacity")

    for name in ("pause", "resume", "stop"):
        p = sub.add_parser(name)
        p.add_argument("project", nargs="?")
        p.add_argument("--all", action="store_true")

    args = ap.parse_args()
    cmd = args.cmd or "status"

    if cmd == "add":
        try:
            from core.capacity import can_add
            c = can_add()
            if not c["ok"] and not args.force:
                print(f"[capacity] cannot add: {c['reason']} (use --force to override)")
                return
        except Exception:
            pass
        pf.register(args.project, args.idea, args.tier, args.priority)
        print(f"registered '{args.project}' (tier={args.tier or 'default'}) "
              f"| supervisor_running={pf.supervisor_running()}")
        if pf.supervisor_running():
            print("  -> running supervisor will pick it up automatically.")
        else:
            print("  -> no supervisor running; run `start` (or it will be picked up on next start).")
        return

    if cmd == "list":
        for p, d in sorted(pf.projects().items()):
            print(f"  {p:<20} tier={d.get('tier',''):<16} priority={d.get('priority','')} "
                  f"status={d.get('status','')}")
        return

    if cmd == "status":
        print(f"supervisor_running={pf.supervisor_running()}")
        print(f"  {'project':<20} {'status':<14} {'pid':<8} {'stage':<5} tier")
        for r in pf.status_rows():
            print(f"  {r['project']:<20} {r['status']:<14} {r['pid']!s:<8} "
                  f"{r['stage']:<5} {r['tier']}")
        return

    if cmd == "start":
        if pf.supervisor_running():
            print("A supervisor is already running — new `add`s will attach to it.")
            return
        if args.mode == "queue":
            # Substrate B: spawn N workers over the sqlite queue.
            import subprocess, sys as _s
            procs = []
            pf._wj(pf.LOCK, {"pid": os.getpid(), "mode": "queue"})
            print(f"Queue workers: {args.workers} (substrate B)")
            for i in range(args.workers):
                procs.append(subprocess.Popen(
                    [_s.executable, "-u", "scripts/run_portfolio.py", "worker"],
                    cwd=str(_PF_ROOT)))
            try:
                for pr in procs:
                    pr.wait()
            finally:
                pf._release_supervisor_lock()
            return
        rc = pf.run_supervisor(max_concurrent=args.max_concurrent,
                               watch=not args.no_watch, dry=args.dry)
        sys.exit(rc)

    if cmd == "worker":
        sys.exit(pf.worker_loop(once=args.once, dry=args.dry, max_jobs=args.max_jobs))

    if cmd == "queue":
        from core import job_manager as jm
        st = jm.status()
        print(f"  limits={st.get('limits')} running={st.get('running_count')} "
              f"by_state={st.get('by_state')}")
        print(f"  {'project':<20} {'state':<12} {'prio':<5} {'source':<10} {'run_id':<20} "
              f"{'item':<10} waiting")
        for j in st.get("jobs", []):
            why = ""
            if j.get("state") == "scheduled" and j.get("not_before"):
                why = f"until {j['not_before']}"
            elif j.get("state") == "paused" and j.get("resume_after"):
                why = f"on {j['resume_after']}"
            print(f"  {j['project']:<20} {j['state']:<12} {str(j.get('priority')):<5} "
                  f"{str(j.get('source') or ''):<10} {str(j.get('run_id') or ''):<20} "
                  f"{str(j.get('item_ids') or ''):<10} {why}")
        return

    if cmd == "capacity":
        from core.capacity import status
        s = status()
        print(f"limits            : {s['limits']}")
        print(f"running projects  : {s['running_count']} {s['running_projects']}")
        print(f"created projects  : {s['created_count']}")
        print(f"supervisors       : {len(s['supervisors'])} {s['supervisors']}")
        print(f"provider limits   : {s['provider_limits']}")
        print(f"global budget     : {s['global_budget']}")
        return

    if cmd in ("pause", "resume", "stop"):
        targets = list(pf.projects()) if args.all else [args.project]
        for p in [t for t in targets if t]:
            pf.control(p, cmd)
            print(f"  {cmd} -> {p}")
        return


if __name__ == "__main__":
    main()
