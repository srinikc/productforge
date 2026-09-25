"""
Deployment providers (gap 8) — pluggable apply/verify/destroy per target.

Deploy is multi-target (docker, local process, kubernetes, terraform, ansible,
paas, installer, or a generic command escape-hatch). The executor selects a
provider from project config (`deploy.target`) or auto-detects; each provider
knows how to bring the app up, verify it, and tear it down.

Everything is guarded: no config / no tool -> provider reports not-applicable.
"""
import json
import os
import shutil
import subprocess
import time
import urllib.request
from typing import Dict, List, Optional


def _which(exe: str) -> bool:
    return shutil.which(exe) is not None


def _run(cmd: List[str], cwd: str, timeout: int = 600) -> Dict:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        tail = ((r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else ""))[-3000:]
        return {"cmd": " ".join(cmd), "ok": r.returncode == 0, "tail": tail}
    except subprocess.TimeoutExpired:
        return {"cmd": " ".join(cmd), "ok": False, "tail": "timeout"}
    except Exception as e:
        return {"cmd": " ".join(cmd), "ok": False, "tail": str(e)}


def load_deploy_cfg(project_dir: str) -> Dict:
    """Merge project.json 'deploy' with tech-stack chosen deploy/runtime."""
    cfg: Dict = {}
    try:
        p = os.path.join(project_dir, "project.json")
        if os.path.exists(p):
            cfg.update((json.load(open(p, encoding="utf-8")) or {}).get("deploy") or {})
    except Exception:
        pass
    try:
        ts = os.path.join(project_dir, "docs", "tech-stack.json")
        if os.path.exists(ts):
            chosen = (json.load(open(ts, encoding="utf-8")) or {}).get("chosen") or {}
            for k in ("deploy", "runtime", "kind"):
                if chosen.get(k) and k not in cfg:
                    cfg[k] = chosen[k]
    except Exception:
        pass
    return cfg


def _health(url: str, timeout: int = 90) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status < 500:
                    return True
        except Exception:
            time.sleep(2)
    return False


def _smoke(project_dir: str) -> List[Dict]:
    try:
        from core.nfr_runner import run_smoke
        return run_smoke(project_dir)
    except Exception:
        return []


class DeploymentProvider:
    name = "none"

    def detect(self, project_dir: str, cfg: Dict) -> bool:
        return False

    def apply(self, project_dir: str, cfg: Dict) -> Dict:
        return {"ok": None, "steps": []}

    def verify(self, project_dir: str, cfg: Dict) -> Dict:
        return {"ok": None, "steps": []}

    def destroy(self, project_dir: str, cfg: Dict) -> Dict:
        return {"ok": None, "steps": []}


class DockerProvider(DeploymentProvider):
    name = "docker"

    def _compose(self, project_dir: str) -> Optional[str]:
        for rel in ("docker-compose.yml", "docker-compose.yaml", "compose.yml",
                    os.path.join("docker", "docker-compose.yml")):
            if os.path.exists(os.path.join(project_dir, rel)):
                return rel
        return None

    def detect(self, project_dir: str, cfg: Dict) -> bool:
        return _which("docker") and self._compose(project_dir) is not None

    def apply(self, project_dir: str, cfg: Dict) -> Dict:
        compose = self._compose(project_dir)
        steps = []
        # Port-collision detection: pick a free host port if the configured one is busy.
        try:
            from core.net_ports import resolve_app_port
            info = resolve_app_port(project_dir, cfg)
            if info.get("collision"):
                steps.append({"cmd": "port-check", "ok": True,
                              "tail": f"preferred {info['preferred']} busy -> using {info['port']}"})
                cfg = {**cfg, "port": info["port"]}
                os.environ["PORT"] = str(info["port"])
            elif info.get("port"):
                cfg = {**cfg, "port": info["port"]}
        except Exception:
            pass
        step = _run(["docker", "compose", "-f", compose, "up", "-d", "--build"], project_dir, timeout=900)
        steps.append(step)
        return {"ok": step["ok"], "steps": steps}

    def verify(self, project_dir: str, cfg: Dict) -> Dict:
        steps = []
        port = cfg.get("port")
        if port:
            ok = _health(f"http://127.0.0.1:{port}{cfg.get('health_path', '/')}", timeout=90)
            steps.append({"cmd": "health-check", "ok": ok, "tail": f"port={port}"})
        steps += _smoke(project_dir)
        checkable = [s for s in steps if s.get("ok") is not None]
        return {"ok": all(s["ok"] for s in checkable) if checkable else None, "steps": steps}

    def destroy(self, project_dir: str, cfg: Dict) -> Dict:
        compose = self._compose(project_dir)
        step = _run(["docker", "compose", "-f", compose, "down", "-v"], project_dir, timeout=300)
        return {"ok": step["ok"], "steps": [step]}


