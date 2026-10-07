#!/usr/bin/env python3
"""WorkerGrid CLI — the `/wg` command surface.

WorkerGrid is a **producer-agnostic execution plane**: it reads *work* from a producer's API (Product Forge by
default), assigns it to registered workers, and writes execution status back. It does **not** create backlog,
groom, or generate products — the producer owns those.

Verbs:
  wg register --runtime opencode [--caps a,b] [--worker-id X]   register a worker (local registry)
  wg list | wg status [<worker_id>] | wg unregister <worker_id>
  wg work [--worker X] [--runtime R] [--scope S] [--project P]  pull the next eligible item + lease it
  wg schedule eligible|next|status [--scope S] [--project P]    query the producer's eligibility
  wg adapters                                                   list runtimes
  wg dispatch [--force]                                         assign eligible work to ONLINE workers
  wg instruct [text] [--show]                                   view/edit the shared worker instructions
  wg config                                                     show resolved config + paths

Storage: workergrid/state/{workers,leases}.json. Instructions: workergrid/instructions.md (edit any time).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _cfg  # noqa: E402
import client  # noqa: E402

RUNTIMES = ("opencode", "claude-code", "remote", "command", "native")


def _workers():
    return _cfg.read_json("workers.json", {"workers": {}})


def _save_workers(d):
    _cfg.write_json("workers.json", d)


def _leases():
    return _cfg.read_json("leases.json", {"leases": {}})


def _save_leases(d):
    _cfg.write_json("leases.json", d)


def _flags(argv):
    pos, flags = [], {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            k = a[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                flags[k] = argv[i + 1]; i += 2
            else:
                flags[k] = "1"; i += 1
        else:
            pos.append(a); i += 1
    return pos, flags


def _emit(obj):
    print(json.dumps(obj, indent=2, default=str) if isinstance(obj, (dict, list)) else obj)


def cmd_register(pos, flags):
    d = _workers()
    wid = flags.get("worker-id") or f"WRK-{flags.get('runtime', _cfg.load().get('default_runtime', 'opencode'))}-{int(time.time()) % 100000000}"
    caps = [c for c in str(flags.get("caps", "")).split(",") if c]
    d["workers"][wid] = {"worker_id": wid, "runtime": flags.get("runtime", _cfg.load().get("default_runtime", "opencode")),
                         "capabilities": caps, "status": "ONLINE", "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _save_workers(d)
    return {"registered": True, "worker_id": wid, "runtime": d["workers"][wid]["runtime"], "capabilities": caps}


def cmd_list(pos, flags):
    d = _workers()
    return {"workers": list(d["workers"].values()), "count": len(d["workers"])}


def cmd_status(pos, flags):
    d = _workers()
    if pos:
        w = d["workers"].get(pos[0])
        return w or {"error": "unknown worker"}
    leases = _leases()["leases"]
    return {"workers": len(d["workers"]), "leases": len(leases), "producer": client._base()}


def cmd_unregister(pos, flags):
    if not pos:
        return {"error": "usage: wg unregister <worker_id>"}
    d = _workers()
    removed = d["workers"].pop(pos[0], None)
    _save_workers(d)
    return {"removed": bool(removed), "worker_id": pos[0]}


def _ensure_worker(flags):
    wid = flags.get("worker", "")
    if wid:
        return wid, _workers()["workers"].get(wid, {})
    rt = flags.get("runtime", _cfg.load().get("default_runtime", "opencode"))
    return cmd_register([], {"runtime": rt})["worker_id"], {"runtime": rt}


def cmd_work(pos, flags):
    scope = flags.get("scope", "product_forge")
    project = flags.get("project", "")
    wid, w = _ensure_worker(flags)
    r = client.next_item(scope, project)
    if not r.get("ok"):
        return {"assigned": False, "reason": f"producer API: {r.get('status')} {r.get('error')}"}
    data = r.get("data") or {}
    item = data.get("item")
    if not data.get("found") or not item:
        return {"assigned": False, "reason": "no eligible item"}
    lease = _leases()
    secs = int(_cfg.load().get("lease_seconds") or 3600)
    lease["leases"][item] = {"item_id": item, "worker_id": wid, "runtime": w.get("runtime", ""),
                             "expires_at": time.time() + secs}
    _save_leases(lease)
    return {"assigned": True, "item_id": item, "title": data.get("title"), "worker_id": wid,
            "runtime": w.get("runtime", ""), "lease_seconds": secs}


def cmd_schedule(pos, flags):
    sub = pos[0] if pos else "status"
    scope = flags.get("scope", "product_forge")
    project = flags.get("project", "")
    if sub == "next":
        return client.next_item(scope, project)
    if sub == "status":
        e = client.eligible(scope, project)
        d = e.get("data") or {}
        return {"total": d.get("total"), "eligible": d.get("eligible"), "blocked": d.get("blocked")}
    return client.eligible(scope, project)


def cmd_adapters(pos, flags):
    return {"runtimes": list(RUNTIMES),
            "note": "WorkerGrid is producer-agnostic; runtimes are worker execution environments"}


def cmd_dispatch(pos, flags):
    d = _workers()
    online = [w for w in d["workers"].values() if str(w.get("status")) in ("ONLINE", "IDLE")]
    assigned = []
    for w in online:
        r = cmd_work([], {"worker": w["worker_id"], "scope": flags.get("scope", "product_forge"),
                          "project": flags.get("project", "")})
        if r.get("assigned"):
            assigned.append({"worker_id": w["worker_id"], "item": r.get("item_id")})
    return {"dispatched": len(assigned), "assigned": assigned,
            "reason": "" if assigned else "no eligible work for ONLINE workers"}


def cmd_instruct(pos, flags):
    p = _cfg.instructions_path()
    if flags.get("show"):
        return {"instructions_file": p}
    text = " ".join(pos).strip()
    if text:
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n" + text + "\n")
        return {"updated": p, "appended": text}
    try:
        with open(p, encoding="utf-8") as f:
            return {"instructions_file": p, "content": f.read()}
    except Exception:
        return {"instructions_file": p, "content": ""}


def cmd_config(pos, flags):
    c = _cfg.load()
    return {"config": c, "instructions_file": _cfg.instructions_path(),
            "state_dir": _cfg.state_dir(), "producer_api": client._base()}


VERBS = {"register": cmd_register, "list": cmd_list, "status": cmd_status, "unregister": cmd_unregister,
         "work": cmd_work, "schedule": cmd_schedule, "adapters": cmd_adapters, "dispatch": cmd_dispatch,
         "instruct": cmd_instruct, "config": cmd_config}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    verb, rest = argv[0], argv[1:]
    if verb not in VERBS:
        print(f"unknown verb {verb!r}. verbs: {', '.join(VERBS)}")
        return 2
    pos, flags = _flags(rest)
    try:
        _emit(VERBS[verb](pos, flags))
    except Exception as e:
        print(f"[wg] {verb} error: {type(e).__name__}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
