"""Intake file ingestion - store original files + extract their text.

The owner (single writer) of the stored intake originals. Any externally captured
document (CustomGPT export, ChatGPT/Claude file, manual drop) is archived verbatim
under ``products/intake/_files/<source>/<ts>_<name>`` and its text is extracted so it
can flow through the ONE intake path (``core.intake.ingest`` -> backlog item).

Extraction is best-effort and never fatal; the original is always kept.
  * text-like (.md .txt .csv .tsv .json .jsonl .yaml .yml .xml .html .rst .log .ini .toml)
  * .pdf   -> pypdf
  * .docx  -> python-docx (paragraphs + tables)
  * .doc   -> legacy Word binary, printable-run scan (low confidence)
  * .rtf   -> control-word strip
  * images / other binaries -> stored only (no OCR); the title/summary is used as body

CLI:
    python -m core.intake_files <path> [--source chatgpt] [--scope project]
                                 [--project X] [--title "..."] [--kind feature]
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
import json
from datetime import datetime

REPO = str(_PF_ROOT)
_FILES_ROOT = os.path.join(REPO, "products", "intake", "_files")

TEXT_EXTS = {".md", ".markdown", ".txt", ".text", ".csv", ".tsv", ".json", ".jsonl",
             ".yaml", ".yml", ".xml", ".html", ".htm", ".rst", ".log", ".ini",
             ".cfg", ".conf", ".toml", ".env", ".srt", ".vtt"}
DOC_EXTS = {".pdf", ".doc", ".docx", ".rtf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".tif", ".tiff"}
MAX_TEXT = 200_000     # extracted-text cap (chars) kept in memory / attached


def _safe_name(name: str) -> str:
    base = os.path.basename(str(name or "").replace("\\", "/")).strip() or "file"
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base)
    return base[:120]


def _ext(name: str) -> str:
    return os.path.splitext(str(name or ""))[1].lower()


def store_dir(source: str = "manual") -> str:
    d = os.path.join(_FILES_ROOT, _safe_name(source or "manual"))
    os.makedirs(d, exist_ok=True)
    return d


def save(source: str, filename: str, data: bytes) -> str:
    """Archive the original bytes; return the repo-relative path."""
    d = store_dir(source)
    p = os.path.join(d, f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{_safe_name(filename)}")
    with open(p, "wb") as f:
        f.write(data if isinstance(data, (bytes, bytearray)) else bytes(data or b""))
    return os.path.relpath(p, REPO).replace("\\", "/")


def _read_text(path: str) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _pdf_text(path: str) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return ""
    out = []
    try:
        for page in PdfReader(path).pages:
            try:
                out.append(page.extract_text() or "")
            except Exception:
                continue
    except Exception:
        return ""
    return "\n".join(out)


def _docx_text(path: str) -> str:
    try:
        import docx  # python-docx
    except Exception:
        return ""
    out = []
    try:
        d = docx.Document(path)
        for p in d.paragraphs:
            if p.text:
                out.append(p.text)
        for t in d.tables:
            for row in t.rows:
                cells = [c.text.strip() for c in row.cells if c.text]
                if cells:
                    out.append(" | ".join(cells))
    except Exception:
        return ""
    return "\n".join(out)


def _doc_text(path: str) -> str:
    """Legacy Word 97-2003 (.doc) best-effort: scan printable runs."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception:
        return ""
    try:
        txt = data.decode("utf-16-le", errors="ignore")
    except Exception:
        txt = ""
    runs = re.findall(r"[ -~\u00A0-\u024F]{4,}", txt)
    best = "\n".join(runs)
    if len(best) < 40:  # fall back to an 8-bit scan of the raw bytes
        best = "\n".join(m.decode("latin-1") for m in re.findall(rb"[ -~]{4,}", data))
    return best