class LocalProvider(DeploymentProvider):
    """No containers: run the smoke suite against the local checkout (8.4)."""
    name = "local"

    def detect(self, project_dir: str, cfg: Dict) -> bool:
        return os.path.exists(os.path.join(project_dir, "package.json")) or \
            os.path.exists(os.path.join(project_dir, "pyproject.toml")) or \
            os.path.isdir(os.path.join(project_dir, "tests"))

    def apply(self, project_dir: str, cfg: Dict) -> Dict:
        return {"ok": None, "steps": [{"cmd": "apply(local)", "ok": True, "tail": "no server lifecycle"}]}

    def verify(self, project_dir: str, cfg: Dict) -> Dict:
        steps = _smoke(project_dir)
        checkable = [s for s in steps if s.get("ok") is not None]
        return {"ok": all(s["ok"] for s in checkable) if checkable else None, "steps": steps}

    def destroy(self, project_dir: str, cfg: Dict) -> Dict:
        return {"ok": None, "steps": []}


def _allok(steps: List[Dict]) -> Optional[bool]:
    chk = [s for s in steps if s.get("ok") is not None]
    return all(s["ok"] for s in chk) if chk else None


class KubernetesProvider(DeploymentProvider):
    name = "kubernetes"

    def _manifests(self, project_dir: str) -> Optional[str]:
        for rel in ("k8s", "kubernetes", "manifests", "deploy/k8s", "deploy/kubernetes"):
            p = os.path.join(project_dir, rel)
            if os.path.isdir(p):
                return p
        for rel in ("deployment.yaml", "k8s.yaml", "deploy.yaml"):
            if os.path.exists(os.path.join(project_dir, rel)):
                return rel
        return None

    def detect(self, project_dir, cfg):
        return _which("kubectl") and self._manifests(project_dir) is not None

    def apply(self, project_dir, cfg):
        m = self._manifests(project_dir)
        steps = [_run(["kubectl", "apply", "-f", m], project_dir, timeout=int(cfg.get("timeout", 900)))] if m else []
        return {"ok": _allok(steps), "steps": steps}

    def verify(self, project_dir, cfg):
        steps = [_run(["kubectl", "get", "all"], project_dir, timeout=120)]
        out = {"ok": _allok(steps), "steps": steps}
        out["steps"] += _smoke(project_dir)
        return out

    def destroy(self, project_dir, cfg):
        m = self._manifests(project_dir)
        steps = [_run(["kubectl", "delete", "-f", m, "--ignore-not-found"], project_dir, timeout=600)] if m else []
        return {"ok": _allok(steps), "steps": steps}


class HelmProvider(DeploymentProvider):
    name = "helm"

    def _chart(self, project_dir: str) -> Optional[str]:
        for rel in (".", "chart", "helm", "deploy/helm"):
            p = os.path.join(project_dir, rel)
            if os.path.exists(os.path.join(p, "Chart.yaml")):
                return p
        return None

    def _release(self, cfg) -> str:
        return str(cfg.get("release") or cfg.get("name") or "app")

    def detect(self, project_dir, cfg):
        return _which("helm") and self._chart(project_dir) is not None

    def apply(self, project_dir, cfg):
        c = self._chart(project_dir)
        steps = [_run(["helm", "upgrade", "--install", self._release(cfg), c],
                      project_dir, timeout=int(cfg.get("timeout", 900)))] if c else []
        return {"ok": _allok(steps), "steps": steps}

    def verify(self, project_dir, cfg):
        steps = [_run(["helm", "status", self._release(cfg)], project_dir, timeout=120)]
        out = {"ok": _allok(steps), "steps": steps}
        out["steps"] += _smoke(project_dir)
        return out

    def destroy(self, project_dir, cfg):
        steps = [_run(["helm", "uninstall", self._release(cfg)], project_dir, timeout=600)]
        return {"ok": _allok(steps), "steps": steps}


