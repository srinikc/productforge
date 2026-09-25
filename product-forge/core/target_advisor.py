"""
Target advisor (dynamic deployment/delivery targets).

Derives a RANKED shortlist of targets from context instead of a flat catalog:
  - product idea / project.json (delivery surface: web|mobile|desktop|cli|api)
  - tech stack (docs/tech-stack.json -> kind/frameworks)
  - architect infra.json (compute/storage/vendors/environments/packaging)
  - product/marketing signals (docs/product-plan.md, design.md, requirements.md)
  - explicit user/end-customer constraints (project.json deploy.target)  [authoritative]

Precedence: explicit > recommendation > default. HIL confirms; the full catalog
is always available ("show all"). Emits docs/targets.md + docs/targets.json.
"""
import json
import os
import re
from typing import Any, Dict, List

_CATALOG = None


def _catalog():
    global _CATALOG
    if _CATALOG is None:
        from core.target_selector import CATALOG
        _CATALOG = CATALOG
    return _CATALOG


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


def _signals(project_dir: str, project: str) -> Dict[str, Any]:
    cfg = _json(os.path.join(project_dir, "project.json"))
    ts = _json(os.path.join(project_dir, "docs", "tech-stack.json"))
    infra = _json(os.path.join(project_dir, "docs", "infra.json"))
    chosen = ts.get("chosen") or {}
    text = " ".join([
        str(cfg.get("idea") or ""),
        _read(os.path.join(project_dir, "docs", "product-plan.md")),
        _read(os.path.join(project_dir, "docs", "design.md")),
        _read(os.path.join(project_dir, "docs", "requirements.md")),
    ]).lower()
    return {"cfg": cfg, "chosen": chosen, "infra": infra, "text": text,
            "explicit": str((cfg.get("deploy") or {}).get("target") or "").strip().lower(),
            "scale": str((cfg.get("sizing") or {}).get("scale") or "").lower()}


def _surface(s: Dict[str, Any]) -> str:
    kind = str(s["chosen"].get("kind") or "").lower()
    fw = " ".join(str(x).lower() for x in (s["chosen"].get("frameworks") or []))
    langs = " ".join(str(x).lower() for x in (s["chosen"].get("languages") or []))
    blob = f"{kind} {fw} {langs}"
    if any(k in blob for k in ("react native", "flutter", "swift", "kotlin", "android", "ios", "mobile")):
        return "mobile"
    if any(k in blob for k in ("electron", "tauri", "desktop", "wpf", "winforms")):
        return "desktop"
    if "cli" in blob or "command-line" in s["text"]:
        return "cli"
    if "library" in blob or kind == "library":
        return "library"
    if any(k in blob for k in ("express", "fastapi", "django", "flask", "api", "service", "grpc")):
        return "api"
    if any(k in blob for k in ("react", "vue", "angular", "svelte", "next", "web")):
        return "web"
    return "web"


def recommend(project_dir: str, project: str = "") -> Dict[str, Any]:
    s = _signals(project_dir, project)
    surface = _surface(s)
    micro = bool(re.search(r"microservice", json.dumps(s["chosen"]) + s["text"], re.I))
    scale = s["scale"] or ("medium" if micro else "small")
    infra = s["infra"]
    compute = str(infra.get("compute") or "").lower()
    vendors = [str(v).lower() for v in (infra.get("vendors") or [])]
    wants_cloud = any(k in compute for k in ("aws", "gcp", "azure", "cloud")) or \
        any(v in ("aws", "gcp", "azure", "s3") for v in vendors)
    wants_k8s = "kubernetes" in compute or "k8s" in compute or micro or scale in ("medium", "large")

    cands: List[Dict[str, Any]] = []

    def add(key, reason, priority):
        cands.append({"key": key, "reason": reason, "priority": priority})

    if surface in ("web", "api"):
        add("docker", f"{surface} service — simplest reproducible run", 40)
        if wants_k8s:
            add("kubernetes", f"scale={scale}/microservices → k8s orchestration", 70)
            add("helm", "package/release onto the cluster", 60)
        if wants_cloud:
            for c in ("aws", "gcp", "azure"):
                if c in compute or c in vendors:
                    add(c, f"architect infra indicates {c} (managed hosting)", 80)
        if surface == "web":
            add("local", "static/dev preview", 20)
    elif surface == "mobile":
        add("command", "mobile: build + submit via CI (App Store / Play Store)", 60)
        add("local", "local device/simulator run", 30)
    elif surface == "desktop":
        add("remote-windows", "desktop installer target (Windows host)", 50)
        add("local", "local build/install", 30)
    elif surface in ("cli", "library"):
        add("local", "no server substrate (binary/package)", 40)
        add("docker", "optional container distribution", 20)
    else:
        add("local", "default", 30)
        add("docker", "containerized run", 40)

    # architect-declared deploy is a strong signal — map it to a KNOWN target key.
    decl_raw = str((infra.get("deploy") or "")).lower()
    keys = {c["key"] for c in _catalog()}
    decl = ""
    for k in keys:
        if re.search(rf"\b{re.escape(k)}\b", decl_raw):
            decl = k
            break
    if not decl:
        for kw, key in (("argocd", "kubernetes"), ("blue-green", "kubernetes"),
                        ("kubectl", "kubernetes"), ("k8s", "kubernetes"),
                        ("compose", "docker"), ("ecs", "aws"), ("eks", "aws"),
                        ("lambda", "aws"), ("gke", "gcp"), ("aks", "azure")):
            if kw in decl_raw:
                decl = key
                break
    if decl:
        add(decl, "declared in architect infra.json", 90)

    # rank: priority desc, dedupe
    seen, ranked = set(), []
    for c in sorted(cands, key=lambda x: -x["priority"]):
        if c["key"] in seen:
            continue
        seen.add(c["key"])
        ranked.append(c)
    default = s["explicit"] or (ranked[0]["key"] if ranked else "local")

    rec = {"project": project or os.path.basename(os.path.normpath(project_dir)),
           "delivery_surface": surface, "scale": scale,
           "recommended": ranked[:5], "default": default,
           "explicit": s["explicit"], "full_catalog": [c["key"] for c in _catalog()],
           "signals": {"kind": s["chosen"].get("kind"), "infra_compute": compute,
                       "vendors": vendors, "cloud": wants_cloud, "k8s": wants_k8s}}
    _write(project_dir, rec)
    return rec


def present(rec: Dict[str, Any]) -> str:
    lines = [f"Recommended deployment targets (delivery surface: {rec['delivery_surface']}):"]
    for i, c in enumerate(rec["recommended"], 1):
        star = " (default)" if c["key"] == rec["default"] else ""
        lines.append(f"  {i}. {c['key']:<16} {c['reason']}{star}")
    lines.append(f"  {len(rec['recommended']) + 1}. show all {len(rec['full_catalog'])} targets / custom")
    return "\n".join(lines)


def _write(project_dir: str, rec: Dict):
    d = os.path.join(project_dir, "docs")
    try:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "targets.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)
        lines = [f"# Deployment / Delivery Targets — {rec['project']}", "",
                 f"- delivery surface: **{rec['delivery_surface']}** · scale: {rec['scale']}",
                 f"- recommended default: **{rec['default']}**", "",
                 "| # | Target | Why |", "|---|---|---|"]
        for i, c in enumerate(rec["recommended"], 1):
            lines.append(f"| {i} | {c['key']} | {c['reason']} |")
        lines += ["", f"Full catalog ({len(rec['full_catalog'])}): "
                      f"{', '.join(rec['full_catalog'])}"]
        with open(os.path.join(d, "targets.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass
