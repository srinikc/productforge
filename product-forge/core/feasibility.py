"""Two-phase feasibility & capability triage (BI-0214).

Phase 1 (BUILD-HOST, at ideation): probe THIS machine; per required modality decide
``local | api | aggregator`` and emit a ``go | conditional | no-go`` verdict.
Phase 2 (DESTINATION, at packaging): profile where the product runs; decide shipping
``bundle | api | hosted | hybrid`` + SKU, without redoing phase 1.

Single writer of ``products/<project>/feasibility.json``. Reuses (never duplicates): capability need
from ``core.modality``, generator license/free/price from ``core.generator_adapters`` + ``config/generators.json``,
packs from ``core.capability_packs``, keys/budget from ``core.credentials``, tiers from
``config/hardware-tiers.json``, target from ``core.target_advisor``.

Fail-closed & degrade: any probe failure is explicit ``unknown`` + ``degraded``; an unknown host yields
``conditional`` (API fallback), never silent ``go``. Never raises. See docs/FEASIBILITY-TRIAGE-DESIGN.md.
"""

import json
import os
import platform
import shutil
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

try:
    from core.paths import ROOT as _ROOT
except ImportError:  # executed as a script
    import sys as _sys
    _d = os.path.abspath(__file__)
    for _ in range(3):
        _d = os.path.dirname(_d)
        if os.path.isfile(os.path.join(_d, "core", "paths.py")):
            _sys.path.insert(0, _d)
            break
    from core.paths import ROOT as _ROOT

TIERS = os.path.join(str(_ROOT), "config", "hardware-tiers." + "json")
REPORT_NAME = "feasibility." + "json"


def _load(path: str) -> Dict:
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _tiers() -> Dict:
    return _load(TIERS)


def report_path(project_dir: str) -> str:
    return os.path.join(project_dir, REPORT_NAME)


def load_report(project_dir: str) -> Dict:
    return _load(report_path(project_dir))


def save_report(project_dir: str, data: Dict) -> None:
    p = report_path(project_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


# ── host probe (lib/tool-guarded; never raises) ─────────────────────────────
def _ram_gb():
    try:
        import importlib.util
        if importlib.util.find_spec("psutil"):
            import psutil
            return round(psutil.virtual_memory().total / (1024 ** 3), 1), False
    except Exception:
        pass
    try:  # Windows
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = _MS()
        m.dwLength = ctypes.sizeof(_MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return round(m.ullTotalPhys / (1024 ** 3), 1), False
    except Exception:
        pass
    try:  # POSIX
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024 ** 3), 1), False
    except Exception:
        return 0.0, True


