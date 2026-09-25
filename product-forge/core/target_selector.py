"""
Deployment target selector + catalog.

If the user hasn't declared `project.json → deploy.target`, the pipeline lists
clearly-described options (default `local`) and asks HIL to choose; the choice
(plus required credentials/inputs) is recorded. Target can also be a **remote
host (Linux/Windows)** on the network, or a vendor lab.

Non-interactive runs default to `local` and record it (never blocks).
"""
import json
import os
import sys
from typing import Any, Dict, List, Optional

CATALOG: List[Dict[str, Any]] = [
    {"key": "local", "kind": "provider", "desc": "Run on this machine (no infra)",
     "requires": []},
    {"key": "docker", "kind": "provider", "desc": "Docker / docker-compose",
     "requires": ["docker"]},
    {"key": "kind", "kind": "provider", "desc": "Local Kubernetes via kind",
     "requires": ["docker", "kind"]},
    {"key": "kubernetes", "kind": "provider", "desc": "Existing Kubernetes cluster",
     "requires": ["kubectl", "KUBECONFIG"]},
    {"key": "helm", "kind": "provider", "desc": "Helm release into a cluster",
     "requires": ["helm", "KUBECONFIG"]},
    {"key": "terraform", "kind": "provider", "desc": "Cloud infra via Terraform",
     "requires": ["terraform", "cloud credentials"]},
    {"key": "ansible", "kind": "provider", "desc": "Configure remote hosts via Ansible",
     "requires": ["ansible-playbook", "inventory/SSH"]},
    {"key": "remote-linux", "kind": "host", "desc": "Remote Linux host over SSH",
     "requires": ["ssh", "host", "user", "key/password"]},
    {"key": "remote-windows", "kind": "host", "desc": "Remote Windows host over WinRM",
     "requires": ["powershell", "host", "user", "password/cert"]},
    {"key": "vmware", "kind": "vendor", "desc": "VMware vSphere/ESXi lab",
     "requires": ["govc", "vcenter", "credentials"]},
    {"key": "dell", "kind": "vendor", "desc": "Dell iDRAC/OMSA", "requires": ["racadm", "host", "credentials"]},
    {"key": "hp", "kind": "vendor", "desc": "HPE iLO/OneView", "requires": ["ilorest", "host", "credentials"]},
    {"key": "cisco", "kind": "vendor", "desc": "Cisco networking", "requires": ["lab handle", "credentials"]},
    {"key": "netapp", "kind": "vendor", "desc": "NetApp storage", "requires": ["lab handle", "credentials"]},
    {"key": "aws", "kind": "cloud", "desc": "Amazon Web Services", "requires": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]},
    {"key": "azure", "kind": "cloud", "desc": "Microsoft Azure", "requires": ["AZURE_CLIENT_ID", "AZURE_TENANT_ID"]},
    {"key": "gcp", "kind": "cloud", "desc": "Google Cloud", "requires": ["GOOGLE_APPLICATION_CREDENTIALS"]},
    {"key": "s3", "kind": "registry", "desc": "S3 artifact bucket", "requires": ["AWS credentials", "bucket"]},
    {"key": "postgres", "kind": "data", "desc": "Managed PostgreSQL", "requires": ["connection string"]},
]


def list_targets(kind: Optional[str] = None) -> List[Dict[str, Any]]:
    return [t for t in CATALOG if not kind or t["kind"] == kind]


def catalog_text() -> str:
    lines = ["Available deployment targets (select one):"]
    for i, t in enumerate(CATALOG, 1):
        req = f"  (requires: {', '.join(t['requires'])})" if t["requires"] else ""
        lines.append(f"  {i:2d}. {t['key']:<15} {t['desc']}{req}")
    return "\n".join(lines)


def required_inputs(target: str) -> List[str]:
    for t in CATALOG:
        if t["key"] == target:
            return list(t["requires"])
    return []


def _cfg_path(project_dir: str) -> str:
    return os.path.join(project_dir, "project.json")


def select(project_dir: str, project: str = "") -> Dict[str, Any]:
    """Chosen target: explicit > advisor-recommended shortlist (HIL) > default."""
    try:
        with open(_cfg_path(project_dir), "r", encoding="utf-8") as f:
            cfg = json.load(f) or {}
    except Exception:
        cfg = {}
    deploy = cfg.get("deploy") or {}
    target = str(deploy.get("target") or "").strip()

    # Dynamic recommendation from product/stack/architect/marketing context.
    try:
        from core.target_advisor import recommend, present
        rec = recommend(project_dir, project)
    except Exception:
        rec = {"recommended": [], "default": "local", "full_catalog": [t["key"] for t in CATALOG]}

    if target:
        return {"target": target, "source": "project", "requires": required_inputs(target),
                "recommended": rec.get("recommended", [])}

    from core import interactive as _interactive
    if not _interactive.enabled() and not sys.stdin.isatty():
        chosen = rec.get("default") or "local"
        _record(project_dir, chosen, "recommended_default")
        return {"target": chosen, "source": "recommended_default",
                "requires": required_inputs(chosen), "recommended": rec.get("recommended", [])}

    try:
        print(present(rec))
    except Exception:
        print(catalog_text())
    default = rec.get("default") or "local"
    try:
        ans = (_interactive.ask(f"Select target number (Enter = {default}) > ", "",
                                project_dir=project_dir) or "").strip()
        ranked = rec.get("recommended", [])
        if ans.isdigit() and 1 <= int(ans) <= len(ranked):
            chosen = ranked[int(ans) - 1]["key"]
        elif ans.isdigit() and ranked and int(ans) == len(ranked) + 1:
            print(catalog_text())
            ans2 = (_interactive.ask("Select from full catalog (number) > ", "1",
                                     project_dir=project_dir) or "1").strip()
            idx = int(ans2) if ans2.isdigit() else 1
            chosen = CATALOG[max(1, min(idx, len(CATALOG))) - 1]["key"]
        else:
            chosen = default
    except Exception:
        chosen = default
    _record(project_dir, chosen, "hil")
    print(f"  [TARGET] selected '{chosen}' (requires: {required_inputs(chosen) or 'none'})")
    return {"target": chosen, "source": "hil", "requires": required_inputs(chosen),
            "recommended": rec.get("recommended", [])}


def _record(project_dir: str, target: str, source: str):
    try:
        p = _cfg_path(project_dir)
        with open(p, "r", encoding="utf-8") as f:
            cfg = json.load(f) or {}
        cfg.setdefault("deploy", {})["target"] = target
        cfg["deploy"]["_selected_by"] = source
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
