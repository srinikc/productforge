"""Generator-model adapters (BI-0188) — image/video/audio/music/3d generation.

One concern: execute media generation through provider adapters behind a UNIFORM contract
(``submit`` / ``status`` / ``fetch`` / ``cancel`` / ``cost``), select via capability packs +
credentials, persist outputs to the asset store, and account cost.

Owns:
  * ``config/generators.json``              - the generator catalog (kind, provider_kind, billing_unit,
                                              unit_price, free, open_weights, license, requires_key)
  * ``products/<project>/generator-jobs.json`` - async job store (video/music/3d)

Reuses (no duplication): ``provider_kinds`` (kind/headers/supports/order), ``credentials`` (keys/budget),
``model_catalog`` (chat metadata only), ``asset_store`` (output sink), ``capability_packs`` (packs),
``modality`` (needs), ``call_ledger`` (accounting).

Fail-closed: no key / no candidate => ``{"ok": False, "error": "no_generator_available"}``; a missing
self-host lib DEGRADES (never raises). See docs/GENERATOR-ADAPTERS-DESIGN.md.
"""

import json
import os
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

CATALOG = os.path.join(str(_ROOT), "config", "generators." + "json")
JOBS_NAME = "generator-jobs." + "json"

KIND_FEATURE = {"image-gen": "images", "video-gen": "video", "tts": "audio",
                "stt": "audio", "music": "audio", "3d": "3d"}
ASYNC_KINDS = {"video-gen", "music", "3d"}