def _rtf_text(path: str) -> str:
    try:
        raw = _read_text(path)
    except Exception:
        return ""
    raw = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", raw)
    raw = raw.replace("{", " ").replace("}", " ")
    return re.sub(r"[ \t]{2,}", " ", raw)


def extract(path: str) -> dict:
    """Extract text from a stored file (best-effort). Never raises."""
    name = os.path.basename(path)
    ext = _ext(name)
    res = {"file": path, "name": name, "ext": ext, "ok": False, "method": "",
           "text": "", "note": ""}
    try:
        if ext in TEXT_EXTS or ext == "":
            res["text"] = _read_text(path)
            res["method"] = "text"
        elif ext == ".pdf":
            res["text"] = _pdf_text(path)
            res["method"] = "pdf"
        elif ext == ".docx":
            res["text"] = _docx_text(path)
            res["method"] = "docx"
        elif ext == ".doc":
            res["text"] = _doc_text(path)
            res["method"] = "doc"
            res["note"] = "legacy .doc: best-effort extraction (low confidence)"
        elif ext == ".rtf":
            res["text"] = _rtf_text(path)
            res["method"] = "rtf"
        elif ext in IMAGE_EXTS:
            res["method"] = "image"
            res["note"] = "image stored (no OCR); title/summary used as body"
        else:
            try:
                res["text"] = _read_text(path)
                res["method"] = "text?"
            except Exception:
                res["method"] = "binary"
                res["note"] = "binary stored (no extraction)"
        res["text"] = (res["text"] or "").strip()[:MAX_TEXT]
        res["ok"] = bool(res["text"]) or res["method"] in ("image", "binary")
    except Exception as e:  # pragma: no cover - defensive
        res["note"] = f"extract failed: {e}"
    return res


def ingest_file(path: str = "", data: bytes = None, filename: str = "",
                source: str = "manual", scope: str = "", project: str = "",
                title: str = "", intent: str = "", kind: str = "") -> dict:
    """Store + extract one file and run it through the intake engine.

    Returns the intake result (backlog item when promoted) with the stored path
    and the extraction metadata attached.
    """
    from core import intake as _intake

    if data is None:
        if not path or not os.path.isfile(path):
            return {"error": f"file not found: {path}"}
        filename = filename or os.path.basename(path)
        with open(path, "rb") as f:
            data = f.read()
    stored = save(source, filename or path or "file", data)
    abs_stored = os.path.join(REPO, stored)
    ex = extract(abs_stored)

    payload = {
        "title": (title or os.path.splitext(os.path.basename(filename or path or "file"))[0])[:200],
        "body": ex.get("text") or "",
        "source": source,
        "attachments": [{"path": stored, "name": ex["name"], "ext": ex["ext"],
                         "method": ex["method"], "note": ex["note"]}],
    }
    if scope:
        payload["scope"] = scope
    if project:
        payload["project"] = project
    if intent:
        payload["intent"] = intent
    if kind:
        payload["kind"] = kind
    if not payload["body"]:
        payload["body"] = f"[{ex.get('method') or 'file'}] {ex['name']}: {ex.get('note') or 'no text extracted'}"

    out = _intake.ingest(source, payload, scope or None, project or None,
                         attachments=payload["attachments"])
    try:
        if isinstance(out, dict):
            out["stored_file"] = stored
            out["extraction"] = {k: ex[k] for k in ("name", "ext", "method", "note", "ok")}
    except Exception:
        pass
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Ingest a file into Product Forge intake.")
    ap.add_argument("path", help="file to ingest (.md/.txt/.pdf/.docx/.doc/.rtf/...)")
    ap.add_argument("--source", default="manual")
    ap.add_argument("--scope", default="")
    ap.add_argument("--project", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--kind", default="")
    ap.add_argument("--intent", default="")
    a = ap.parse_args(argv)
    r = ingest_file(a.path, source=a.source, scope=a.scope, project=a.project,
                    title=a.title, kind=a.kind, intent=a.intent)
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0 if not (isinstance(r, dict) and r.get("error")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
