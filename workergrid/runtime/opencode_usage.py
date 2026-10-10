#!/usr/bin/env python3
"""Runtime wrapper (WorkerGrid adapter): run the agent runtime, capture its usage, write `.wg/usage.json`.

Runs ``opencode run --format json <args>`` in the current directory (the assignment worktree), sums the per-step
token/cost usage from the JSON event stream, and writes ``<cwd>/.wg/usage.json`` for the worker to forward to the
producer as ``usage`` (BI-PF-1239). This is the ONLY place that knows the runtime's wire format - the producer
(PF) is framework-agnostic and only sees the normalized ``usage`` payload.

Usage: ``python workergrid/runtime/opencode_usage.py [--model M] [--auto] "<message>"``
Passes stdout/stderr through and exits with the runtime's exit code. A usage-parse failure never fails the run.
"""
import json
import os
import subprocess
import sys


def _usage_from_stream(stream: str) -> dict:
    inp = out = reas = cr = cw = total = calls = 0
    cost = 0.0
    model = ""
    for line in (stream or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("type") != "step_finish":
            continue
        part = ev.get("part") or {}
        t = part.get("tokens") or {}
        cache = t.get("cache") or {}
        calls += 1
        inp += int(t.get("input") or 0)
        out += int(t.get("output") or 0)
        reas += int(t.get("reasoning") or 0)
        cr += int(cache.get("read") or 0)
        cw += int(cache.get("write") or 0)
        total += int(t.get("total") or 0)
        try:
            cost += float(part.get("cost") or 0.0)
        except Exception:
            pass
        model = str(part.get("modelID") or part.get("model") or model or "")
    return {"input_tokens": inp, "output_tokens": out, "reasoning_tokens": reas,
            "cache_read_tokens": cr, "cache_write_tokens": cw, "total_tokens": total,
            "calls": calls, "cost_usd": round(cost, 6),
            "cost_source": "reported" if calls else "unknown", "model": model}


def main() -> int:
    args = sys.argv[1:]
    cmd = ["opencode", "run", "--format", "json", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    usage = _usage_from_stream(proc.stdout)
    try:
        d = os.path.join(os.getcwd(), ".wg")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "usage.json"), "w", encoding="utf-8") as f:
            json.dump(usage, f, indent=2)
    except Exception:
        pass
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
