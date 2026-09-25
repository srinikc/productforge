"""
Vendor integration adapters + lab handles.

Vendors (VMware/HPE/Dell/Cisco/NetApp/cloud/DBs) are handled as **data + adapters
+ user/vendor-provided labs** — never fabricated. Each adapter is command-driven
(CLI when present) and records whether a real lab handle was provided.

Config: docs/infra.json -> "vendors": [
  { "name": "vmware", "lab_handle": "vcenter.lab.example", "cli": "govc",
    "commands": { "apply": [["govc","import.ova",...]], "verify": [[...]], "destroy": [[...]] } } ]
"""
import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

_VENDORS = {
    "vmware": ("govc", "VMware vSphere/ESXi"),
    "dell": ("racadm", "Dell iDRAC / OMSA"),
    "hp": ("ilorest", "HPE iLO / OneView"),
    "cisco": ("", "Cisco networking"),
    "netapp": ("", "NetApp storage"),
    "s3": ("aws", "AWS S3"),
    "aws": ("aws", "Amazon Web Services"),
    "azure": ("az", "Microsoft Azure"),
    "gcp": ("gcloud", "Google Cloud"),
    "postgres": ("psql", "PostgreSQL"),
    "oracle": ("sqlplus", "Oracle Database"),
}


def list_vendors() -> Dict[str, Dict]:
    return {k: {"cli": v[0], "description": v[1]} for k, v in _VENDORS.items()}


def _run(cmd: List[str], cwd: str, timeout: int = 600) -> Dict:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return {"step": " ".join(cmd), "ok": r.returncode == 0,
                "tail": ((r.stdout or "") + (r.stderr or ""))[-400:]}
    except FileNotFoundError:
        return {"step": " ".join(cmd), "ok": None, "error": "cli missing"}
    except Exception as e:
        return {"step": " ".join(cmd), "ok": False, "error": str(e)[:200]}


class VendorAdapter:
    def __init__(self, name: str):
        self.name = name
        spec = _VENDORS.get(name, ("", "vendor"))
        self.cli, self.description = spec[0], spec[1]

    def detect(self) -> bool:
        return bool(self.cli) and shutil.which(self.cli) is not None

    def _phase(self, project_dir: str, cfg: Dict, key: str) -> Dict:
        cmds = (cfg.get("commands") or {}).get(key) or []
        steps = []
        for c in cmds:
            cmd = c if isinstance(c, list) else str(c).split()
            if cmd:
                steps.append(_run(cmd, project_dir, timeout=int(cfg.get("timeout", 900))))
        chk = [s for s in steps if s.get("ok") is not None]
        return {"ok": all(s["ok"] for s in chk) if chk else None, "steps": steps}

    def apply(self, project_dir: str, cfg: Dict) -> Dict:
        return self._phase(project_dir, cfg, "apply")

    def verify(self, project_dir: str, cfg: Dict) -> Dict:
        return self._phase(project_dir, cfg, "verify")

    def destroy(self, project_dir: str, cfg: Dict) -> Dict:
        return self._phase(project_dir, cfg, "destroy")


def get_adapter(name: str) -> VendorAdapter:
    return VendorAdapter(name)


def _read_infra(project_dir: str) -> Dict:
    try:
        with open(os.path.join(project_dir, "docs", "infra.json"), "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def run_vendors(project_dir: str, infra: Optional[Dict] = None) -> List[Dict]:
    """Apply+verify each configured vendor (lab handle recorded; policy=external)."""
    infra = infra or _read_infra(project_dir)
    out = []
    for v in (infra.get("vendors") or []):
        name = str(v.get("name") or v.get("vendor") or "").lower()
        ad = VendorAdapter(name)
        res = {"vendor": name, "lab_handle": v.get("lab_handle", ""),
               "detected": ad.detect(),
               "verification": "external" if not ad.detect() else "internal"}
        res["apply"] = ad.apply(project_dir, v)
        res["verify"] = ad.verify(project_dir, v)
        out.append(res)
    return out
