"""Diagram renderer: ```mermaid blocks -> .mmd (+ .svg/.png/.pdf when a renderer exists).

Single concern: extract mermaid fences from an artifact and render them with a real
renderer, selected via env ``PIPELINE_DIAGRAM_RENDERER`` (default ``auto``):

  1. ``mmdc`` (mermaid-cli) found on PATH.
  2. **Kroki** (network): POST https://kroki.io/mermaid/{svg,png}; the response is
     written only after its SVG/PNG magic is verified -- never fabricated.
  3. **Bundled draw.io desktop CLI** resolved relative to the repo
     (``.opencode/tools/drawio/draw.io.exe``), exported with
     ``--export --format <fmt> --crop --output <out> <in>``. draw.io >= 31 reads
     Mermaid (.mmd/.mermaid) directly, so the always-written .mmd is the input when
     no sibling ``<base>.drawio`` source exists.
  4. Fallback: write the ``.mmd`` source only and report why in ``reason``.

The ``.mmd`` source is **always** written (it is extracted, not generated). The report
``renderer`` field is the renderer actually used, else ``"unavailable"``.

Env:
  PIPELINE_DIAGRAM_RENDERER = auto | off | mmdc | kroki | drawio   (default: auto)
  PIPELINE_DRAWIO_CLI       = explicit path to the draw.io CLI      (overrides bundled)

Owner store (single writer = this module):
  products/<project>/artifacts/<stage>/diagrams/*.mmd  -- extracted mermaid source
  ...*.svg / *.png / *.pdf / *.drawio                  -- only when a renderer emits them
"""
try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import os
import re
import shutil
import subprocess
from typing import Dict, List, Tuple

_FENCE_RE = re.compile(r"```[ \t]*mermaid[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)
_TIMEOUT = 180
_KROKI_TIMEOUT = 30
_KROKI_BASE = "https://kroki.io/mermaid"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_REPO_ROOT = str(_PF_ROOT)
_BUNDLED_DRAWIO = os.path.join(_REPO_ROOT, ".opencode", "tools", "drawio", "draw.io.exe")
_MODES = ("off", "kroki", "mmdc", "drawio", "auto")


def extract_mermaid(text: str) -> List[str]:
    """Return the body of every ```mermaid fenced block (stripped)."""
    return [m.strip() for m in _FENCE_RE.findall(text or "") if m and m.strip()]


def _which(*names: str) -> str:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return ""


def _mode() -> str:
    m = (os.environ.get("PIPELINE_DIAGRAM_RENDERER") or "auto").strip().lower()
    return m if m in _MODES else "auto"


def _drawio_cli() -> str:
    env = (os.environ.get("PIPELINE_DRAWIO_CLI") or "").strip()
    if env and os.path.exists(env):
        return env
    if os.path.exists(_BUNDLED_DRAWIO):
        return _BUNDLED_DRAWIO
    return _which("drawio", "draw.io", "drawio.exe")


def _cmd(exe: str, args: List[str]) -> List[str]:
    cmd = [exe] + list(args)
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c"] + cmd
    return cmd


def _run(cmd: List[str]) -> bool:
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=_TIMEOUT)
    except Exception:
        return False
    return True


def _is_svg(data: bytes) -> bool:
    head = data[:4096].lstrip()
    return head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in data[:4096])


def _is_png(data: bytes) -> bool:
    return data[:8] == _PNG_MAGIC


def _is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def _verify(path: str, check) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except Exception:
        return False
    return bool(head) and check(head)


def _kroki_url(fmt: str) -> str:
    return f"{_KROKI_BASE}/{fmt}"


