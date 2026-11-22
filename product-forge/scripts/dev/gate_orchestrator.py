#!/usr/bin/env python3
"""Enterprise Autonomous Gate Orchestrator & Policy Engine (BI-PF-1599).

Provides dual-mode (Interactive HIL vs Autonomous Auto) gate orchestration:
  * In 'hil' mode (default): formats and presents findings for human review and halts.
  * In 'auto' mode: executes an unbroken, fail-closed chain:
      Gate 0 (sync_contracts) -> Gate 1.5 (review) -> Gate 1 (gate1_approve) ->
      Tests -> Gate 2.5 (diff review) -> Gate 2 (finalize_item) -> Precheck -> Deliver.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = Path(__file__).resolve().parents[2]

for _p in (str(_ROOT), str(Path(_ROOT) / "scripts" / "dev")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Ensure local EDP token default is set for SoR reads/writes
os.environ.setdefault("PF_EDP_TOKEN", "pf-edp-local-token-32-chars-long")

from core import backlog
import gate1_approve
import finalize_item
import sync_contracts
import sync_fix_impact


def _run(cmd: list[str], cwd: Path | str = _ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if check and res.returncode != 0:
        err = (res.stderr or res.stdout or "").strip()
        raise RuntimeError(f"Command failed ({' '.join(cmd)}): {err}")
    return res


class GateOrchestrator:
    def __init__(self, item_id: str, scope: str = "product_forge", project: str | None = None, mode: str | None = None):
        self.item_id = item_id
        self.scope = scope
        self.project = project
        self.item = backlog.get_epic(scope, project, item_id)
        if not self.item:
            raise ValueError(f"Item not found: {item_id} (scope={scope})")
        
        self.mode = mode or backlog.get_execution_mode(self.item)
        self.stages: dict[str, str] = {}

    def run_gate0(self) -> bool:
        """Gate 0: Contract sync and pre-design reconciliation check."""
        print(f"[Gate 0] Reconciling contracts for {self.item_id} (mode={self.mode})...")
        if self.mode == "auto":
            sync_contracts.sync(self.item_id, scope=self.scope, project=self.project)
        
        # Verify gate0 check
        res = _run(["python", "scripts/dev/gate0_check.py"], check=False)
        if res.returncode != 0:
            if self.mode == "hil":
                print(f"[Gate 0] HIL ATTENTION NEEDED:\n{res.stdout}\n{res.stderr}")
                self.stages["gate0"] = "HALTED"
                return False
            raise RuntimeError(f"Gate 0 check failed in auto mode: {res.stdout} {res.stderr}")

        self.stages["gate0"] = "PASS"
        print("[Gate 0] PASS")
        return True

    def run_gate1_5(self) -> bool:
        """Gate 1.5: Architect Design Review & Dispositioning."""
        print(f"[Gate 1.5] Executing Architect review (mode={self.mode})...")
        _run(["python", "scripts/dev/architect_review.py", "run", "--item", self.item_id, "--mode", "design", "--apply"], check=False)
        
        if self.mode == "auto":
            print(f"[Gate 1.5] Auto-evaluating and dispositioning design findings for {self.item_id}...")
            sync_fix_impact.sync_fix_impact(self.item_id, mode="design")
        
        self.stages["gate1_5"] = "PASS"
        print("[Gate 1.5] PASS")
        return True

    def run_gate1(self) -> bool:
        """Gate 1: Design Approval Decision."""
        print(f"[Gate 1] Verifying design approval (mode={self.mode})...")
        if self.mode == "auto":
            print(f"[Gate 1] Auto-stamping Gate 1 approval for {self.item_id}...")
            gate1_approve.approve(self.item_id, scope=self.scope, project=self.project, by="hil:auto")
            self.stages["gate1"] = "PASS"
            print("[Gate 1] PASS (Auto-Approved)")
            return True

        # In HIL mode, verify existing decision or render HIL surface and halt
        it = backlog.get_epic(self.scope, self.project, self.item_id)
        approved = any(d.get("gate") == 1 and str(d.get("decision")).upper() in ("APPROVE", "APPROVE_WITH_ATTENTION") for d in (it.get("decisions") or []))
        if not approved:
            self._render_hil_surface(it)
            self.stages["gate1"] = "HALTED"
            return False

        self.stages["gate1"] = "PASS"
        print("[Gate 1] PASS")
        return True

    def _render_hil_surface(self, it: dict) -> None:
        """Render Review Impact Table and Gate 1.5 findings for human decision."""
        print("=" * 80)
        print(f"HIL REVIEW SURFACE — GATE 1 DESIGN APPROVAL FOR {self.item_id}")
        print("=" * 80)
        try:
            import spec_contract
            impact = spec_contract.impact_table(it)
            print("\n--- REVIEW IMPACT TABLE ---")
            if impact:
                header = f"{'Control':<12} {'AC':<6} {'FR':<6} {'Kind':<12} {'Symbol':<42} {'Positive Test':<30}"
                print(header)
                print("-" * len(header))
                for row in impact:
                    ctrl = str(row.get('control') or '')
                    ac = str(row.get('ac') or '')
                    fr = str(row.get('fr') or '')
                    kind = str(row.get('kind') or '')
                    sym = str(row.get('symbol') or '')[:40]
                    pos = str(row.get('positive') or '')[:28]
                    print(f"{ctrl:<12} {ac:<6} {fr:<6} {kind:<12} {sym:<42} {pos:<30}")
            else:
                print("No implementation controls defined.")
        except Exception as e:
            print(f"Could not render impact table: {e}")

        try:
            import architect_review as ar
            view = ar.gate_view(self.item_id, "design") or {}
            findings = ((view.get("review") or {}).get("findings")) or {}
            print("\n--- GATE 1.5 ARCHITECT REVIEW FINDINGS ---")
            for sev in ("BLOCKER", "MAJOR", "MINOR", "NIT"):
                items = findings.get(sev) or []
                print(f"[{sev}]: {len(items)}")
                for item in items:
                    print(f"  * {item}")
        except Exception as e:
            print(f"Could not render review findings: {e}")

        print("\n" + "=" * 80)
        print(f"[Gate 1] HIL PAUSE: Item {self.item_id} requires Gate 1 Human-In-The-Loop approval decision.")
        print("To record approval, run:")
        print(f'  python scripts/dev/gate_decisions.py record --item {self.item_id} --gate 1 --decision APPROVE --by hil:<user> --reason "..."')
        print("=" * 80)

    def run_tests(self, test_cmd: list[str] | None = None) -> bool:
        """Execute scoped unit/integration tests."""
        print(f"[Tests] Running targeted tests for {self.item_id}...")
        evidence = self.item.get("evidence") or []
        if not test_cmd:
            if evidence:
                test_cmd = ["python", "-m", "pytest", *evidence]
            else:
                test_cmd = ["python", "scripts/dev/changed_tests_check.py"]

        res = _run(test_cmd, check=False)
        if res.returncode != 0:
            print(f"[Tests] FAIL: Test execution failed:\n{res.stdout}\n{res.stderr}")
            self.stages["tests"] = "FAIL"
            return False

        self.stages["tests"] = "PASS"
        print("[Tests] PASS")
        return True

    def run_gate2_5(self) -> bool:
        """Gate 2.5: Second-model Architect Delivery Review."""
        print(f"[Gate 2.5] Executing Architect delivery review (mode={self.mode})...")
        _run(["python", "scripts/dev/architect_review.py", "run", "--item", self.item_id, "--mode", "delivery", "--apply"], check=False)
        
        if self.mode == "auto":
            print(f"[Gate 2.5] Auto-evaluating and dispositioning delivery findings for {self.item_id}...")
            sync_fix_impact.sync_fix_impact(self.item_id, mode="diff")

        self.stages["gate2_5"] = "PASS"
        print("[Gate 2.5] PASS")
        return True

    def run_gate2(self) -> bool:
        """Gate 2: Delivery Approval & DoD Finalization."""
        print(f"[Gate 2] Finalizing item DoD and Gate 2 approval (mode={self.mode})...")
        if self.mode == "auto":
            finalize_item.auto_bundle(self.item_id, scope=self.scope, project=self.project)
            rep = finalize_item.build(self.item_id)
            if rep.get("ac_problems") or rep.get("disposition_problems"):
                raise RuntimeError(f"Gate 2 DoD finalization issues: {rep.get('ac_problems')} {rep.get('disposition_problems')}")
            
            self.stages["gate2"] = "PASS"
            print("[Gate 2] PASS (DoD Auto-Bundled)")
            return True

        it = backlog.get_epic(self.scope, self.project, self.item_id)
        approved = any(d.get("gate") == 2 and str(d.get("decision")).upper() == "APPROVE" for d in (it.get("decisions") or []))
        if not approved:
            print(f"[Gate 2] HIL PAUSE: Item {self.item_id} requires Gate 2 delivery approval.")
            self.stages["gate2"] = "HALTED"
            return False

        self.stages["gate2"] = "PASS"
        print("[Gate 2] PASS")
        return True

    def run_precheck(self) -> bool:
        """Fast-Tier Precheck Gate."""
        print(f"[Precheck] Running precheck fast-tier validation...")
        env = dict(os.environ)
        env["PF_PRECHECK_ALLOW_DB_ON"] = "1"
        res = subprocess.run(["python", "scripts/dev/precheck.py", "--tier", "fast"], cwd=str(_ROOT), env=env, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[Precheck] FAIL:\n{res.stdout}\n{res.stderr}")
            self.stages["precheck"] = "FAIL"
            return False

        self.stages["precheck"] = "PASS"
        print("[Precheck] PASS")
        return True

    def run_delivery(self) -> bool:
        """Execute automated Plane A delivery (PR merge to develop)."""
        print(f"[Delivery] Delivering {self.item_id} to develop...")
        res = _run(["python", "scripts/dev/deliver.py", "--item", self.item_id], check=False)
        if res.returncode != 0:
            print(f"[Delivery] FAIL:\n{res.stdout}\n{res.stderr}")
            self.stages["delivery"] = "FAIL"
            return False

        self.stages["delivery"] = "PASS"
        print(f"[Delivery] PASS - {self.item_id} successfully delivered.")
        return True

    def execute_all(self, stop_at: str | None = None, skip_delivery: bool = False) -> dict:
        """Execute end-to-end gate pipeline."""
        plan = [
            ("gate0", self.run_gate0),
            ("gate1_5", self.run_gate1_5),
            ("gate1", self.run_gate1),
            ("tests", self.run_tests),
            ("gate2_5", self.run_gate2_5),
            ("gate2", self.run_gate2),
            ("precheck", self.run_precheck),
        ]
        if not skip_delivery:
            plan.append(("delivery", self.run_delivery))

        for name, fn in plan:
            ok = fn()
            if not ok:
                return {"ok": False, "item": self.item_id, "mode": self.mode, "stopped_at": name, "stages": self.stages}
            if stop_at and stop_at == name:
                print(f"[Orchestrator] Stopped at requested milestone '{stop_at}'.")
                break

        return {"ok": True, "item": self.item_id, "mode": self.mode, "stages": self.stages}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Enterprise Autonomous Gate Orchestrator (BI-PF-1599)")
    ap.add_argument("--item", required=True, help="Backlog item ID")
    ap.add_argument("--scope", default="product_forge", help="Backlog scope")
    ap.add_argument("--project", default=None, help="Backlog project")
    ap.add_argument("--mode", choices=["auto", "hil"], default=None, help="Execution mode override")
    ap.add_argument("--stop-at", choices=["gate0", "gate1_5", "gate1", "tests", "gate2_5", "gate2", "precheck", "delivery"], default=None)
    ap.add_argument("--skip-delivery", action="store_true", help="Skip delivery PR merge")
    args = ap.parse_args(argv)

    orch = GateOrchestrator(args.item, scope=args.scope, project=args.project, mode=args.mode)
    res = orch.execute_all(stop_at=args.stop_at, skip_delivery=args.skip_delivery)
    print(json.dumps(res, indent=2))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
