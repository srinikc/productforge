#!/usr/bin/env python3
"""TTY-less prompt bridge — relay the pipeline's runtime prompts to a file channel.

Single concern: let interactive prompts (project/idea/tier, integration HIL, target
selection, enhance accept, `--step` pauses) be answered when there is no TTY, so the
pipeline can run interactively from an agent harness (e.g. `/pipeline`).

Resolution order for every prompt:
  1. bridge enabled (opt-in)         -> write request, print ``[PROMPT <id>]``,
                                        poll the answer file, then return it
  2. real TTY, bridge disabled       -> ``input(prompt)``                (unchanged)
  3. non-TTY, bridge disabled        -> ``default``                     (unchanged)

Opt-in beats the TTY check on purpose: some harness consoles report ``isatty()==True``
yet deliver EOF to ``input()`` (prompt shows, answer impossible). ``--interactive``
therefore always routes through the bridge.

Owner store (single writer = this module):
  ``<project_dir>/interactive/prompts.json``  — kind=control, scope=project
  ``<products_dir>/.interactive/prompts.json`` — scope=global, for prompts asked
  before a project directory exists (e.g. the project-name prompt).

Enable with env ``PIPELINE_INTERACTIVE=1`` (``run_pipeline.py --interactive`` sets it).
Answer from the harness with:
  ``python -m core.interactive --project <p> --list``
  ``python -m core.interactive --project <p> --answer <id> "<value>"``
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

TRUTHY = ("1", "true", "yes", "on")
DEFAULT_TIMEOUT = 1800  # seconds; bounded so an unanswered prompt never hangs forever
POLL_SECONDS = 3


def enabled() -> bool:
    """True when the file bridge is switched on (env ``PIPELINE_INTERACTIVE``)."""
    return str(os.getenv("PIPELINE_INTERACTIVE", "")).lower() in TRUTHY


def _isatty() -> bool:
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except Exception:
        return False


def _timeout() -> float:
    try:
        return float(os.getenv("PIPELINE_PROMPT_TIMEOUT", str(DEFAULT_TIMEOUT)))
    except Exception:
        return float(DEFAULT_TIMEOUT)


def _bridge_dir(project_dir: Optional[str] = None, products_dir: str = "products") -> str:
    if project_dir:
        return os.path.join(project_dir, "interactive")
    return os.path.join(products_dir, ".interactive")


def _store_path(project_dir: Optional[str] = None, products_dir: str = "products") -> str:
    return os.path.join(_bridge_dir(project_dir, products_dir), "prompts.json")


def _lock(d: str):
    os.makedirs(d, exist_ok=True)
    lp = os.path.join(d, ".lock")
    for _ in range(50):
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return lp
        except FileExistsError:
            time.sleep(0.1)
    return None


def _unlock(lp):
    try:
        os.remove(lp)
    except Exception:
        pass


def _read(p: str) -> Dict:
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("prompts"), list):
            return data
    except Exception:
        pass
    return {"updated_at": None, "prompts": []}


def _write(p: str, data: Dict) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    data["updated_at"] = datetime.now().isoformat()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def _next_id(prompts: List[Dict]) -> str:
    n = 0
    for item in prompts:
        pid = str(item.get("id") or "")
        if pid.startswith("P") and pid[1:].isdigit():
            n = max(n, int(pid[1:]))
    return f"P{n + 1}"


def _submit(prompt: str, default, options, kind: str,
            project_dir: Optional[str], products_dir: str) -> Dict:
    p = _store_path(project_dir, products_dir)
    lp = _lock(os.path.dirname(p))
    try:
        data = _read(p)
        prompts = data["prompts"]
        # Idempotent: reuse an existing PENDING prompt for the SAME question+kind so a
        # restart/rerun reuses the same P# instead of minting a new one (avoids the
        # P72/P74-style orphan prompts). An answered one is NOT reused.
        for it in prompts:
            if (it.get("status") == "pending"
                    and str(it.get("kind") or "text") == str(kind or "text")
                    and (it.get("prompt") or "").strip() == (prompt or "").strip()):
                return it
        item = {
            "id": _next_id(prompts),
            "prompt": prompt,
            "default": default,
            "options": options or [],
            "kind": kind,
            "project": os.path.basename(project_dir) if project_dir else "",
            "status": "pending",
            "value": None,
            "created_at": datetime.now().isoformat(),
            "answered_at": None,
        }
        prompts.append(item)
        _write(p, data)
        return item
    finally:
        _unlock(lp)


def _find(data: Dict, prompt_id: str) -> Optional[Dict]:
    prompts = data.get("prompts", [])
    if prompt_id in ("", "latest", "-1"):
        pend = [x for x in prompts if x.get("status") == "pending"]
        return pend[-1] if pend else None
    for item in prompts:
        if str(item.get("id")) == str(prompt_id):
            return item
    return None


def list_pending(project_dir: Optional[str] = None, products_dir: str = "products") -> List[Dict]:
    """Pending prompt requests awaiting an answer (oldest first)."""
    data = _read(_store_path(project_dir, products_dir))
    return [x for x in data.get("prompts", []) if x.get("status") == "pending"]


def answer(project_dir: Optional[str], prompt_id: str, value, products_dir: str = "products") -> Optional[Dict]:
    """Record an answer for a prompt id (or the newest pending when id is 'latest')."""
    p = _store_path(project_dir, products_dir)
    lp = _lock(os.path.dirname(p))
    try:
        data = _read(p)
        item = _find(data, prompt_id)
        if item is None:
            return None
        item["value"] = value
        item["status"] = "answered"
        item["answered_at"] = datetime.now().isoformat()
        _write(p, data)
        return item
    finally:
        _unlock(lp)


def ask(prompt: str, default=None, *, project_dir: Optional[str] = None,
        products_dir: str = "products", options=None, kind: str = "text",
        timeout: Optional[float] = None, context: str = "", impact: str = ""):
    """Ask a question the terminal way, or relay it through the bridge when headless.

    Returns a string (the same contract as ``input()``); ``default`` is returned
    whenever the bridge is disabled or the wait times out.
    """
    if not enabled():
        if _isatty():
            try:
                return input(prompt)
            except (EOFError, KeyboardInterrupt):
                return default
        return default

    item = _submit(prompt, default, options, kind, project_dir, products_dir)
    pid = item["id"]
    scope = f"--project {os.path.basename(project_dir)} " if project_dir else ""
    # Clear HIL prompt: context + impact + options (BI-0033), not a bare question.
    print(f"\n  ┌─ PROMPT {pid} " + "─" * max(0, 50 - len(pid)))
    print(f"  │ Q: {prompt.strip()}")
    if context:
        print(f"  │ Context: {context.strip()}")
    if impact:
        print(f"  │ Impact: {impact.strip()}")
    if options:
        print("  │ Options:")
        for i, o in enumerate(options, 1):
            print(f"  │   {i}) {o}")
    if default not in (None, ""):
        print(f"  │ Default (enter to accept): {default!r}")
    print(f"  └─ answer with: python -m core.interactive {scope}--answer {pid} \"<value>\"")

    max_wait = timeout if timeout is not None else _timeout()
    started = time.time()
    last_beat = 0.0
    ctrl_file = os.path.join(project_dir, "control.json") if project_dir else None
    while time.time() - started < max_wait:
        # Honour cross-process stop even while waiting for an answer.
        if ctrl_file and os.path.exists(ctrl_file):
            try:
                with open(ctrl_file, encoding="utf-8") as f:
                    act = str((json.load(f) or {}).get("action") or "").lower()
                if act == "stop":
                    print(f"  [PROMPT {pid}] control=stop; aborting wait")
                    return default
            except Exception:
                pass
        data = _read(_store_path(project_dir, products_dir))
        cur = _find(data, pid)
        if cur and cur.get("status") == "answered":
            print(f"  [PROMPT {pid}] answered: {cur.get('value')!r}")
            return cur.get("value")
        time.sleep(POLL_SECONDS)
        waited = int(time.time() - started)
        if waited - last_beat >= 30:
            last_beat = waited
            print(f"  [PROMPT {pid}] still waiting ({waited}s)...")

    print(f"  [PROMPT {pid}] timed out after {int(max_wait)}s; using default {default!r}")
    # Do NOT record this as an explicit "answered" - mark it timed_out so callers
    # and the dashboard can see it was never actually decided (BI-0048).
    try:
        _mark_timeout(project_dir, pid, default, products_dir)
    except Exception:
        pass
    return default


def _mark_timeout(project_dir: Optional[str], prompt_id: str, value, products_dir: str = "products") -> None:
    p = _store_path(project_dir, products_dir)
    lp = _lock(os.path.dirname(p))
    try:
        data = _read(p)
        item = _find(data, prompt_id)
        if item is None:
            return
        item["value"] = value
        item["status"] = "timed_out"
        item["timed_out"] = True
        item["answered_at"] = datetime.now().isoformat()
        _write(p, data)
    finally:
        _unlock(lp)


def list_timed_out(project_dir: Optional[str] = None, products_dir: str = "products") -> List[Dict]:
    """Prompts that timed out without an explicit human answer (BI-0048)."""
    data = _read(_store_path(project_dir, products_dir))
    return [x for x in data.get("prompts", []) if x.get("status") == "timed_out"]


def ask_many(items: List[Dict], *, project_dir: Optional[str] = None,
             products_dir: str = "products", timeout: Optional[float] = None) -> List:
    """Submit several prompts at once, then wait for all answers (order preserved).

    Each item is ``{"prompt": str, "default": Any, "options": [..], "kind": str}``.
    Returns one value per item; a prompt left unanswered (or a disabled bridge, or
    ``control=stop``) falls back to that item's ``default``.
    """
    items = list(items or [])
    if not items:
        return []
    if not enabled():
        if _isatty():
            try:
                return [input(it.get("prompt") or "") for it in items]
            except (EOFError, KeyboardInterrupt):
                return [it.get("default") for it in items]
        return [it.get("default") for it in items]

    pending: List[Dict] = []
    for it in items:
        pending.append(_submit(it.get("prompt") or "", it.get("default"),
                               it.get("options") or [], it.get("kind", "text"),
                               project_dir, products_dir))

    scope = f"--project {os.path.basename(project_dir)} " if project_dir else ""
    print(f"\n  [PROMPTS] {len(pending)} question(s) queued")
    for p in pending:
        print(f"  [PROMPT {p['id']}] {p['prompt'].strip()}")
        if p.get("options"):
            for o in p["options"]:
                print(f"      - {o}")
        if p.get("default") not in (None, ""):
            print(f"  [PROMPT {p['id']}] default: {p['default']!r}")
    print(f"  Answer each: python -m core.interactive {scope}--answer <id> \"<value>\"")

    max_wait = timeout if timeout is not None else _timeout()
    store = _store_path(project_dir, products_dir)
    ctrl_file = os.path.join(project_dir, "control.json") if project_dir else None
    started = time.time()
    last_beat = 0.0
    answered: Dict[str, Any] = {}
    while True:
        data = _read(store)
        answered = {str(x.get("id")): x.get("value")
                    for x in data.get("prompts", []) if x.get("status") == "answered"}
        if all(str(p["id"]) in answered for p in pending):
            break
        stop = False
        if ctrl_file and os.path.exists(ctrl_file):
            try:
                with open(ctrl_file, encoding="utf-8") as f:
                    stop = str((json.load(f) or {}).get("action") or "").lower() == "stop"
            except Exception:
                stop = False
        if stop:
            print("  [PROMPTS] control=stop; aborting wait")
            break
        if time.time() - started >= max_wait:
            print(f"  [PROMPTS] timed out after {int(max_wait)}s; using defaults for the rest")
            break
        time.sleep(POLL_SECONDS)
        waited = int(time.time() - started)
        if waited - last_beat >= 30:
            last_beat = waited
            missing = [p["id"] for p in pending if str(p["id"]) not in answered]
            print(f"  [PROMPTS] still waiting ({waited}s) on {missing}")

    out: List = []
    for p in pending:
        v = answered.get(str(p["id"]))
        if v in (None, ""):
            v = p.get("default")
            try:
                answer(project_dir, p["id"], v, products_dir)
            except Exception:
                pass
        out.append(v)
    return out


def _cli():
    ap = argparse.ArgumentParser(description="Answer pipeline prompts when running without a TTY")
    ap.add_argument("--project", default=None, help="project name (omit for the pre-project prompt)")
    ap.add_argument("--products-dir", default="products")
    ap.add_argument("--list", action="store_true", help="list pending prompts and exit")
    ap.add_argument("--answer", nargs=2, metavar=("ID", "VALUE"),
                    help="answer a prompt id ('latest' for the newest pending)")
    ap.add_argument("--answer-file", nargs=2, metavar=("ID", "PATH"),
                    help="answer a prompt id with the contents of a file (long/multiline answers)")
    args = ap.parse_args()

    project_dir = os.path.join(args.products_dir, args.project) if args.project else None

    if args.answer or args.answer_file:
        if args.answer_file:
            pid, path = args.answer_file
            try:
                with open(path, "r", encoding="utf-8") as f:
                    value = f.read().strip()
            except Exception as e:
                print(f"cannot read answer file {path}: {e}")
                sys.exit(2)
        else:
            pid, value = args.answer
        item = answer(project_dir, pid, value, args.products_dir)
        if item is None:
            print(f"No pending prompt '{pid}' for {args.project or '(pre-project)'}")
            sys.exit(1)
        print(f"answered {item['id']} = {value!r}")
        return

    pending = list_pending(project_dir, args.products_dir)
    if not pending:
        print("No pending prompts.")
        return
    for item in pending:
        line = f"[{item['id']}] {item['prompt'].strip()}"
        if item.get("default") is not None:
            line += f"  (default: {item['default']!r})"
        print(line)
        for o in item.get("options") or []:
            print(f"      - {o}")


if __name__ == "__main__":
    _cli()


def reset_for_new_run(project_dir: Optional[str] = None, products_dir: str = "products") -> str:
    """Archive the prompts store and start FRESH so prompt ids begin at P1 for this run.

    Keeps history (moves the old store to prompts-archive-<ts>.json) - nothing is deleted.
    """
    sp = _store_path(project_dir, products_dir)
    try:
        if os.path.exists(sp):
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            arch = os.path.join(os.path.dirname(sp), f"prompts-archive-{ts}.json")
            try:
                os.replace(sp, arch)
            except Exception:
                import shutil as _sh
                _sh.copyfile(sp, arch)
                os.remove(sp)
    except Exception:
        pass
    try:
        _write(sp, {"prompts": []})
    except Exception:
        pass
    return sp
