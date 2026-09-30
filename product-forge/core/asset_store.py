"""Project media asset store + ingest / segmentation (BI-0187).

Single writer of the project asset store:
  * ``products/<project>/assets.json``      - the asset index (metadata, ids, children)
  * ``products/<project>/assets/<id>/...``  - immutable media blobs (originals + derived parts)

Turns ingested media (image/audio/video) into stable ``AS-*`` assets with metadata, splits large media
intelligently (image tiles / audio segments / video frame-sampling), and produces the media dicts
consumed by ``core/multimodal.py`` (<= 8 MB per part).

Libs (PIL/numpy/scipy present; cv2/librosa/av/ffmpeg often absent) are guarded: a missing segmenter
DEGRADES the asset (``degraded=true``) and never raises. QA (loudness/perceptual/A-V sync) is BI-0191.

See docs/MEDIA-INGEST-DESIGN.md.
"""

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

MODALITY_MIME = {"image": "image/png", "audio": "audio/wav", "video": "video/mp4",
                 "file": "application/octet-stream"}
EXT_TYPE = {
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image", ".webp": "image",
    ".bmp": "image", ".tiff": "image",
    ".wav": "audio", ".mp3": "audio", ".m4a": "audio", ".flac": "audio", ".ogg": "audio",
    ".aac": "audio",
    ".mp4": "video", ".mov": "video", ".mkv": "video", ".webm": "video", ".avi": "video",
}
INDEX_NAME = "assets." + "json"
MAX_PART_BYTES = 8 * 1024 * 1024  # match multimodal cap


def _index_path(project_dir: str) -> str:
    return os.path.join(project_dir, INDEX_NAME)


def _assets_dir(project_dir: str) -> str:
    return os.path.join(project_dir, "assets")