def probe_host() -> Dict:
    """Snapshot the machine building the product. Unknown => explicit flags; never raises."""
    reasons: List[str] = []
    host = {"os": f"{platform.system()} {platform.release()}", "machine": platform.machine(),
            "cpu_cores": os.cpu_count() or 0, "ram_gb": 0.0, "disk_free_gb": 0.0,
            "gpu_model": "", "vram_gb": 0.0, "cuda": False,
            "probe_source": "none", "degraded": False, "reasons": reasons}
    ram, d1 = _ram_gb()
    host["ram_gb"] = ram
    if d1:
        reasons.append("ram_unknown"); host["degraded"] = True
    try:
        host["disk_free_gb"] = round(shutil.disk_usage(str(_ROOT)).free / (1024 ** 3), 1)
    except Exception:
        reasons.append("disk_unknown"); host["degraded"] = True
    exe = shutil.which("nvidia-smi")
    if exe:
        try:
            out = subprocess.run(
                [exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10)
            line = (out.stdout or "").strip().splitlines()[0] if out.stdout else ""
            if line:
                parts = [p.strip() for p in line.split(",")]
                host["gpu_model"] = parts[0]
                host["vram_gb"] = round(float(parts[1]) / 1024, 1) if len(parts) > 1 else 0.0
                host["cuda"] = True
                host["probe_source"] = "nvidia-smi"
        except Exception:
            reasons.append("nvidia_smi_failed"); host["degraded"] = True
    else:
        ov = os.getenv("PIPELINE_FEASIBILITY_GPU_OVERRIDE", "")
        if ov:
            try:
                host["vram_gb"] = float(ov); host["cuda"] = True; host["probe_source"] = "override"
            except Exception:
                pass
    return host


# ── shared assessment ───────────────────────────────────────────────────────
def _bundle_allowed(lic: str, open_weights: bool) -> bool:
    permissive = {l.lower() for l in (_tiers().get("permissive_licenses") or [])}
    return bool(open_weights) and str(lic or "").lower() in permissive


def _required_modalities(project_dir: str) -> List[str]:
    try:
        from core import capability_packs as _cp
        prof = _cp.load_profile(project_dir)
        req = prof.get("required_capabilities") or []
        if req:
            return [m for m in req if m != "text"]
    except Exception:
        pass
    try:
        from core import asset_store as _as
        return [m for m in _as.modalities(project_dir) if m != "text"]
    except Exception:
        return []


def _assess_modality(modality: str, host: Dict) -> Dict:
    """Per-modality: pick a generator, check license/host fit, choose build mode."""
    tiers = (_tiers().get("modalities") or {}).get(modality, {})
    need_vram = float(tiers.get("vram_gb", 0) or 0)
    need_ram = float(tiers.get("ram_gb", 0) or 0)
    need_disk = float(tiers.get("disk_gb", 0) or 0)
    row = {"modality": modality, "required": True, "generator": "", "provider_kind": "",
           "license": "", "open_weights": False, "free": False, "requires_key": False,
           "bundle_allowed": False, "build_mode": "api",
           "vram_required_gb": need_vram, "ram_required_gb": need_ram, "disk_required_gb": need_disk,
           "fits_local": False, "reasons": []}
    gen = None
    try:
        from core import generator_adapters as _ga
        gen = _ga.select(_KIND_BY_MODALITY.get(modality, ""), [modality])
        if not gen:
            ids = _ga.models_for_output(modality) or []
            gen = _ga.view(ids[0]) if ids else None
    except Exception:
        gen = None
    if not gen:
        row["reasons"].append("no_generator_available")
        row["build_mode"] = "api"
        return row
    row["generator"] = gen.get("id", "")
    row["provider_kind"] = gen.get("provider_kind", "")
    row["license"] = gen.get("license", "")
    row["open_weights"] = bool(gen.get("open_weights"))
    row["free"] = bool(gen.get("free"))
    row["requires_key"] = bool(gen.get("requires_key", True))
    row["bundle_allowed"] = _bundle_allowed(row["license"], row["open_weights"])
    # local fit: needs self-host (or bundle-able weights) AND host resources
    vram = float(host.get("vram_gb") or 0)
    ram = float(host.get("ram_gb") or 0)
    disk = float(host.get("disk_free_gb") or 0)
    fits = True
    if need_vram > 0 and vram < need_vram:
        fits = False; row["reasons"].append(f"host_vram_{vram:g}<{need_vram:g}")
    if need_ram > 0 and ram and ram < need_ram:
        fits = False; row["reasons"].append(f"host_ram_{ram:g}<{need_ram:g}")
    if need_disk > 0 and disk and disk < need_disk:
        fits = False; row["reasons"].append(f"host_disk_{disk:g}<{need_disk:g}")
    if not row["bundle_allowed"]:
        row["reasons"].append("weights_not_bundle_allowed")
    row["fits_local"] = fits and row["bundle_allowed"]
    # build mode decision (fail-closed: prefer API unless local clearly fits)
    if row["fits_local"]:
        row["build_mode"] = "local"
    elif row["provider_kind"] == "aggregator":
        row["build_mode"] = "aggregator"
    else:
        row["build_mode"] = "api"
    return row


def _verdict(rows: List[Dict], host: Dict) -> Dict:
    reasons: List[str] = []
    risks: List[str] = []
    if host.get("degraded"):
        risks.append("host_probe_degraded")
    blocking = 0
    conditional = 0
    for r in rows:
        if "no_generator_available" in r["reasons"]:
            blocking += 1; reasons.append(f"{r['modality']}: no generator available")
        elif r["build_mode"] in ("api", "aggregator"):
            conditional += 1
            risks.append(f"{r['modality']}: {r['build_mode']} required (local not feasible)")
        else:
            risks.append(f"{r['modality']}: local ok ({r['generator']})")
    if blocking:
        v = "no-go"
    elif conditional:
        v = "conditional"
    else:
        v = "go"
    # unknown host can never be a silent go
    if v == "go" and host.get("degraded"):
        v = "conditional"
    return {"verdict": v, "reasons": reasons, "risks": risks}


_KIND_BY_MODALITY = {"image": "image-gen", "video": "video-gen", "audio": "tts",
                     "3d": "3d", "music": "music"}


# ── phases ──────────────────────────────────────────────────────────────────
def assess_build(project_dir: str, host: Optional[Dict] = None) -> Dict:
    host = host or probe_host()
    mods = _required_modalities(project_dir)
    rows = [_assess_modality(m, host) for m in mods]
    v = _verdict(rows, host)
    return {"host": host, "per_modality": rows, **v}


def assess_destination(project_dir: str, target: str = "", shipping: str = "") -> Dict:
    target = target or ""
    surface = ""
    try:
        from core import target_advisor as _ta
        adv = _ta.recommend(project_dir, os.path.basename(os.path.normpath(project_dir))) or {}
        target = target or adv.get("default", "")
        surface = adv.get("delivery_surface", "")
    except Exception:
        pass
    build = load_report(project_dir).get("phase1_build_host") or {}
    rows = build.get("per_modality") or []
    # shipping: bundle only if ALL required modalities are bundle-allowed; else api/hybrid
    if shipping:
        mode = shipping
    elif any(r.get("build_mode") in ("api", "aggregator") for r in rows):
        mode = "hybrid" if any(r.get("bundle_allowed") for r in rows) else "api"
    else:
        mode = "bundle"
    sku = "thin-api" if mode in ("api", "hosted") else ("hybrid" if mode == "hybrid" else "offline-weights")
    required_keys: List[str] = []
    hardware = {"vram_gb": 0.0, "ram_gb": 0.0, "disk_gb": 0.0}
    for r in rows:
        if r.get("requires_key") and r.get("build_mode") in ("api", "aggregator"):
            required_keys.append(r.get("provider", "") or r.get("generator", ""))
        if mode == "bundle":
            hardware["vram_gb"] = max(hardware["vram_gb"], float(r.get("vram_required_gb") or 0))
            hardware["ram_gb"] = max(hardware["ram_gb"], float(r.get("ram_required_gb") or 0))
            hardware["disk_gb"] = max(hardware["disk_gb"], float(r.get("disk_required_gb") or 0))
    reasons = [] if rows else ["no_build_assessment_to_base_destination_on"]
    v = "no-go" if not rows else ("conditional" if mode in ("api", "hybrid") else "go")
    return {"target": target, "delivery_surface": surface, "shipping_mode": mode, "sku": sku,
            "required_hardware": hardware, "required_keys": [k for k in required_keys if k],
            "per_modality": rows, "verdict": v, "reasons": reasons, "risks": []}


def evaluate(project_dir: str, phase: str = "build", host: Optional[Dict] = None,
             target: str = "", shipping: str = "") -> Dict:
    """Run one phase and merge into feasibility.json (phase-independent; idempotent)."""
    cur = load_report(project_dir)
    data = {"schema": "product-forge/feasibility@1",
            "project": os.path.basename(os.path.normpath(project_dir)),
            "generated_at": datetime.now().isoformat(),
            "item_id": "BI-0214",
            "phase1_build_host": cur.get("phase1_build_host") or {},
            "phase2_destination": cur.get("phase2_destination") or {}}
    if phase == "build":
        data["phase1_build_host"] = assess_build(project_dir, host)
    elif phase == "destination":
        data["phase2_destination"] = assess_destination(project_dir, target=target, shipping=shipping)
    save_report(project_dir, data)
    return data


def verdict(project_dir: str, phase: str = "build") -> Dict:
    data = load_report(project_dir)
    key = "phase1_build_host" if phase == "build" else "phase2_destination"
    v = (data.get(key) or {}).get("verdict", "")
    return {"verdict": v, "phase": phase}
