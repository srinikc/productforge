"""
Sizing / footprint report.

Computes the **resource footprint** the product needs — CPU, memory, disk (and
GPU when relevant) — for **monolithic** or **microservices** deployments, per
environment (dev/staging/prod), for docker/kubernetes or similar.

Heuristics are conservative and overridable via `project.json → sizing`.
Persists: products/<project>/docs/sizing.md and docs/sizing.json.
"""
import json
import os
import re
from typing import Any, Dict, List

# per-service baselines (small instance)
_BASE = {"cpu": 0.5, "mem_mb": 512, "disk_gb": 2}
_DB = {"cpu": 2.0, "mem_mb": 4096, "disk_gb": 20}
_CACHE = {"cpu": 0.5, "mem_mb": 1024, "disk_gb": 5}
_SCALE = {"small": 1.0, "medium": 2.0, "large": 4.0}
_ENV = {"dev": 0.5, "staging": 1.0, "prod": 2.0}   # prod also gets HA replicas
_GPU_RE = re.compile(r"\b(gpu|cuda|inference|tensor|machine learning|\bml\b)\b", re.I)


def _read(p: str) -> str:
    try:
        return open(p, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""


def _json(p: str) -> Dict:
    try:
        return json.load(open(p, encoding="utf-8")) or {}
    except Exception:
        return {}


def compute(project_dir: str, project: str = "") -> Dict[str, Any]:
    ts = _json(os.path.join(project_dir, "docs", "tech-stack.json"))
    chosen = ts.get("chosen") or {}
    arch = _read(os.path.join(project_dir, "docs", "architecture.md"))
    reqs = _read(os.path.join(project_dir, "docs", "requirements.md"))
    cfg = (_json(os.path.join(project_dir, "project.json")).get("sizing") or {})

    kind = str(chosen.get("kind") or "web-app").lower()
    services = re.findall(r"^\s*[-*]\s+\*{0,2}([A-Za-z][\w ./+-]{1,40})", arch, re.M)
    _metric = re.compile(r"token|cost|match|align|avoid|score|percent|%|latency|throughput|"
                         r"input|output|cached|reasoning|total|budget|time|count|rate", re.I)
    services = [s.strip() for s in services if not _metric.search(s)][:12]
    micro = (kind in ("service", "microservice", "microservices")
             or bool(re.search(r"\bmicroservice", arch, re.I))
             or len(services) >= 5)
    scale = str(cfg.get("scale") or ("medium" if micro else "small")).lower()
    needs_db = bool(re.search(r"database|postgres|mysql|sqlite|sql\b", arch + reqs, re.I))
    needs_cache = bool(re.search(r"redis|cache|queue|kafka|rabbit", arch + reqs, re.I))
    needs_gpu = bool(_GPU_RE.search(arch + " " + reqs))

    def shard(replicas=1, extra=None):
        r = dict(_BASE)
        if extra:
            r["cpu"] += extra.get("cpu", 0)
            r["mem_mb"] += extra.get("mem_mb", 0)
            r["disk_gb"] += extra.get("disk_gb", 0)
        r["cpu"] = round(r["cpu"] * replicas, 2)
        return r

    units: List[Dict[str, Any]] = []
    if micro:
        n = max(len(services), 3)
        for s in (services or [f"service-{i+1}" for i in range(n)]):
            units.append({"name": s, **shard()})
    else:
        units.append({"name": "app (monolith)", **shard()})
    if needs_db:
        units.append({"name": "database", **dict(_DB)})
    if needs_cache:
        units.append({"name": "cache/queue", **dict(_CACHE)})

    envs: Dict[str, Dict[str, Any]] = {}
    for env, mult in _ENV.items():
        replicas = 2 if env == "prod" else 1
        cpu = round(sum(u["cpu"] for u in units) * _SCALE.get(scale, 1.0) * mult * replicas, 2)
        mem = round(sum(u["mem_mb"] for u in units) * _SCALE.get(scale, 1.0) * mult * replicas)
        disk = round(sum(u["disk_gb"] for u in units) * mult * replicas, 1)
        envs[env] = {"cpu_cores": cpu, "memory_mb": mem, "disk_gb": disk,
                     "replicas": replicas, "gpu": (1 if needs_gpu else 0)}

    out = {"project": project or os.path.basename(os.path.normpath(project_dir)),
           "deployment_model": "microservices" if micro else "monolithic",
           "scale": scale, "gpu_required": needs_gpu,
           "units": units, "environments": envs,
           "orchestration": ["docker-compose"] if not micro else ["kubernetes", "helm"],
           "notes": cfg.get("notes") or ""}
    _write(project_dir, out)
    return out


def _write(project_dir: str, data: Dict):
    d = os.path.join(project_dir, "docs")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "sizing.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    lines = [f"# Sizing / Footprint — {data['project']}", "",
             f"- model: **{data['deployment_model']}** · scale: {data['scale']} · "
             f"GPU: {'yes' if data['gpu_required'] else 'no'}",
             f"- orchestration: {', '.join(data['orchestration'])}", "",
             "| Unit | CPU (cores) | Memory (MB) | Disk (GB) |", "|---|---|---|---|"]
    for u in data["units"]:
        lines.append(f"| {u['name']} | {u['cpu']} | {u['mem_mb']} | {u['disk_gb']} |")
    lines += ["", "| Env | Replicas | CPU (cores) | Memory (MB) | Disk (GB) | GPU |",
              "|---|---|---|---|---|---|"]
    for env, e in data["environments"].items():
        lines.append(f"| {env} | {e['replicas']} | {e['cpu_cores']} | {e['memory_mb']} | "
                     f"{e['disk_gb']} | {e['gpu']} |")
    lines += ["", "> Heuristics; override via `project.json → sizing` "
                  "(scale, notes, explicit resources)."]
    with open(os.path.join(d, "sizing.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