class CommandProvider(DeploymentProvider):
    """Generic escape hatch for any tool (terraform, ansible, k8s, paas, installer)."""
    name = "command"

    def detect(self, project_dir: str, cfg: Dict) -> bool:
        cmds = cfg.get("commands") or {}
        return bool(cmds.get("apply") or cmds.get("verify"))

    def _phase(self, project_dir: str, cfg: Dict, key: str) -> Dict:
        cmds = (cfg.get("commands") or {}).get(key) or []
        steps = []
        for c in cmds:
            cmd = c if isinstance(c, list) else str(c).split()
            if cmd:
                steps.append(_run(cmd, project_dir, timeout=int(cfg.get("timeout", 900))))
        checkable = [s for s in steps if s.get("ok") is not None]
        return {"ok": all(s["ok"] for s in checkable) if checkable else None, "steps": steps}

    def apply(self, project_dir: str, cfg: Dict) -> Dict:
        return self._phase(project_dir, cfg, "apply")

    def verify(self, project_dir: str, cfg: Dict) -> Dict:
        out = self._phase(project_dir, cfg, "verify")
        out["steps"] += _smoke(project_dir)
        return out

    def destroy(self, project_dir: str, cfg: Dict) -> Dict:
        return self._phase(project_dir, cfg, "destroy")


class TerraformProvider(DeploymentProvider):
    name = "terraform"

    def _dir(self, project_dir: str) -> Optional[str]:
        for rel in ("infra", "terraform", "deploy/terraform", "."):
            p = os.path.join(project_dir, rel)
            if os.path.isdir(p) and any(f.endswith(".tf") for f in os.listdir(p)):
                return p
        return None

    def detect(self, project_dir, cfg):
        return _which("terraform") and self._dir(project_dir) is not None

    def apply(self, project_dir, cfg):
        d = self._dir(project_dir)
        steps = []
        if not d:
            return {"ok": None, "steps": steps}
        steps.append(_run(["terraform", "init", "-input=false"], d, timeout=600))
        plan = _run(["terraform", "plan", "-input=false", "-out=tfplan"], d, timeout=600)
        steps.append(plan)
        if plan.get("ok"):
            steps.append(_run(["terraform", "apply", "-input=false", "-auto-approve", "tfplan"],
                              d, timeout=int(cfg.get("timeout", 1800))))
        return {"ok": _allok(steps), "steps": steps}

    def verify(self, project_dir, cfg):
        d = self._dir(project_dir)
        steps = [_run(["terraform", "output", "-json"], d, timeout=120)] if d else []
        out = {"ok": _allok(steps), "steps": steps}
        out["steps"] += _smoke(project_dir)
        return out

    def destroy(self, project_dir, cfg):
        d = self._dir(project_dir)
        steps = [_run(["terraform", "destroy", "-input=false", "-auto-approve"], d, timeout=1800)] if d else []
        return {"ok": _allok(steps), "steps": steps}


class AnsibleProvider(DeploymentProvider):
    name = "ansible"

    def _playbook(self, project_dir: str) -> Optional[str]:
        for rel in ("playbook.yml", "playbook.yaml", "ansible/playbook.yml", "deploy/playbook.yml"):
            if os.path.exists(os.path.join(project_dir, rel)):
                return rel
        return None

    def detect(self, project_dir, cfg):
        return _which("ansible-playbook") and self._playbook(project_dir) is not None

    def apply(self, project_dir, cfg):
        pb = self._playbook(project_dir)
        steps = []
        if not pb:
            return {"ok": None, "steps": steps}
        steps.append(_run(["ansible-playbook", "--check", pb], project_dir, timeout=600))
        steps.append(_run(["ansible-playbook", pb], project_dir, timeout=int(cfg.get("timeout", 1800))))
        return {"ok": _allok(steps), "steps": steps}

    def verify(self, project_dir, cfg):
        return {"ok": None, "steps": _smoke(project_dir)}

    def destroy(self, project_dir, cfg):
        pb = self._playbook(project_dir)
        steps = [_run(["ansible-playbook", pb, "--tags", "destroy"], project_dir, timeout=1800)] if pb else []
        return {"ok": _allok(steps), "steps": steps}


class VendorProvider(DeploymentProvider):
    """Wraps core.vendor_adapters for a named vendor target (data + commands + lab)."""
    def __init__(self, name: str):
        self.name = name

    def _adapter(self):
        from core.vendor_adapters import VendorAdapter
        return VendorAdapter(self.name)

    def detect(self, project_dir, cfg):
        return True

    def _cfg(self, cfg):
        v = cfg.get("vendor")
        return v if isinstance(v, dict) else cfg

    def apply(self, project_dir, cfg):
        return self._adapter().apply(project_dir, self._cfg(cfg))

    def verify(self, project_dir, cfg):
        return self._adapter().verify(project_dir, self._cfg(cfg))

    def destroy(self, project_dir, cfg):
        return self._adapter().destroy(project_dir, self._cfg(cfg))