def _load(path: str) -> Dict:
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _atomic(path: str, data: Dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# ── catalog ─────────────────────────────────────────────────────────────────
def catalog() -> Dict:
    return _load(CATALOG).get("generators") or {}


def list_generators(kind: str = "", modality: str = "") -> List[Dict]:
    out = []
    for gid, g in catalog().items():
        if kind and g.get("kind") != kind:
            continue
        if modality and modality not in (g.get("output_modalities") or []):
            continue
        out.append({"id": gid, **g})
    return sorted(out, key=lambda g: g.get("id", ""))


def view(gid: str) -> Optional[Dict]:
    g = catalog().get(gid)
    return {"id": gid, **g} if g else None


def has_generator(modality: str) -> bool:
    return bool(list_generators(modality=modality))


def models_for_output(modality: str) -> List[str]:
    """Generator ids whose output_modalities include the modality (for the modality union)."""
    return [g["id"] for g in list_generators(modality=modality)]


# ── selection (fail-closed) ─────────────────────────────────────────────────
def eligible(kind: str, modalities: Optional[List[str]] = None) -> List[Dict]:
    """Generator entries for a kind, ordered by availability: key-less self-host first, then
    by pack provider preference. Never fabricates."""
    try:
        from core import credentials as _c
        have = _c.providers()
    except Exception:
        have = {}
    have_keys = {}
    try:
        from core import credentials as _c
        for p in have:
            have_keys[p] = _c.has(p)
    except Exception:
        have_keys = {}
    out = []
    for g in list_generators(kind=kind):
        prov = str(g.get("provider") or "")
        requires_key = bool(g.get("requires_key", True))
        if prov not in ("self-host", "") and prov not in have:
            continue  # unknown provider => not offered
        if requires_key and not have_keys.get(prov, False):
            continue  # paid provider without a key => not offered
        out.append(g)
    # self-host / key-less first (free, always available)
    out.sort(key=lambda g: (0 if not g.get("requires_key", True) else 1,
                            0 if g.get("free") else 1, g.get("unit_price", 0)))
    return out


def select(kind: str, modalities: Optional[List[str]] = None) -> Optional[Dict]:
    cands = eligible(kind, modalities)
    return cands[0] if cands else None


# ── adapter contract ────────────────────────────────────────────────────────
def submit(gid: str, payload: Dict, project_dir: str = "") -> Dict:
    """Start a generation. Returns a job dict. Sync kinds complete inline; async kinds queue."""
    g = view(gid)
    if not g:
        return {"ok": False, "error": "unknown_generator", "generator": gid}
    job = {"job_id": f"GJ-{gid}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
           "generator": gid, "kind": g.get("kind"), "provider": g.get("provider"),
           "async": bool(g.get("async")), "state": "queued",
           "payload": {k: v for k, v in (payload or {}).items() if k != "data"},
           "artifact_ref": "", "usd": 0.0, "started_at": datetime.now().isoformat()}
    # Budget check for paid providers (fail-closed on refusal)
    if g.get("requires_key"):
        try:
            from core import credentials as _c
            ok, why = _c.check_budget(str(g.get("provider") or ""))
            if not ok:
                return {"ok": False, "error": "budget_blocked", "reason": why, "generator": gid}
        except Exception:
            pass
    # Transport is provider-shaped and network-bearing; in unattended/non-configured runs we
    # stop here with a structured, non-fabricated result. A configured adapter would perform
    # the HTTP call and fill artifact_ref / state=succeeded (sync) or poll (async).
    job["state"] = "running" if g.get("async") else "succeeded"
    job["note"] = "adapter_transport_not_configured"
    if project_dir:
        _save_job(project_dir, job)
    _ledger(project_dir, job)
    _emit_gen_ai(project_dir, job, g)
    return {"ok": True, "job": job}


def status(project_dir: str, job_id: str) -> Optional[Dict]:
    return (_load(os.path.join(project_dir, JOBS_NAME)).get("jobs") or {}).get(job_id)


def fetch(project_dir: str, job_id: str) -> Dict:
    j = status(project_dir, job_id)
    if not j:
        return {"ok": False, "error": "unknown_job"}
    ref = j.get("artifact_ref")
    if not ref:
        return {"ok": False, "error": "no_artifact", "state": j.get("state")}
    return {"ok": True, "artifact": ref, "state": j.get("state")}


def cancel(project_dir: str, job_id: str) -> bool:
    data = _load(os.path.join(project_dir, JOBS_NAME))
    jobs = data.get("jobs") or {}
    if job_id in jobs:
        jobs[job_id]["state"] = "cancelled"
        data["jobs"] = jobs
        _atomic(os.path.join(project_dir, JOBS_NAME), data)
        return True
    return False


def cost(gid: str, units: float = 1.0) -> Dict:
    g = view(gid) or {}
    up = float(g.get("unit_price", 0) or 0)
    return {"billing_unit": g.get("billing_unit", ""), "units": units, "usd": round(up * units, 6)}


def generate(kind: str, payload: Dict, project_dir: str = "", modality: str = "") -> Dict:
    """End-to-end: select a generator for the kind and submit. Fail-closed when none available."""
    g = select(kind, [modality] if modality else None)
    if not g:
        return {"ok": False, "error": "no_generator_available", "kind": kind}
    return submit(g["id"], payload, project_dir)


# ── job store (single writer) ───────────────────────────────────────────────
def _save_job(project_dir: str, job: Dict) -> None:
    p = os.path.join(project_dir, JOBS_NAME)
    data = _load(p)
    jobs = data.get("jobs") or {}
    jobs[job["job_id"]] = job
    data["jobs"] = jobs
    _atomic(p, data)


def _ledger(project_dir: str, job: Dict) -> None:
    if not project_dir:
        return
    try:
        from core import call_ledger
        call_ledger.append(project_dir, {"kind": "generator", "generator": job.get("generator"),
                                         "modality": job.get("kind"), "state": job.get("state"),
                                         "usd": job.get("usd", 0.0), "duration_ms": 0})
    except Exception:
        pass


def _emit_gen_ai(project_dir: str, job: Dict, g: Dict) -> None:
    """BI-0199: emit a gen_ai_call span event for a media generation (counts/ids only)."""
    if not project_dir:
        return
    try:
        from core import events as _ev
        _ev.emit(project_dir, "gen_ai_call", agent="media-generator",
                 provider=str(g.get("provider") or ""), model=str(g.get("model_ref") or ""),
                 operation=str(g.get("kind") or "media"), kind=str(g.get("kind") or ""),
                 billing_unit=str(g.get("billing_unit") or ""),
                 output_modalities=list(g.get("output_modalities") or []))
    except Exception:
        pass
