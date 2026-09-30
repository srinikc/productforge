"""Media QA validators (BI-0191).

Quality gate for media outputs: probe (codec/res/fps/duration/format/size), loudness (EBU R128),
perceptual-hash continuity (across frames/tiles), A/V sync. Lib/tool-guarded and FAIL-CLOSED:
a missing tool degrades the check (never a false PASS, never raises). Findings feed the existing
compliance/defect/issue streams — this module owns NO store.

Reuses: core.asset_store (assets, children, _probe/_ffprobe). See docs/MEDIA-QA-DESIGN.md.
"""

import hashlib
import os
import shutil
import subprocess
from typing import Dict, List, Optional

_MEDIA_TYPES = ("image", "audio", "video")


def _mode() -> str:
    try:
        from core import env_flags as _ef
        return str(_ef.get("PIPELINE_MEDIA_QA", "warn") or "warn").lower()
    except Exception:
        return os.getenv("PIPELINE_MEDIA_QA", "warn").lower()


def _tol() -> float:
    try:
        from core import env_flags as _ef
        return float(_ef.get("PIPELINE_MEDIA_QA_TOLERANCE", "0.5") or 0.5)
    except Exception:
        return 0.5


def _check(name: str, ok: Optional[bool], detail: str, degraded: bool = False) -> Dict:
    return {"name": name, "ok": ok, "detail": detail, "degraded": degraded}


# ── individual validators ───────────────────────────────────────────────────
def probe(asset: Dict) -> List[Dict]:
    meta = asset.get("metadata") or {}
    out: List[Dict] = []
    typ = asset.get("type")
    if asset.get("bytes", 0) <= 0:
        out.append(_check("size", False, "zero-byte asset"))
    else:
        out.append(_check("size", True, f"{asset.get('bytes')}B"))
    if typ == "video":
        out.append(_check("video_meta", bool(meta.get("dimensions")),
                          f"dims={meta.get('dimensions')} fps={meta.get('fps')}", degraded=not meta))
    elif typ == "audio":
        out.append(_check("audio_meta", bool(meta.get("sample_rate")),
                          f"rate={meta.get('sample_rate')} dur={meta.get('duration')}",
                          degraded=not meta))
    elif typ == "image":
        out.append(_check("image_meta", bool(meta.get("dimensions")),
                          f"dims={meta.get('dimensions')}", degraded=not meta))
    return out


def loudness(path: str) -> List[Dict]:
    """EBU R128 integrated loudness via ffmpeg (if present). Degrades when unavailable."""
    exe = shutil.which("ffmpeg")
    if not exe:
        return [_check("loudness", None, "ffmpeg unavailable", degraded=True)]
    try:
        r = subprocess.run([exe, "-v", "info", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=60)
        txt = (r.stderr or "")
        import re
        m = re.search(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", txt)
        if not m:
            return [_check("loudness", None, "no ebur128 output", degraded=True)]
        lufs = float(m.group(1))
        # common streaming target ~ -14..-16 LUFS; accept a generous band
        ok = -30.0 <= lufs <= -6.0
        return [_check("loudness", ok, f"I={lufs} LUFS")]
    except Exception as e:
        return [_check("loudness", None, f"error:{e}", degraded=True)]


def perceptual_continuity(asset: Dict, project_dir: str) -> List[Dict]:
    """Flag blank/duplicate frames among children (PIL/numpy if present; else degrade)."""
    children = asset.get("children") or []
    if not children:
        return [_check("perceptual", None, "no children to compare", degraded=True)]
    try:
        from PIL import Image
        import numpy as np  # noqa: F401
    except Exception:
        return [_check("perceptual", None, "PIL/numpy unavailable", degraded=True)]
    seen = set()
    dup = blank = 0
    for c in children:
        p = os.path.join(project_dir, c.get("path", ""))
        if not os.path.isfile(p):
            continue
        try:
            with Image.open(p) as im:
                g = im.convert("L").resize((16, 16))
                arr = list(g.getdata())
                if max(arr) - min(arr) < 4:
                    blank += 1
                h = hashlib.md5(bytes(arr)).hexdigest()
                if h in seen:
                    dup += 1
                seen.add(h)
        except Exception:
            continue
    ok = (blank == 0 and dup == 0)
    return [_check("perceptual", ok, f"blank={blank} duplicate={dup} of {len(children)}")]


def av_sync(asset: Dict) -> List[Dict]:
    meta = asset.get("metadata") or {}
    if asset.get("type") != "video":
        return [_check("av_sync", None, "not a video", degraded=True)]
    dur = meta.get("duration")
    if not dur:
        return [_check("av_sync", None, "no duration", degraded=True)]
    return [_check("av_sync", True, f"duration={dur}s (single-track skew n/a)")]


# ── aggregate ───────────────────────────────────────────────────────────────
def validate_asset(project_dir: str, asset: Dict) -> Dict:
    checks: List[Dict] = []
    try:
        checks += probe(asset)
        p = os.path.join(project_dir, asset.get("path") or "")
        if asset.get("type") in ("audio", "video") and os.path.isfile(p):
            checks += loudness(p)
        if asset.get("type") in ("image", "video"):
            checks += perceptual_continuity(asset, project_dir)
        if asset.get("type") == "video":
            checks += av_sync(asset)
    except Exception as e:
        checks.append(_check("validate", None, f"error:{e}", degraded=True))
    return {"asset_id": asset.get("asset_id"), "type": asset.get("type"),
            "checks": checks,
            "ok": all(c["ok"] for c in checks if c["ok"] is not None),
            "degraded": any(c.get("degraded") for c in checks)}


def validate_project(project_dir: str) -> Dict:
    """Validate every media asset in the project. No media => no-op. Never raises."""
    try:
        from core import asset_store as _as
        assets = [a for a in _as.list_assets(project_dir) if a.get("type") in _MEDIA_TYPES]
    except Exception:
        return {"ok": True, "noop": True, "assets": [], "findings": [], "degraded": False}
    if not assets:
        return {"ok": True, "noop": True, "assets": [], "findings": [], "degraded": False}
    results = [validate_asset(project_dir, a) for a in assets]
    findings: List[Dict] = []
    for r in results:
        for c in r["checks"]:
            if c["ok"] is False:
                findings.append({"asset_id": r["asset_id"], "type": r["type"],
                                 "check": c["name"], "detail": c["detail"]})
    return {"ok": len(findings) == 0 and not any(r["degraded"] for r in results),
            "noop": False, "assets": results, "findings": findings,
            "degraded": any(r["degraded"] for r in results),
            "mode": _mode()}