# Registry: named targets -> provider. CommandProvider covers everything configurable.
_REGISTRY: Dict[str, DeploymentProvider] = {
    "docker": DockerProvider(),
    "local": LocalProvider(),
    "command": CommandProvider(),
    "kubernetes": KubernetesProvider(), "k8s": KubernetesProvider(),
    "helm": HelmProvider(),
    "terraform": TerraformProvider(),
    "ansible": AnsibleProvider(),
    # Config-driven escape hatch for anything else.
    "chef": CommandProvider(), "puppet": CommandProvider(),
    "paas": CommandProvider(), "installer": CommandProvider(),
    "aws": CommandProvider(), "gcp": CommandProvider(), "azure": CommandProvider(),
}

# Vendor targets (VMware/HPE/Dell/Cisco/NetApp/DBs/cloud) -> vendor adapters.
for _v in ("vmware", "dell", "hp", "cisco", "netapp", "s3", "aws", "azure", "gcp",
           "postgres", "oracle"):
    _REGISTRY[_v] = VendorProvider(_v)


def select_provider(project_dir: str, cfg: Dict) -> Optional[DeploymentProvider]:
    target = str(cfg.get("target") or "").strip().lower()
    if target and target in _REGISTRY:
        return _REGISTRY[target]
    # auto-detect: k8s -> helm -> terraform -> ansible -> docker -> command -> local
    for name in ("kubernetes", "helm", "terraform", "ansible", "docker", "command", "local"):
        prov = _REGISTRY[name]
        if prov.detect(project_dir, cfg):
            return prov
    return None


def run_deploy_up(project_dir: str, deploy_cfg: Optional[Dict] = None) -> Dict:
    """Bring the app up (apply -> verify) WITHOUT tearing it down (for UI/e2e tests)."""
    cfg = deploy_cfg if deploy_cfg is not None else load_deploy_cfg(project_dir)
    provider = select_provider(project_dir, cfg)
    if provider is None:
        return {"ran": False, "reason": "no applicable deployment provider",
                "provider": None, "passed": None, "steps": []}
    steps: List[Dict] = []
    ok = None
    try:
        applied = provider.apply(project_dir, cfg)
        steps += applied.get("steps", [])
        if applied.get("ok") is False:
            ok = False
        else:
            verified = provider.verify(project_dir, cfg)
            steps += verified.get("steps", [])
            ok = verified.get("ok")
        # Vendors / labs declared in docs/infra.json (external verification policy).
        try:
            from core.vendor_adapters import run_vendors
            vres = run_vendors(project_dir)
            for v in vres:
                steps.append({"step": f"vendor:{v['vendor']}", "ok": v.get("apply", {}).get("ok"),
                              "detail": f"verification={v.get('verification')} "
                                        f"lab={v.get('lab_handle') or '-'}"})
        except Exception:
            pass
    except Exception as e:
        ok = False
        steps.append({"step": "apply", "ok": False, "error": str(e)})
    checkable = [s for s in steps if s.get("ok") is not None]
    passed = all(s["ok"] for s in checkable) if checkable else ok
    return {"ran": True, "provider": provider.name, "passed": passed,
            "cfg": cfg, "steps": steps}


def run_deploy_down(project_dir: str, deploy_cfg: Optional[Dict] = None,
                    provider_name: Optional[str] = None) -> Dict:
    """Tear the app down (destroy) for the previously selected provider."""
    cfg = deploy_cfg if deploy_cfg is not None else load_deploy_cfg(project_dir)
    provider = _REGISTRY.get(provider_name) if provider_name else select_provider(project_dir, cfg)
    if provider is None:
        return {"ran": False, "reason": "no applicable deployment provider", "steps": []}
    steps: List[Dict] = []
    try:
        destroyed = provider.destroy(project_dir, cfg)
        steps += destroyed.get("steps", [])
    except Exception as e:
        steps.append({"step": "destroy", "ok": False, "error": str(e)})
    checkable = [s for s in steps if s.get("ok") is not None]
    return {"ran": True, "provider": provider.name,
            "passed": all(s["ok"] for s in checkable) if checkable else None, "steps": steps}


def run_deploy(project_dir: str, deploy_cfg: Optional[Dict] = None) -> Dict:
    """Apply -> verify -> destroy via the selected provider (guarded)."""
    up = run_deploy_up(project_dir, deploy_cfg)
    if not up.get("ran"):
        return {"ran": False, "reason": up.get("reason", "no applicable deployment provider"),
                "steps": [], "passed": None}
    steps: List[Dict] = list(up.get("steps", []))
    try:
        down = run_deploy_down(project_dir, up.get("cfg"), up.get("provider"))
        steps += down.get("steps", [])
    except Exception:
        pass
    checkable = [s for s in steps if s.get("ok") is not None]
    passed = all(s["ok"] for s in checkable) if checkable else None
    return {"ran": True, "provider": up.get("provider"), "passed": passed, "steps": steps}
