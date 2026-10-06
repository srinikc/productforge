#!/usr/bin/env python3
"""`/pf` - the Product Forge command surface (thin client).

One umbrella over the canonical owners: product generation (delegates to ``scripts/pipeline.py``),
backlog grooming/analysis, scheduler eligibility/claim, worker registry, adapters, dispatch, dogfood,
validation, release, packaging and the final audit. It contains **no orchestration logic** - it calls the
same core/API the rest of PF uses (doc §26-28: TUI/CLI/UI are clients).

Usage:
  python scripts/pf.py <verb> [args] [--scope S] [--project P] [--json]
  python scripts/pf.py help [verb]                               # overview / per-verb usage details
  python scripts/pf.py product new "an idea" --tier cheap     # delegates to scripts/pipeline.py
  python scripts/pf.py backlog list
  python scripts/pf.py backlog groom <id> [--no-ai]
  python scripts/pf.py work --runtime command
  python scripts/pf.py scheduler eligible
  python scripts/pf.py worker register --runtime opencode --caps python,code
  python scripts/pf.py dispatch tick --force
  python scripts/pf.py status
"""
import json
import os
import subprocess
import sys

try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:
    import os as _pf_os
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, "core", "paths.py")):
            sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

ROOT = str(_PF_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

VERBS = ("product", "backlog", "work", "scheduler", "worker", "adapters",
         "dispatch", "dogfood", "validate", "release", "package", "audit", "status", "pidl")


def _flags(argv):
    """Split positional args and --flags/--scope/--project/--json."""
    pos, flags = [], {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                flags[key] = argv[i + 1]
                i += 2
            else:
                flags[key] = "1"
                i += 1
        else:
            pos.append(a)
            i += 1
    return pos, flags


def _emit(obj, as_json: bool):
    if as_json or not isinstance(obj, str):
        print(json.dumps(obj, indent=2, default=str) if isinstance(obj, (dict, list)) else obj)
    else:
        print(obj)


def _scope(flags):
    return flags.get("scope", "product_forge"), (flags.get("project") or None)


def cmd_product(argv):
    # thin delegate: product generation is the existing pipeline CLI
    return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "pipeline.py"), *argv], cwd=ROOT).returncode


def cmd_backlog(pos, flags):
    from core import backlog, grooming
    s, p = _scope(flags)
    sub = pos[0] if pos else "list"
    if sub == "list":
        return {"items": [{"id": i.get("id"), "status": i.get("status"), "title": i.get("title")}
                          for i in backlog.list_open(s, p)]}
    if sub in ("show", "get") and len(pos) > 1:
        return backlog.get_epic(s, p, pos[1]) or {"error": "not found"}
    if sub in ("groom", "analyze") and len(pos) > 1:
        mode = "deterministic" if flags.get("no-ai") else ""
        return grooming.groom(s, p, pos[1], mode=mode)
    if sub == "approve" and len(pos) > 1:
        return grooming.decide(s, p, pos[1], "APPROVE")
    return {"error": "usage: pf backlog list|show <id>|groom <id> [--no-ai]|approve <id>"}


def cmd_work(pos, flags):
    from core import work_pull
    s, p = _scope(flags)
    return work_pull.pull(s, p, worker_id=flags.get("worker", ""), runtime=flags.get("runtime", ""))


def cmd_scheduler(pos, flags):
    from core import scheduler
    s, p = _scope(flags)
    sub = pos[0] if pos else "status"
    if sub == "eligible":
        return scheduler.eligible_backlog(s, p)
    if sub == "next":
        return scheduler.next_eligible(s, p)
    if sub == "plan":
        return scheduler.plan(s, p)
    return {"eligible": scheduler.eligible_backlog(s, p)["eligible"],
            "report": scheduler.report(s, p)}


def cmd_worker(pos, flags):
    from core import worker_registry as wr
    s, p = _scope(flags)
    sub = pos[0] if pos else "list"
    if sub == "register":
        caps = [c for c in str(flags.get("caps", flags.get("capabilities", ""))).split(",") if c]
        return wr.register(s, p, runtime=flags.get("runtime", "opencode"), capabilities=caps,
                           role=flags.get("role", ""))
    if sub == "status" and len(pos) > 1:
        return wr.get(s, p, pos[1]) or {"error": "unknown worker"}
    if sub == "unregister" and len(pos) > 1:
        return wr.unregister(s, p, pos[1], revoke=bool(flags.get("revoke")))
    return {"workers": wr.list_workers(s, p), "enabled": wr.integration_enabled()}


def cmd_adapters(pos, flags):
    from core import worker_adapters as wa
    return {"contract": wa.contract(), "adapters": wa.list_adapters()}


