"""EDP-12 build/deploy residency gate (BI-PF-1304).

Validates the residency section with the Go authority (cmd/pfresidency) and a Python parity check.
Exit: 0 pass (or warn-mode violation), 1 blocked policy violation, 2 execution failure.
--report is non-fatal (exit 0) and writes the JSON report.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "scripts" / "dev"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

POLICY = ROOT / "config" / "residency-policy.json"
EVENT = Path(os.environ.get("PF_RESIDENCY_EVENT") or (ROOT / "engineering" / "residency-gate.json"))
JSONL = Path(os.environ.get("PF_RESIDENCY_JSONL") or (ROOT / "engineering" / "residency-gate.jsonl"))
MAX_JSONL = 5 * 1024 * 1024


def _policy() -> dict:
    try:
        with open(POLICY, encoding="utf-8-sig") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception as e:
        print(f"residency: BLOCK policy unreadable: {e}", file=sys.stderr)
        return {"gate_mode": "block", "_error": "RESIDENCY_POLICY_UNREADABLE"}


def _event(rec: dict) -> None:
    try:
        ROOT.joinpath("engineering").mkdir(parents=True, exist_ok=True)
        EVENT.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        if JSONL.exists() and JSONL.stat().st_size > MAX_JSONL:
            JSONL.with_suffix(".jsonl.3").unlink(missing_ok=True)
            for i in (2, 1):
                old, new = JSONL.with_suffix(f".jsonl.{i}"), JSONL.with_suffix(f".jsonl.{i + 1}")
                if old.exists():
                    os.replace(old, new)
            os.replace(JSONL, JSONL.with_suffix(".jsonl.1"))
        with open(JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception as e:
        print(f"residency: WARN cannot write event: {e}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Residency manifest build/deploy gate")
    ap.add_argument("--scope", default="product_forge")
    ap.add_argument("--project", default="")
    ap.add_argument("--manifest", default="")
    ap.add_argument("--profiles", default="")
    ap.add_argument("--mode", choices=("warn", "block"), default="")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    from core import packaging
    manifest = a.manifest or packaging.residency_path(a.scope, a.project)
    profiles = a.profiles or str(packaging.residency_profiles_dir())
    policy = _policy()
    mode = a.mode or str(policy.get("gate_mode") or "warn")
    expires = str(policy.get("gate_mode_expires") or "")
    mode_original = mode
    if mode == "warn" and expires:
        try:
            from datetime import date
            if date.fromisoformat(expires) < date.today():
                mode = "block"
        except ValueError:
            mode = "block"
    rec = {"at": datetime.now(timezone.utc).isoformat(), "scope": a.scope, "project": a.project,
           "manifest": str(manifest), "gate_mode": mode, "gate_mode_original": mode_original,
           "report_version": 1, "gate_mode_escalated": mode != mode_original}
    try:
        try:
            with open(manifest, encoding="utf-8-sig") as f:
                py = {"validation": packaging.validate_residency(json.load(f))}
        except Exception as e:
            py = {"validation": {"valid": False, "unmet": ["RESIDENCY_MANIFEST_UNREADABLE"]}}
        gomod = ROOT / "go" / "residencymanifest"
        cmd = ["go", "run", "./cmd/pfresidency", "--manifest", str(manifest),
               "--profiles", profiles, "--mode", mode, "--report"]
        r = subprocess.run(cmd, cwd=str(gomod), capture_output=True, text=True, timeout=120)
    except Exception as e:
        rec.update({"ok": False, "execution_error": str(e), "errors": ["RESIDENCY_VALIDATOR_UNAVAILABLE"]})
        _report(rec, a.report)
        _event(rec)
        print(f"residency: BLOCK validator unavailable: {e}", file=sys.stderr)
        return 2
    out = (r.stdout or "").strip().splitlines()
    try:
        go = json.loads(out[-1]) if out else {}
    except Exception:
        go = {}
    if not isinstance(go, dict) or "ok" not in go:
        rec.update({"ok": False, "execution_error": "validator returned no JSON",
                    "errors": ["RESIDENCY_VALIDATOR_UNAVAILABLE"]})
        _report(rec, a.report)
        _event(rec)
        print(f"residency: BLOCK validator returned no JSON: {r.stderr.strip()}", file=sys.stderr)
        return 2
    py_valid = bool((py.get("validation") or {}).get("valid"))
    go_valid = bool(go.get("ok"))
    parity = py_valid == go_valid
    errors = list(go.get("errors") or (py.get("validation") or {}).get("unmet") or [])
    rec.update({"ok": go_valid and parity, "go": go, "python_valid": py_valid,
                "parity": parity, "errors": errors, "exit": r.returncode})
    _report(rec, a.report)
    _event(rec)
    if r.returncode == 2 or not parity:
        print(f"residency: BLOCK execution/parity failure: {errors or r.stderr.strip()}", file=sys.stderr)
        return 2
    if not go_valid:
        hard = {"RESIDENCY_UNKNOWN_HOME", "RESIDENCY_PROFILE_UNREADABLE", "RESIDENCY_SCHEMA_VERSION"}
        if mode == "warn" and not (set(errors) & hard):
            print(f"residency: WARN {len(errors)} violation(s): {errors}", file=sys.stderr)
            return 0 if a.report else 0
        print(f"residency: BLOCK {len(errors)} violation(s): {errors}", file=sys.stderr)
        return 0 if a.report else 1
    print("residency: OK")
    return 0


def _report(rec: dict, force: bool) -> None:
    if force:
        print(json.dumps(rec, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