def _http_post(url: str, body: str, timeout: int = _KROKI_TIMEOUT):
    """POST text/plain and return the response bytes, or None on any failure.

    This is the monkeypatch seam used by the tests; it never raises.
    """
    try:
        import requests
        r = requests.post(url, data=body.encode("utf-8"),
                          headers={"Content-Type": "text/plain"}, timeout=timeout)
        if r.status_code == 200:
            return r.content
        return None
    except Exception:
        pass
    try:
        import urllib.request
        req = urllib.request.Request(url, data=body.encode("utf-8"),
                                     headers={"Content-Type": "text/plain"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if getattr(resp, "status", 200) == 200:
                return resp.read()
    except Exception:
        pass
    return None


def _render_kroki(block: str, base: str) -> Tuple[List[str], List[str]]:
    produced, missing = [], []
    for fmt, check in (("svg", _is_svg), ("png", _is_png)):
        out = base + "." + fmt
        data = _http_post(_kroki_url(fmt), block)
        if data and check(data):
            try:
                with open(out, "wb") as f:
                    f.write(data)
                produced.append(out)
                continue
            except Exception:
                pass
        missing.append(out)
    return produced, missing


def _render_mmdc(mmdc: str, mmd: str, base: str) -> Tuple[List[str], List[str]]:
    produced, missing = [], []
    for fmt, check in (("svg", _is_svg), ("pdf", _is_pdf)):
        out = base + "." + fmt
        if _run(_cmd(mmdc, ["-i", mmd, "-o", out])) and _verify(out, check):
            produced.append(out)
        else:
            missing.append(out)
    return produced, missing


def _render_drawio(cli: str, mmd: str, base: str) -> Tuple[List[str], List[str]]:
    src = base + ".drawio"
    inp = src if os.path.exists(src) else mmd
    produced, missing = [], []
    for fmt, check in (("svg", _is_svg), ("pdf", _is_pdf)):
        out = base + "." + fmt
        cmd = _cmd(cli, ["--export", "--format", fmt, "--crop", "--disable-update",
                         "--output", out, inp])
        if _run(cmd) and _verify(out, check):
            produced.append(out)
        else:
            missing.append(out)
    return produced, missing


def _try(cand: str, block: str, mmd: str, base: str, mmdc: str, drawio_cli: str):
    if cand == "mmdc" and mmdc:
        return _render_mmdc(mmdc, mmd, base)
    if cand == "kroki":
        return _render_kroki(block, base)
    if cand == "drawio" and drawio_cli:
        return _render_drawio(drawio_cli, mmd, base)
    return [], []


def render(project_dir: str, stage, artifact_path: str) -> Dict:
    """Extract + (best-effort) render every mermaid block in an artifact.

    Returns a report dict: {"renderer", "count", "mmd", "rendered", "missing", "reason"}.
    """
    report: Dict = {"renderer": "unavailable", "count": 0, "mmd": [], "rendered": [],
                    "missing": [], "reason": ""}
    try:
        with open(artifact_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except Exception as e:
        report["reason"] = f"cannot read artifact: {e}"
        return report

    blocks = extract_mermaid(text)
    report["count"] = len(blocks)
    if not blocks:
        report["reason"] = "no mermaid blocks"
        return report

    stem = os.path.splitext(os.path.basename(artifact_path))[0]
    from core import stage_paths as _sp
    out_dir = os.path.join(_sp.find_stage_dir(project_dir, str(stage)), "diagrams")
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception as e:
        report["reason"] = f"cannot create diagrams dir: {e}"
        return report

    mode = _mode()
    mmdc = _which("mmdc", "mmdc.cmd")
    drawio_cli = _drawio_cli()
    if mode == "auto":
        cands = (["mmdc"] if mmdc else []) + ["kroki"] + (["drawio"] if drawio_cli else [])
    elif mode == "off":
        cands = []
    else:
        cands = [mode]

    chosen = ""
    for i, block in enumerate(blocks, 1):
        base = os.path.join(out_dir, f"{stem}-{i}")
        mmd = base + ".mmd"
        try:
            with open(mmd, "w", encoding="utf-8") as f:
                f.write(block + "\n")
            report["mmd"].append(mmd)
        except Exception:
            continue

        order = ([chosen] if chosen else []) + [c for c in cands if c != chosen]
        for cand in order:
            produced, missing = _try(cand, block, mmd, base, mmdc, drawio_cli)
            report["missing"].extend(missing)
            if produced:
                chosen = cand
                report["rendered"].extend(produced)
                break

    if chosen:
        report["renderer"] = chosen
    elif mode == "off":
        report["reason"] = ("rendering disabled (PIPELINE_DIAGRAM_RENDERER=off); "
                            ".mmd source written only")
    elif mode == "auto":
        report["reason"] = ("no usable renderer (mmdc/kroki/drawio); "
                            ".mmd source written only")
    else:
        report["reason"] = (f"requested renderer '{mode}' produced no output; "
                            ".mmd source written only")
    return report