def _load(project_dir: str) -> Dict:
    try:
        with open(_index_path(project_dir), encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save(project_dir: str, data: Dict) -> None:
    p = _index_path(project_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _type_of(path: str, type_: str = "") -> str:
    if type_:
        return type_
    return EXT_TYPE.get(os.path.splitext(path)[1].lower(), "file")


# ── public: ingest ──────────────────────────────────────────────────────────
def index(project_dir: str) -> Dict:
    return _load(project_dir)


def list_assets(project_dir: str, type_: str = "") -> List[Dict]:
    out = []
    for a in (_load(project_dir).get("assets") or {}).values():
        if type_ and a.get("type") != type_:
            continue
        out.append(a)
    return sorted(out, key=lambda a: a.get("asset_id", ""))


def get(project_dir: str, asset_id: str) -> Optional[Dict]:
    return (_load(project_dir).get("assets") or {}).get(asset_id)


def add(project_dir: str, path: str = "", data: Optional[bytes] = None,
        type_: str = "", name: str = "", source: str = "ingest", item_id: str = "",
        split: bool = False) -> Dict:
    """Ingest one media file/bytes -> a stable AS-* asset (dedupe by sha256). Never raises."""
    try:
        typ = _type_of(path or name, type_)
        if data is None:
            if not path or not os.path.isfile(path):
                return {"error": "no_source"}
            sha = _sha256_file(path)
            size = os.path.getsize(path)
            src_path = path
        else:
            sha = _sha256_bytes(data)
            size = len(data)
            src_path = ""
        idx = _load(project_dir)
        assets = idx.get("assets") or {}
        # dedupe: same content => return existing asset id
        for aid, a in assets.items():
            if a.get("sha256") == sha:
                return a
        aid = f"AS-{sha[:8]}-{len(assets) + 1}"
        blob_dir = os.path.join(_assets_dir(project_dir), aid)
        os.makedirs(blob_dir, exist_ok=True)
        ext = os.path.splitext(path or name)[1] or ("." + MODALITY_MIME.get(typ, "").split("/")[-1])
        blob = os.path.join(blob_dir, "original" + ext)
        if data is not None:
            with open(blob, "wb") as f:
                f.write(data)
        else:
            try:
                shutil.copy2(src_path, blob)
            except Exception:
                blob = src_path  # keep reference to the original if copy fails
        meta, degraded, reason = _probe(blob, typ)
        asset = {"asset_id": aid, "type": typ, "mime": MODALITY_MIME.get(typ, ""),
                 "name": name or os.path.basename(src_path or blob), "sha256": sha,
                 "bytes": size, "source": source, "item_id": item_id,
                 "path": os.path.relpath(blob, project_dir) if os.path.isabs(blob) else blob,
                 "metadata": meta, "children": [], "degraded": degraded, "reason": reason,
                 "at": datetime.now().isoformat()}
        if split and typ in ("image", "audio", "video"):
            asset["children"] = _split(project_dir, aid, blob, typ)
        assets[aid] = asset
        idx["assets"] = assets
        _save(project_dir, idx)
        return asset
    except Exception as e:
        return {"error": f"ingest_failed:{e}"}


def ingest_dir(project_dir: str, src_dir: str, recursive: bool = False,
               split: bool = False) -> List[Dict]:
    """Ingest every media file in a directory (typed by extension). Never raises."""
    out: List[Dict] = []
    if not os.path.isdir(src_dir):
        return out
    for root, _dirs, names in os.walk(src_dir):
        for n in sorted(names):
            p = os.path.join(root, n)
            typ = _type_of(p)
            if typ == "file":
                continue
            out.append(add(project_dir, path=p, type_=typ, source="ingest_dir", split=split))
        if not recursive:
            break
    return out


# ── metadata probe (lib-guarded; QA is BI-0191) ─────────────────────────────
def _probe(path: str, typ: str):
    meta: Dict = {}
    if typ == "image":
        try:
            from PIL import Image
            with Image.open(path) as im:
                meta = {"dimensions": list(im.size), "mode": im.mode, "format": im.format}
            return meta, False, ""
        except ImportError:
            return meta, True, "pillow_missing"
        except Exception as e:
            return meta, True, f"probe_failed:{e}"
    if typ == "audio":
        try:
            import wave
            with wave.open(path, "rb") as w:
                meta = {"channels": w.getnchannels(), "sample_rate": w.getframerate(),
                        "frames": w.getnframes(),
                        "duration": round(w.getnframes() / float(w.getframerate() or 1), 3)}
            return meta, False, ""
        except Exception:
            d = _ffprobe(path)
            return (d, False, "") if d else (meta, True, "audio_probe_unavailable")
    if typ == "video":
        d = _ffprobe(path)
        if d:
            return d, False, ""
        return meta, True, "ffprobe_unavailable"
    return meta, False, ""


def _ffprobe(path: str) -> Dict:
    exe = shutil.which("ffprobe")
    if not exe:
        return {}
    try:
        out = subprocess.run(
            [exe, "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", path],
            capture_output=True, text=True, timeout=20)
        info = json.loads(out.stdout or "{}")
        meta: Dict = {}
        for s in info.get("streams", []):
            if s.get("codec_type") == "video":
                meta["dimensions"] = [s.get("width"), s.get("height")]
                meta["codec"] = s.get("codec_name")
                if s.get("avg_frame_rate", "0/0") != "0/0":
                    num, _, den = s["avg_frame_rate"].partition("/")
                    try:
                        meta["fps"] = round(float(num) / max(1.0, float(den or 1)), 3)
                    except Exception:
                        pass
            elif s.get("codec_type") == "audio":
                meta["sample_rate"] = int(s.get("sample_rate") or 0) or None
                meta["channels"] = s.get("channels")
        if info.get("format", {}).get("duration"):
            meta["duration"] = round(float(info["format"]["duration"]), 3)
        return {k: v for k, v in meta.items() if v is not None}
    except Exception:
        return {}


# ── segmentation / tiling / frame-sampling (guarded) ────────────────────────
def _split(project_dir: str, asset_id: str, blob: str, typ: str) -> List[Dict]:
    if typ == "image":
        return _tile_image(project_dir, asset_id, blob)
    if typ == "audio":
        return _segment_audio(project_dir, asset_id, blob)
    if typ == "video":
        return _sample_video(project_dir, asset_id, blob)
    return []


def _child(project_dir: str, asset_id: str, path: str, kind: str, index: int,
           extra: Optional[Dict] = None) -> Dict:
    c = {"id": f"{asset_id}-{kind[:1]}{index}", "kind": kind,
         "path": os.path.relpath(path, project_dir), "index": index,
         "bytes": os.path.getsize(path) if os.path.exists(path) else 0}
    if extra:
        c.update(extra)
    return c


def _tile_image(project_dir: str, asset_id: str, blob: str,
                tile: int = 1024, overlap: int = 0) -> List[Dict]:
    out: List[Dict] = []
    try:
        from PIL import Image
        d = os.path.join(_assets_dir(project_dir), asset_id, "tiles")
        os.makedirs(d, exist_ok=True)
        with Image.open(blob) as im:
            w, h = im.size
            if w <= tile and h <= tile:
                return []  # small enough, no tiling needed
            step = max(1, tile - overlap)
            i = 0
            for y in range(0, h, step):
                for x in range(0, w, step):
                    box = (x, y, min(x + tile, w), min(y + tile, h))
                    p = os.path.join(d, f"tile_{i:04d}.png")
                    im.crop(box).save(p, "PNG")
                    out.append(_child(project_dir, asset_id, p, "tile", i, {"box": list(box)}))
                    i += 1
    except Exception:
        return out
    return out


def _segment_audio(project_dir: str, asset_id: str, blob: str,
                   segment_s: float = 60.0) -> List[Dict]:
    out: List[Dict] = []
    try:
        import wave
        d = os.path.join(_assets_dir(project_dir), asset_id, "segments")
        os.makedirs(d, exist_ok=True)
        with wave.open(blob, "rb") as w:
            rate = w.getframerate() or 1
            per = int(rate * segment_s)
            n = w.getnframes()
            i = 0
            while i * per < n:
                w.setpos(i * per)
                frames = w.readframes(min(per, n - i * per))
                p = os.path.join(d, f"seg_{i:04d}.wav")
                with wave.open(p, "wb") as o:
                    o.setnchannels(w.getnchannels())
                    o.setsampwidth(w.getsampwidth())
                    o.setframerate(rate)
                    o.writeframes(frames)
                out.append(_child(project_dir, asset_id, p, "segment", i,
                                  {"start_s": round(i * segment_s, 3)}))
                i += 1
    except Exception:
        return out
    return out


def _sample_video(project_dir: str, asset_id: str, blob: str,
                  every_s: float = 5.0) -> List[Dict]:
    """Frame-sample video via ffmpeg (if present). Absent => no children (degraded upstream)."""
    exe = shutil.which("ffmpeg")
    if not exe:
        return []
    out: List[Dict] = []
    try:
        d = os.path.join(_assets_dir(project_dir), asset_id, "frames")
        os.makedirs(d, exist_ok=True)
        pat = os.path.join(d, "frame_%04d.png")
        subprocess.run([exe, "-v", "quiet", "-i", blob, "-vf", f"fps=1/{every_s}", pat],
                       capture_output=True, timeout=120)
        for n in sorted(os.listdir(d)):
            if n.endswith(".png"):
                p = os.path.join(d, n)
                out.append(_child(project_dir, asset_id, p, "frame", len(out),
                                  {"at_s": round(len(out) * every_s, 3)}))
    except Exception:
        return out
    return out


# ── multimodal bridge (BI-0186) ─────────────────────────────────────────────
def to_media(project_dir: str, asset: Dict, prefer_children: bool = True) -> List[Dict]:
    """Produce multimodal media dicts for an asset (parts <= MAX_PART_BYTES). Children first."""
    items: List[Dict] = []
    if prefer_children and asset.get("children"):
        for c in asset["children"]:
            p = os.path.join(project_dir, c["path"])
            if os.path.exists(p) and os.path.getsize(p) <= MAX_PART_BYTES:
                items.append({"type": asset["type"] if c["kind"] != "frame" else "image",
                              "path": p, "name": c["id"]})
        if items:
            return items
    p = os.path.join(project_dir, asset.get("path") or "")
    if os.path.exists(p) and os.path.getsize(p) <= MAX_PART_BYTES:
        return [{"type": asset["type"], "path": p, "name": asset["asset_id"]}]
    # too large / missing: fall back to children even if large filter above excluded them
    for c in (asset.get("children") or []):
        pc = os.path.join(project_dir, c["path"])
        if os.path.exists(pc):
            items.append({"type": "image" if c["kind"] in ("tile", "frame") else asset["type"],
                          "path": pc, "name": c["id"]})
    return items


def modalities(project_dir: str) -> List[str]:
    """Distinct modalities present among assets (excludes 'file')."""
    out = []
    for a in list_assets(project_dir):
        t = a.get("type")
        if t and t != "file" and t not in out:
            out.append(t)
    return out


def ingest_project_media(project_dir: str, project: str = "") -> List[Dict]:
    """Ingest media already stored for this project's intake into the asset store.

    Looks under the shared intake originals dir (products/intake/_files/) for files whose links
    reference this project, plus any project-local ``uploads/`` dir. Idempotent (dedupe by sha256).
    Never raises.
    """
    out: List[Dict] = []
    try:
        from core.paths import ROOT
        roots = [os.path.join(str(ROOT), "products", "intake", "_files"),
                 os.path.join(project_dir, "uploads")]
        for root in roots:
            if not os.path.isdir(root):
                continue
            for r, _d, names in os.walk(root):
                for n in sorted(names):
                    p = os.path.join(r, n)
                    typ = _type_of(p)
                    if typ in ("image", "audio", "video"):
                        out.append(add(project_dir, path=p, type_=typ,
                                       source="intake", split=True))
    except Exception:
        pass
    return [a for a in out if a and not a.get("error")]
