#!/usr/bin/env python3
"""
Generic pipeline runner — the framework-agnostic entry point.

Runs the Python PipelineExecutor for a project (optionally seeding the idea).
Used by the /pipeline slash command and by the API/dashboard.
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
import json
import os
import sys

ROOT = str(_PF_ROOT)
sys.path.insert(0, ROOT)

from core.pipeline_executor import PipelineExecutor  # noqa: E402


def _ask(prompt: str, default=None, *, project_dir=None, products_dir="products"):
    """Interactive prompt.

    Delegates to ``core.interactive``: real TTY -> ``input()``; when the file bridge
    is on (``--interactive`` / ``PIPELINE_INTERACTIVE=1``) -> relayed through
    ``prompts.json``; otherwise -> ``default`` (never crashes, never hangs).
    """
    try:
        from core import interactive
        return interactive.ask(prompt, default, project_dir=project_dir,
                               products_dir=products_dir)
    except Exception:
        return default


class _Tee:
    """Mirror stdout/stderr to a file so /pipeline (agent) and the dashboard can stream it."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            try:
                st.write(s)
            except Exception:
                pass

    def flush(self):
        for st in self.streams:
            try:
                st.flush()
            except Exception:
                pass


def _setup_run_log(project_dir):
    """Tee stdout/stderr -> products/<project>/pipeline-run.log (line-buffered)."""
    try:
        os.makedirs(project_dir, exist_ok=True)
        path = os.path.join(project_dir, "pipeline-run.log")
        # line-buffered (buffering=1) so the log streams live instead of only at exit
        f = open(path, "a", encoding="utf-8", errors="replace", buffering=1)
        sys.stdout = _Tee(sys.__stdout__, f)
        sys.stderr = _Tee(sys.__stderr__, f)
        print(f"[logging] {path}")
        return f
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="Run the generic Product Forge pipeline")
    ap.add_argument("tokens", nargs="*",
                    help="optional: 'new' | 'continue' | <project name>")
    ap.add_argument("--project", default=None)
    ap.add_argument("--run-id", default=None, help="Use this run id (else one is minted)")
    ap.add_argument("--amend", action="store_true",
                    help="Incremental change: agents amend their existing artifacts (no rebuild)")
    ap.add_argument("--idea", default=None, help="Product brief fed to Stage 0")
    ap.add_argument("--pipeline", default="pipeline-definition.json")
    ap.add_argument("--products-dir", default="products")
    ap.add_argument("--tier", default=None,
                    help="Model tier profile, e.g. 'actual' or 'free-trial' "
                         "(overrides project.json model_tier via PIPELINE_MODEL_TIER)")
    ap.add_argument("--tier-list", action="store_true", help="List available tier profiles and exit")
    ap.add_argument("--tier-info", default=None, help="Show details for one tier profile and exit")
    ap.add_argument("--agent", default=None,
                    help="Selective rerun: comma-separated agents (their stages + downstream rerun)")
    ap.add_argument("--only-stage", default=None, help="Selective rerun: comma-separated stage ids")
    ap.add_argument("--phase", default=None,
                    help="Selective rerun of a whole phase (name/id, e.g. 'P2' or 'Business'); "
                         "expands to that phase's stage ids from pipeline-definition.json")
    ap.add_argument("--from-stage", default=None, help="Rerun from this stage onward")
    ap.add_argument("--only", action="store_true",
                    help="Run ONLY the selected stages/agents (leave dependents pending)")
    ap.add_argument("--control", default=None, choices=["stop", "exit", "pause", "resume"],
                    help="Signal a running pipeline (writes products/<project>/control.json) and exit")
    ap.add_argument("--step", action="store_true",
                    help="Pause for confirmation after each agent (HIL step mode)")
    ap.add_argument("--interactive", action="store_true",
                    help="Relay prompts through products/<project>/interactive/prompts.json "
                         "(for TTY-less harnesses); implies --step. Answer with: "
                         "python -m core.interactive --project <p> --answer <id> \"<value>\"")
    ap.add_argument("--auto", action="store_true",
                    help="Auto mode: Human-like agents make HIL decisions (sets auto_mode+auto_approve)")
    ap.add_argument("--goal", default="",
                    help="Enhance mode: the goal (e.g. 'make it enterprise/production ready')")
    ap.add_argument("--no-run", action="store_true", help="Enhance mode: plan only, do not run")
    ap.add_argument("--no-cache", action="store_true",
                    help="Disable ALL caching (output + input): full recompute, no cache reads/writes")
    ap.add_argument("--fresh", action="store_true",
                    help="Treat as a FRESH run: reset prompt ids to P1 (previous archived)")
    args = ap.parse_args()

    # Layer 3: hard cache bypass. Propagates to the executor in-process and to any
    # child process via the environment (PIPELINE_NO_CACHE=1).
    if getattr(args, "no_cache", False):
        os.environ["PIPELINE_NO_CACHE"] = "1"

    # TTY-less interactive bridge: enable before any prompt is asked.
    # `--interactive` implies --step; set PIPELINE_STEP=0 to keep the bridge but
    # pause only at gates (not after every agent).
    if getattr(args, "interactive", False):
        os.environ["PIPELINE_INTERACTIVE"] = "1"
        os.environ.setdefault("PIPELINE_STEP", "1")

    # ── Resolve project (and new vs continue) — interactive when nothing given ──
    import json as _json_mod
    toks = [t for t in getattr(args, "tokens", []) if t]
    mode = None
    project = args.project
    if toks and toks[0].lower() in ("new", "continue", "enhance"):
        mode = toks[0].lower()
        if len(toks) > 1 and not project:
            project = toks[1]
    elif toks and not project:
        project = toks[0]

    def _existing():
        d = args.products_dir
        if not os.path.isdir(d):
            return []
        return sorted(x for x in os.listdir(d)
                      if os.path.isdir(os.path.join(d, x)) and not x.startswith(".")
                      and os.path.exists(os.path.join(d, x, "project.json")))

    if not project:
        if not sys.stdin.isatty() and os.environ.get("PIPELINE_INTERACTIVE") != "1":
            print("No project given.\n"
                  "  python scripts/run_pipeline.py <project> [--tier <tier>] [--idea \"...\"]\n"
                  "  python scripts/run_pipeline.py new <project>\n"
                  "  python scripts/run_pipeline.py continue <project>\n"
                  "NOTE: stdin is not a TTY here -> interactive prompts are disabled; pass flags.\n"
                  "      Run in your own terminal for the interactive flow.")
            sys.exit(2)
        ex = _existing()
        if ex:
            print("Existing projects: " + ", ".join(ex))
        project = (_ask("Project name (new or existing, blank to cancel): ", "",
                        products_dir=args.products_dir) or "").strip()
        if not project:
            print("Cancelled.")
            sys.exit(0)
        mode = mode or ("new" if project not in ex else "continue")

    args.project = project
    pdir = os.path.join(args.products_dir, args.project)
    os.makedirs(pdir, exist_ok=True)
    cfg_path = os.path.join(pdir, "project.json")
    _cfg = {}
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                _cfg = _json_mod.load(f) or {}
        except Exception:
            _cfg = {}
    is_new = (mode == "new") or (not _cfg)
    if not cfg_path and not mode:
        mode = "new"
    _interactive = (sys.stdin.isatty() or os.environ.get("PIPELINE_INTERACTIVE") == "1")
    _from0 = str(getattr(args, "from_stage", "") or "").strip() == "0"
    _phase0 = bool(getattr(args, "phase", None)) and (
        "p1" in str(args.phase).lower() or "ideation" in str(args.phase).lower())
    # NOTE: the brief is shown AFTER logging starts (below) so it lands in the run log.

    # Auto mode: Human-like agents make HIL decisions (no waiting for a person).
    if getattr(args, "auto", False):
        _cfg["auto_mode"] = True
        _cfg["auto_approve"] = True
        _cfg.setdefault("mode", "auto")
        try:
            from core.project_store import update as _ps_update
            _ps_update(args.project, args.products_dir,
                       auto_mode=True, auto_approve=True, mode=_cfg.get("mode", "auto"))
        except Exception:
            with open(cfg_path, "w", encoding="utf-8") as f:
                _json_mod.dump(_cfg, f, indent=2, ensure_ascii=False)
        print("[auto] enabled: Human-like agents will make HIL decisions.")

    # Enhance mode: analyze existing artifacts -> plan -> (optionally) rerun E2E.
    if mode == "enhance":
        goal = args.goal
        if not goal:
            goal = (_ask("Enhancement goal (e.g. 'make it enterprise/production ready'): ", "",
                         project_dir=pdir, products_dir=args.products_dir)
                    or "production/enterprise ready")
        from core.enhance import enhance
        rc = enhance(args.project, goal, accept=not args.no_run, products_dir=args.products_dir,
                     auto=args.auto)
        sys.exit(rc or 0)

    # Cross-process control (exit/stop/pause/resume) — no run.
    if args.control:
        import json as _json
        from datetime import datetime as _dt
        pdir = os.path.join(args.products_dir, args.project)
        os.makedirs(pdir, exist_ok=True)
        action = "stop" if args.control == "exit" else args.control
        with open(os.path.join(pdir, "control.json"), "w", encoding="utf-8") as f:
            _json.dump({"action": action, "updated_at": _dt.now().isoformat()}, f)
        print(f"[control] {action} written for project '{args.project}'")
        sys.exit(0)

    if args.step:
        os.environ["PIPELINE_STEP"] = "1"

    # Tier discovery (no run)
    if args.tier_list or args.tier_info:
        from core.orchestrator.model_router import describe_tiers, load_tier_config_file
        info = describe_tiers(args.products_dir, os.path.join(args.products_dir, args.project))
        if args.tier_info:
            prof = info["profiles"].get(args.tier_info)
            if not prof:
                print(f"Unknown tier '{args.tier_info}'. Available: {', '.join(info['configured_profiles'])}")
                sys.exit(1)
            cfg = load_tier_config_file(args.products_dir, os.path.join(args.products_dir, args.project))
            agents = (cfg.get("profiles", {}).get(args.tier_info, {}) or {}).get("agents", {}) or {}
            print(f"Tier: {args.tier_info}")
            print(f"  description : {prof['description']}")
            print(f"  provider    : {prof['provider']}")
            print(f"  default     : {prof['default_model']}")
            print(f"  endpoint    : {prof['api_endpoint']}")
            print(f"  agents      : {prof['agents_mapped']} mapped, {prof['models']} models catalogued")
            print("  per-agent   :")
            for a, v in sorted(agents.items()):
                print(f"    {a:<22} {v.get('model')}  (fallbacks: {', '.join(v.get('fallback_models', []))})")
            sys.exit(0)
        print(f"Active tier: {info['active_tier']}")
        print(f"{'tier':<16} {'provider':<14} {'agents':<7} default_model")
        print("-" * 70)
        for name, prof in info["profiles"].items():
            star = "*" if name == info["active_tier"] else " "
            print(f"{star}{name:<15} {prof['provider']:<14} {prof['agents_mapped']:<7} {prof['default_model']}")
        sys.exit(0)

    pdir = os.path.join(args.products_dir, args.project)
    os.makedirs(pdir, exist_ok=True)
    cfg_path = os.path.join(pdir, "project.json")
    cfg = {}
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}

    # Tier resolution: --tier > project.json:model_tier > interactive (TTY/bridge) > active.
    if not args.tier and not cfg.get("model_tier") and (
            sys.stdin.isatty() or os.environ.get("PIPELINE_INTERACTIVE") == "1"):
        try:
            from core.orchestrator.model_router import describe_tiers
            info = describe_tiers(args.products_dir, pdir)
            names = list(info["profiles"].keys())
            print("\nSelect model tier for this run:")
            for i, n in enumerate(names, 1):
                pr = info["profiles"][n]
                print(f"  {i}) {n:<16} {pr['provider']:<12} {pr['agents_mapped']:>2} agents  "
                      f"default={pr['default_model']}")
            prompt = f"Enter number or name [default '{info['active_tier']}']: "
            try:
                choice = (_ask(prompt, "", project_dir=pdir,
                               products_dir=args.products_dir) or "").strip()
            except EOFError:
                choice = ""
            if choice.isdigit() and 1 <= int(choice) <= len(names):
                args.tier = names[int(choice) - 1]
            elif choice in info["profiles"]:
                args.tier = choice
        except Exception as e:
            print(f"(tier prompt skipped: {e})")

    if args.tier:
        os.environ["PIPELINE_MODEL_TIER"] = args.tier
        cfg["model_tier"] = args.tier

    if args.idea:
        cfg["idea"] = args.idea
    cfg.setdefault("name", args.project)
    try:
        from core.project_store import save as _ps_save
        _ps_save(args.project, cfg, args.products_dir)
    except Exception:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

    executor = PipelineExecutor(products_dir=args.products_dir, project=args.project)
    # Incremental/amend mode: agents update existing artifacts instead of rebuilding.
    if getattr(args, "amend", False):
        executor.amend_mode = True
        os.environ["PIPELINE_AMEND"] = "1"
        print("[mode] AMEND: agents will update existing artifacts incrementally.")
    # Capacity preflight (substrate A/B): warn if no free slot.
    try:
        from core.capacity import can_start
        cap = can_start(args.project)
        if not cap["ok"]:
            print(f"[capacity] WARNING: {cap['reason']} — consider the portfolio "
                  f"manager (python scripts/run_portfolio.py) to queue/schedule.")
        else:
            print(f"[capacity] ok ({cap['running']}/{cap['max_parallel']} parallel slots used)")
    except Exception:
        pass
    _run_log = _setup_run_log(os.path.join(args.products_dir, args.project))
    # Prompt numbering: FRESH run (new / from-stage 0 / --fresh) -> reset to P1.
    # RESUME (pause/failure/stop, or continue mid-stage) -> KEEP numbering (e.g. from P20).
    _fresh = (mode == "new") or (str(getattr(args, "from_stage", "") or "") == "0") \
        or bool(getattr(args, "fresh", False))
    if _fresh:
        try:
            from core.interactive import reset_for_new_run as _resetp
            _resetp(os.path.join(args.products_dir, args.project), args.products_dir)
            print("[prompts] FRESH run - prompt ids reset to P1 (previous archived)")
        except Exception as _pe:
            print(f"[prompts] reset skipped: {_pe}")
    else:
        print("[prompts] RESUME - prompt ids continue from where they left off")
    # GENERAL rerun review: on ANY restart/rerun (continue / from-stage / only-stage /
    # agent / phase) show what exists (brief + artifacts) + recommendations, then
    # continue. Set PIPELINE_ASK_RERUN=1 to also ask continue/accept-recommendations/reject.
    try:
        from core import rerun_review as _rr
        _is_rerun = bool(mode == "continue" or getattr(args, "from_stage", None)
                         or getattr(args, "phase", None) or getattr(args, "only_stage", None)
                         or getattr(args, "agent", None)) and not getattr(args, "idea", None)
        if _is_rerun:
            import os as _os
            _pj = _os.path.join(args.products_dir, args.project)
            _scope = {"from_stage": getattr(args, "from_stage", None),
                      "only_stages": [s for s in (getattr(args, "only_stage", None) or "").split(",") if s],
                      "agents": [a for a in (getattr(args, "agent", None) or "").split(",") if a],
                      "phase": getattr(args, "phase", None)}
            _rv = _rr.build(_pj, args.project, _scope)
            print(_rr.present(_rv))
            _ask_run = (sys.stdin.isatty() or os.environ.get("PIPELINE_INTERACTIVE") == "1") and \
                str(os.getenv("PIPELINE_ASK_RERUN", "0")).lower() in ("1", "true", "yes")
            if _ask_run:
                from core.interactive import ask as _iask
                _ans = (_iask("Proceed with the rerun? [continue/accept-recommendations/reject] "
                              "(enter=continue): ", "continue", project_dir=_pj,
                              products_dir=args.products_dir) or "continue").strip().lower()
                if _ans not in ("continue", "accept-recommendations", "reject"):
                    _ans = "continue"
                _rr.decide(_pj, _ans)
                if _ans == "reject":
                    print("Rerun rejected by operator - exiting.")
                    return
            else:
                _rr.decide(_pj, "continue")
    except Exception as _rre:
        print(f"[rerun-review] skipped: {_rre}")
    try:
        from core.banner import print_banner
        _tier = args.tier or os.environ.get("PIPELINE_MODEL_TIER", "")
        print_banner(f"project={args.project} | tier={_tier or 'active'} | "
                     f"mode={'new' if mode == 'new' else 'run'}")
    except Exception:
        pass
    if not executor.load_pipeline(args.pipeline):
        print("Failed to load pipeline")
        sys.exit(1)

    # Selective rerun: reset target stages + stale their downstream.
    selective = bool(args.agent or args.only_stage or args.from_stage or args.phase)
    if selective:
        only = [s for s in (args.only_stage or "").split(",") if s]
        # --phase <name/id>: expand to that phase's stage ids (metadata: stage.phase).
        if args.phase:
            try:
                import json as _json
                _term = str(args.phase).strip().lower()
                _stages = (_json.load(open(args.pipeline, encoding="utf-8-sig")).get("stages") or {})
                _ph_stages = [sid for sid, st in _stages.items()
                              if _term and _term in (str(st.get("phase", "")).lower())]
                if _ph_stages:
                    only = sorted(set(only) | set(_ph_stages))
                    print(f"  [PHASE] '{args.phase}' -> stages {sorted(_ph_stages)}")
                    args.only = True  # a phase run is self-contained
                else:
                    print(f"  [PHASE] no stages matched phase '{args.phase}'")
            except Exception as _pe:
                print(f"  [PHASE] could not resolve phase: {_pe}")
        ags = [a for a in (args.agent or "").split(",") if a]
        plan = executor.invalidate_for_rerun(only_stages=only,
                                             from_stage=args.from_stage, agents=ags,
                                             run_only=args.only)
        print(f"Rerun plan: rerun={plan['rerun']} invalidated={plan['invalidated']} "
              f"agents={plan.get('agents')}")
        if args.only:
            print(f"Run-only scope: stages={plan['rerun']} agents={plan.get('agents')} "
                  f"(dependents stay pending)")
    else:
        # A normal/continue run is unrestricted: drop any leftover selective scope.
        executor._clear_run_scope()

    # Guarded run entry (ONE place): stop any OTHER instance, acquire the lock with a
    # run id, back-fill/annotate run linkage, and reconcile already-approved stages so
    # resume skips them. User data is never cleared.
    from core import run_entry
    try:
        _run_id = getattr(args, "run_id", None) or ""
        if not _run_id:
            _run_id = executor.execution.pipeline_id or ""
    except Exception:
        _run_id = ""
    beg = run_entry.begin_run(args.project, args.products_dir, run_id=_run_id)
    if not beg.get("ok"):
        print(f"Project '{args.project}' could not start: {beg.get('reason')}")
        sys.exit(2)
    lock_holder = beg.get("lock_holder", f"run-{os.getpid()}")
    if beg.get("marked_completed"):
        print(f"  [Resume] reconciled already-approved stages: {beg['marked_completed']}")
    if beg.get("backfilled"):
        print(f"  [RunLink] back-filled approvals: {beg['backfilled']}")

    # The executor must use the SAME run id as the lock/registry.
    try:
        if executor.execution and beg.get("run_id"):
            executor.execution.pipeline_id = beg["run_id"]
    except Exception:
        pass

    try:
        ok = executor.execute_pipeline()
    finally:
        # Selective scope is one-shot; never let it leak into a later run.
        try:
            executor._clear_run_scope()
        except Exception:
            pass
        # If the job was asked to pause, mark it paused (parked at a safe checkpoint)
        # so the queue can give the slot to a priority job; otherwise finish it.
        _paused = False
        try:
            from core import job_manager as _jm
            _st = _jm.status()
            _row = next((j for j in _st.get("jobs", []) if j.get("project") == args.project), None)
            if _row and _row.get("state") == "pause_pending":
                _jm.mark_paused(args.project)
                _paused = True
                print(f"  [job] {args.project}: PAUSED at checkpoint (resumable)")
        except Exception:
            pass
        if not _paused:
            try:
                from core import job_manager as _jm
                _jm.finish(args.project, 0 if ok else 1)
            except Exception:
                pass
        run_entry.end_run(args.project, args.products_dir, lock_holder)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
