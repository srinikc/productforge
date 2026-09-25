"""Multi-modal support — detect a project's modalities and resolve the right models.

Today the LLM catalog is **text-in/text-out** plus **media IN** (image/audio/video) on 65
models; **media OUT** needs separate **generator** models (image/video/TTS/3D). This module:
  * detects the project's modalities from the idea/context,
  * lists catalog models that ACCEPT a modality (input),
  * flags which media OUT modalities have NO generator available yet (needs registration).

Owner: this module (pure). Wired in pipeline_executor (logged at preflight).
"""
import os
import re
from typing import Dict, List

from core import model_catalog as mc

MODALITIES = ("text", "image", "audio", "video", "3d", "sensor")

_SIGNALS = {
    "audio": ("voice", "speech", "tts", "stt", "wake word", "audio", "spoken", "listen"),
    "video": ("video", "animation", "animate", "sora", "movie", "clip", "reel"),
    "image": ("image", "photo", "picture", "logo", "illustration", "render", "draw", "poster"),
    "3d": ("3d", "cad", "autocad", "mesh", "revit", "bim", "building", "floor plan", "blueprint"),
    "sensor": ("sensor", "iot", "telemetry", "device data", "embedded", "firmware"),
}


def detect(text: str) -> List[str]:
    """Modalities implied by the idea/context (always includes 'text')."""
    t = (text or "").lower()
    out = ["text"]
    for mod, sigs in _SIGNALS.items():
        if any(s in t for s in sigs):
            out.append(mod)
    return out


def models_for_input(modality: str, limit: int = 8) -> List[str]:
    """Catalog models that ACCEPT this modality as input."""
    return [n for n, m in (mc.load() or {}).items()
            if modality in (m.get("input_modalities") or [])][:limit]


def models_for_output(modality: str, limit: int = 8) -> List[str]:
    """Catalog models that EMIT this modality (today: text only)."""
    return [n for n, m in (mc.load() or {}).items()
            if modality in (m.get("output_modalities") or [])][:limit]


def generators_needed(modalities: List[str]) -> List[str]:
    """Media-OUT modalities with no available generator model (must be registered)."""
    need = []
    for m in modalities:
        if m == "text":
            continue
        if not models_for_output(m):
            need.append(m)
    return need


def capabilities_for_project(idea: str) -> Dict:
    mods = detect(idea)
    return {"modalities": mods,
            "input_models": {m: models_for_input(m) for m in mods if m != "text"},
            "output_models": {m: models_for_output(m) for m in mods},
            "generators_needed": generators_needed(mods)}


def _main(argv=None) -> int:
    import argparse, json
    ap = argparse.ArgumentParser(description="Multi-modal capability detection")
    ap.add_argument("--idea", required=True)
    a = ap.parse_args(argv)
    print(json.dumps(capabilities_for_project(a.idea), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