def cmd_dispatch(pos, flags):
    from core import dispatcher
    s, p = _scope(flags)
    if (pos and pos[0] == "tick") or flags.get("tick"):
        return dispatcher.tick(s, p, force=bool(flags.get("force")))
    return dispatcher.status()


def cmd_dogfood(pos, flags):
    from core import dogfood
    s, p = _scope(flags)
    d = os.path.join(ROOT, "products", p) if p else ROOT
    return dogfood.run(p or s, d, dry=bool(flags.get("dry", "1")), scope=s, use_worktree=False)


def cmd_validate(pos, flags):
    from core import validation_engine as ve
    s, p = _scope(flags)
    prof = pos[0] if pos else "FEATURE_PR"
    d = os.path.join(ROOT, "products", p) if p else ROOT
    return ve.run(p or s, d, profile_name=prof.upper(), scope=s)


def cmd_release(pos, flags):
    from core import release
    s, p = _scope(flags)
    sub = pos[0] if pos else "readiness"
    return release.gate(s, p or "") if sub == "gate" else release.readiness(s, p or "")


def cmd_package(pos, flags):
    from core import packaging
    s, p = _scope(flags)
    edition = pos[0] if pos else "community"
    return packaging.build(s, p or "", edition=edition)


def cmd_audit(pos, flags):
    from core import audit
    return audit.summary()


def cmd_pidl(pos, flags):
    from core import pidl
    s, p = _scope(flags)
    sub = pos[0] if pos else "decisions"
    if sub in ("show", "get") and len(pos) > 1:
        return pidl.get(pos[1]) or {"error": "not found"}
    if sub == "candidates":
        return {"candidates": pidl.feedback_candidates(status=flags.get("status", "proposed"))}
    if sub == "policy":
        return pidl.approval_policy(action=flags.get("action", ""), area=flags.get("area", ""))
    if sub == "latest" and len(pos) > 1:
        return pidl.latest(pos[1]) or {"error": "no decision"}
    return {"decisions": pidl.history(scope=s if s != "product_forge" else "",
                                      project=p or "", item_id=flags.get("item", ""),
                                      limit=int(flags.get("limit", 20)))}


def cmd_status(pos, flags):
    from core import audit, dispatcher
    from core import worker_registry as wr
    s, p = _scope(flags)
    return {"production_ready": audit.summary().get("production_ready"),
            "worker_integration": wr.integration_enabled(),
            "workers": len(wr.list_workers(s, p)),
            "dispatch": dispatcher.status()}


# Help surface: (description, subcommands [(usage, help)], verb flags [(usage, help)])
# Global flags apply to every verb. Keep in sync with .opencode/command/pf.md verb map.
_GLOBAL_FLAGS = (
    ("--scope S", "store scope (default: product_forge)"),
    ("--project P", "project scope (routes to products/<P>/)"),
    ("--json", "JSON output (default for every verb)"),
)

_HELP = {
    "product": ("Product generation - delegates to scripts/pipeline.py (the agent runner).",
                [('new "<idea>" --tier <tier>', "start a new product from an idea; --tier picks the model tier"),
                 ("continue", "resume the current/last run (journal/checkpoint state)"),
                 ('fix "<desc>"', "run a fix pass with a fix brief")],
                (("--tier <tier>", "model tier (e.g. cheap, free-trial-fast)"),)),
    "backlog": ("Backlog SSOT (single writer: core/backlog.py).",
                [("list", "open backlog items (JSON: id/status/title)"),
                 ("show <id>", "full item record (e.g. BI-PF-0408)"),
                 ("groom <id> [--no-ai]", "analyze/groom one item; --no-ai = deterministic only"),
                 ("approve <id>", "approve a groomed item")],
                (("--no-ai", "groom deterministically (skip AI analysis)"),)),
    "work": ("Pull eligible work for a worker/runtime.",
             [],
             (("--worker W", "claim as worker W"), ("--runtime R", "filter by runtime R"))),
    "scheduler": ("Scheduler eligibility and planning.",
                  [("status", "current scheduler report (default)"),
                   ("eligible", "eligible backlog items"),
                   ("next", "next eligible item"),
                   ("plan", "execution plan")], ()),
    "worker": ("Worker registry (single writer: core/worker_registry.py).",
               [("register --runtime R --caps a,b", "register a worker; --role is optional"),
                ("list", "registered workers + integration flag (default)"),
                ("status <id>", "one worker's record"),
                ("unregister <id>", "remove a worker; --revoke revokes its lease")],
               (("--runtime R", "worker runtime (e.g. opencode, command)"),
                ("--caps a,b", "comma-separated capabilities"),
                ("--role", "worker role"), ("--revoke", "unregister: revoke lease"))),
    "adapters": ("List worker adapters and the adapter contract.", [], ()),
    "dispatch": ("Work dispatch loop.",
                 [("status", "dispatcher status (default)"),
                  ("tick [--force]", "run one dispatch tick; --force ignores gating")],
                 (("--force", "run the tick even if gating would skip it"),)),
    "dogfood": ("Run Product Forge's own dogfood validation.", [],
                (("--dry", "dry run (default on; pass without value to toggle)"),)),
    "validate": ("Validation profiles (single writer: core/validation_engine.py).",
                 [("<PROFILE>", "profile name, e.g. FEATURE_PR (default)")], ()),
    "release": ("Release gate.",
                [("readiness", "readiness report (default)"),
                 ("gate", "go/no-go gate verdict")], ()),
    "package": ("Build a distribution package for an edition.",
                [("<edition>", "edition to package (default: community)")], ()),
    "audit": ("Final audit summary (production readiness).", [], ()),
    "status": ("Compact status: workers + dispatch + readiness.", [], ()),
    "pidl": ("Product-Forge decision log (PIDL).",
             [("decisions", "decision history (default)"),
              ("show <id>", "one decision"), ("candidates", "feedback candidates"),
              ("policy", "approval policy"), ("latest <id>", "latest decision per key")],
             (("--item", "filter history by item id"), ("--limit N", "history limit (default 20)"),
              ("--status", "candidates: status filter (default proposed)"),
              ("--action", "policy: action to look up"), ("--area", "policy: area to look up"))),
}


