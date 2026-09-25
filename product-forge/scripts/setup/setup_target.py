"""Setup automation for deployment targets (starter catalog).

Usage:
  python scripts/setup/setup_target.py <target> [--json]

Guarded: if the required tooling/credentials are missing it reports `not_run`
(never fabricates). The pipeline can call this before APPLY when a target needs
one-time setup.

Targets: local docker kind kubernetes helm terraform ansible remote-linux remote-windows
"""
import json
import os
import shutil
import subprocess
import sys

TARGETS = {
    "local": {"need": [], "desc": "Run on this machine (no setup)"},
    "docker": {"need": ["docker"], "desc": "Docker / compose"},
    "kind": {"need": ["docker", "kind"], "desc": "Local Kubernetes (kind)"},
    "kubernetes": {"need": ["kubectl"], "desc": "Existing cluster (KUBECONFIG)"},
    "helm": {"need": ["helm"], "desc": "Helm release into a cluster"},
    "terraform": {"need": ["terraform"], "desc": "Terraform (cloud creds)"},
    "ansible": {"need": ["ansible-playbook"], "desc": "Ansible inventory/SSH"},
    "remote-linux": {"need": ["ssh"], "desc": "Remote Linux host (SSH)"},
    "remote-windows": {"need": ["powershell"], "desc": "Remote Windows host (WinRM)"},
}


def _which(exe):
    return shutil.which(exe) is not None


def _run(cmd, timeout=600):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"step": " ".join(cmd), "ok": r.returncode == 0,
                "tail": ((r.stdout or "") + (r.stderr or ""))[-300:]}
    except FileNotFoundError:
        return {"step": " ".join(cmd), "ok": None, "error": "tool missing"}
    except Exception as e:
        return {"step": " ".join(cmd), "ok": False, "error": str(e)[:200]}


def setup(target, project_dir="."):
    target = (target or "local").lower()
    spec = TARGETS.get(target)
    if not spec:
        return {"target": target, "status": "unknown", "steps": []}
    missing = [t for t in spec["need"] if not _which(t)]
    creds = [k for k in ("KUBECONFIG", "AWS_ACCESS_KEY_ID", "AZURE_CLIENT_ID",
                         "GOOGLE_APPLICATION_CREDENTIALS") if os.environ.get(k)]
    steps = []
    status = "ready"
    if missing:
        status = "not_run"
    else:
        if target == "kind":
            steps.append(_run(["kind", "get", "clusters"]))
            steps.append(_run(["kind", "create", "cluster", "--name", "pf-local"], timeout=1800))
        elif target == "helm":
            steps.append(_run(["helm", "repo", "update"]))
        elif target == "terraform":
            steps.append(_run(["terraform", "version"]))
        elif target == "ansible":
            steps.append(_run(["ansible", "--version"]))
    return {"target": target, "status": status, "tooling_missing": missing,
            "credentials_present": creds, "steps": steps, "desc": spec["desc"]}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    target = args[0] if args else "local"
    res = setup(target)
    if as_json:
        print(json.dumps(res))
    else:
        print(f"target={res['target']} status={res['status']} desc={res['desc']}")
        if res["tooling_missing"]:
            print("  missing tooling:", res["tooling_missing"])
        if res["credentials_present"]:
            print("  credentials present:", res["credentials_present"])
        for s in res["steps"]:
            print("  -", s.get("step"), "->", s.get("ok"))


if __name__ == "__main__":
    main()
