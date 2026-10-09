#!/usr/bin/env python3
"""`/pf` - the Product Forge command surface (thin client).

One umbrella over the canonical owners: product generation (delegates to ``scripts/pipeline.py``),
backlog grooming/analysis, dogfood, validation, release, packaging and the final audit. It contains **no
orchestration logic** - it calls the same core/API the rest of PF uses (doc §26-28: TUI/CLI/UI are clients).

Worker/scheduler orchestration was **decoupled** into WorkerGrid (``/wg``, ``workergrid/wg.py``) - see ADR-0002.

Usage:
  python scripts/pf.py <verb> [args] [--scope S] [--project P] [--json]
  python scripts/pf.py help [verb]                               # overview / per-verb usage details
  python scripts/pf.py product new "an idea" --tier cheap     # delegates to scripts/pipeline.py
  python scripts/pf.py backlog list
  python scripts/pf.py backlog groom <id> [--no-ai]
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

VERBS = ("product", "backlog", "dogfood", "validate", "release", "package", "audit", "status", "pidl", "sync")


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


def _slugify(text: str, maxlen: int = 48) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return s[:maxlen].strip("-") or "product"


def cmd_product(argv):
    """Thin delegate: product generation runs through the canonical runner ``scripts/run_pipeline.py``.

    Contracts:
      /pf product new "<idea>" [--tier T]       -> run_pipeline.py new <slug> --idea "<idea>" [--tier T]
      /pf product new <project> --idea "<i>"    -> passthrough
      /pf product continue <project> [...]      -> passthrough
      /pf product enhance <project> --goal "g"  -> passthrough
      /pf product fix <project> "<desc>"        -> run_pipeline.py enhance <project> --goal "<desc>"
    """
    runner = os.path.join(ROOT, "scripts", "run_pipeline.py")
    argv = list(argv or [])
    if not argv:
        return subprocess.run([sys.executable, runner, "--help"], cwd=ROOT).returncode
    mode = argv[0].lower()
    rest = argv[1:]

    if mode == "new":
        flags: dict = {}
        pos: list = []
        i = 0
        while i < len(rest):
            a = rest[i]
            if a.startswith("-"):
                if i + 1 < len(rest) and not rest[i + 1].startswith("-"):
                    flags[a] = rest[i + 1]
                    i += 2
                else:
                    flags[a] = ""
                    i += 1
            else:
                pos.append(a)
                i += 1
        idea = flags.get("--idea", "")
        project = flags.get("--project", "")
        if idea:
            project = project or (pos[0] if pos else _slugify(idea))
        elif len(pos) == 1:
            idea = pos[0]
            project = project or _slugify(idea)
        elif len(pos) >= 2:
            project = project or pos[0]
        else:
            project = project or _slugify("product")
        extra: list = []
        for k, v in flags.items():
            if k in ("--idea", "--project"):
                continue
            extra.append(k)
            if v:
                extra.append(v)
        run_args = ["new", project] + (["--idea", idea] if idea else []) + extra
    elif mode == "fix" and rest:
        project = "" if rest[0].startswith("-") else rest[0]
        desc = rest[1] if project and len(rest) > 1 else ""
        run_args = ["enhance"] + ([project] if project else []) + ["--goal", desc]
    else:
        run_args = list(argv)
    return subprocess.run([sys.executable, runner, *run_args], cwd=ROOT).returncode


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
        return grooming.groom(s, p, pos[1], mode=mode, force=bool(flags.get("force")))
    if sub == "groom-all":
        mode = "deterministic" if flags.get("no-ai") else ""
        return grooming.groom_all(s, p, mode=mode, batch=int(flags.get("batch") or 0),
                                  limit=int(flags.get("limit") or 0), force=bool(flags.get("force")),
                                  dry=bool(flags.get("dry")), jobs=int(flags.get("jobs") or 0))
    if sub == "review":
        return grooming.review(s, p)
    if sub == "approve" and len(pos) > 1:
        return grooming.decide(s, p, pos[1], "APPROVE")
    if sub == "approve-all":
        ids = [x.strip() for x in str(flags.get("ids") or "").split(",") if x.strip()]
        return grooming.decide_all(s, p, "APPROVE", ids=(ids or None), force=bool(flags.get("force")),
                                   dry=bool(flags.get("dry")))
    return {"error": "usage: pf backlog list|show <id>|groom <id> [--no-ai]|groom-all "
                     "[--no-ai] [--batch N] [--limit N] [--force] [--dry]|review|approve <id>|"
                     "approve-all [--ids a,b] [--force] [--dry]"}


# worker/scheduler/work/adapters/dispatch verbs MOVED to WorkerGrid (`/wg`, workergrid/wg.py) - decoupled.


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
    from core import audit
    s, p = _scope(flags)
    return {"production_ready": audit.summary().get("production_ready")}


def cmd_sync(pos, flags):
    """Git sync (Stage 2a): fetch the remote and push the integration branch."""
    from core.vcs import VCSManager
    return VCSManager(ROOT).sync(push=True)


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
                 ("groom <id> [--no-ai] [--force]",
                  "groom one item: analysis + full context + priority + deps (gap-fill; --force overwrites)"),
                 ("groom-all [--no-ai] [--batch N] [--jobs N] [--limit N] [--force] [--dry]",
                  "groom all open items incl. in-progress; batched AI (3/pass, N concurrent)"),
                 ("review", "groomed-but-undecided items: status/confidence/flags/context_review"),
                 ("approve <id>", "approve a groomed item"),
                 ("approve-all [--ids a,b] [--force] [--dry]",
                  "approve CLEAN groomed items; --force also approves flagged ones")],
                (("--no-ai", "groom deterministically (skip AI analysis)"),
                 ("--batch N", "items per AI call (default 3)"),
                 ("--jobs N", "concurrent AI batches (default 4)"),
                 ("--limit N", "process at most N items this run"),
                 ("--force", "groom/approve even if already groomed or flagged"),
                 ("--dry", "preview what would change (no writes)"),
                 ("--ids a,b", "approve-all: restrict to these item ids"))),
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
    "status": ("Compact status: production readiness.", [], ()),
    "sync": ("Git sync (Stage 2a): fetch the remote + push the integration branch (develop).", [], ()),
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
    fn = {"backlog": cmd_backlog, "dogfood": cmd_dogfood, "validate": cmd_validate,
          "release": cmd_release, "package": cmd_package, "audit": cmd_audit,
          "status": cmd_status, "pidl": cmd_pidl, "sync": cmd_sync}[verb]
    try:
        res = fn(pos, flags)
    except Exception as e:
        print(f"[pf] {verb} error: {type(e).__name__}: {e}")
        return 1
    _emit(res, as_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