def _help_overview():
    lines = [(__doc__ or "").strip().splitlines()[0], "",
             "GLOBAL FLAGS", ""]
    w = max(len(f) for f, _ in _GLOBAL_FLAGS)
    for f, d in _GLOBAL_FLAGS:
        lines.append(f"  {f:<{w}}  {d}")
    lines += ["", "VERBS   (details: /pf help <verb>)", ""]
    for v in VERBS:
        desc, subs, vflags = _HELP[v]
        usage = " | ".join(c for c, _ in subs)
        if not subs and vflags:
            usage = " ".join(f"[{f}]" for f, _ in vflags)
        line = f"  /pf {v}" + (f" {usage}" if usage else "")
        lines.append(f"  {v:<10}" + line.strip())
    lines += ["", "Examples:",
              "  python scripts/pf.py help backlog",
              "  python scripts/pf.py backlog list"]
    return "\n".join(lines)


def _help_verb(v):
    desc, subs, vflags = _HELP[v]
    usage = " | ".join(c for c, _ in subs)
    if not subs and vflags:
        usage = " ".join(f"[{f}]" for f, _ in vflags)
    lines = [f"{v} - {desc}", "", "USAGE", f"  /pf {v}" + (f" {usage}" if usage else "")]
    if subs:
        lines += ["", "SUBCOMMANDS"]
        w = max(len(c) for c, _ in subs)
        for c, d in subs:
            lines.append(f"  {c:<{w}}  {d}")
    flags = tuple(vflags) + _GLOBAL_FLAGS
    lines += ["", "FLAGS"]
    w = max(len(f) for f, _ in flags)
    for f, d in flags:
        lines.append(f"  {f:<{w}}  {d}")
    return "\n".join(lines)


def _help_cmd(rest):
    if not rest:
        print(_help_overview())
        return 0
    topic = rest[0]
    if topic not in _HELP:
        print(f"unknown help topic {topic!r}. verbs: {', '.join(VERBS)}")
        return 2
    print(_help_verb(topic))
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return _help_cmd([])
    if argv[0] in ("-h", "--help", "help"):
        return _help_cmd(argv[1:])
    verb, rest = argv[0], argv[1:]
    if verb not in VERBS:
        print(f"unknown verb {verb!r}. verbs: {', '.join(VERBS)}")
        return 2
    if verb == "product":
        return cmd_product(rest)
    pos, flags = _flags(rest)
    as_json = "json" in flags or True  # structured by default
    fn = {"backlog": cmd_backlog, "work": cmd_work, "scheduler": cmd_scheduler,
          "worker": cmd_worker, "adapters": cmd_adapters, "dispatch": cmd_dispatch,
          "dogfood": cmd_dogfood, "validate": cmd_validate, "release": cmd_release,
          "package": cmd_package, "audit": cmd_audit, "status": cmd_status, "pidl": cmd_pidl}[verb]
    try:
        res = fn(pos, flags)
    except Exception as e:
        print(f"[pf] {verb} error: {type(e).__name__}: {e}")
        return 1
    _emit(res, as_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
