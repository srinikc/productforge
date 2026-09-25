"""Dynamic artifact-format policy (BI-0110).

Single concern: decide, per project + agent + artifact kind, WHICH output formats to
emit for a generated artifact, then derive the extra formats from the canonical ``.md``.

Owner store (single writer = this module): ``config/artifact-formats.json``.

Rules (owner decision):
  * ``.md`` is the canonical default for EVERY artifact and is always emitted first.
  * Extra formats (pdf/docx/xlsx/pptx/html/svg) are chosen dynamically per project and
    artifact type, then filtered by emitter availability (``capability_fallback``).
  * Derived formats are GENERATED, never hand-edited, and degrade gracefully: an
    unavailable emitter is dropped and reported, never a hard failure.
"""
import json
import os
import re
from typing import Dict, List

__all__ = ["formats_for", "emit", "content_candidates"]

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "artifact-formats.json")

_DEFAULT_CONFIG = {
    "default": ["md"],
    "by_agent": {},
    "by_kind": {},
    "project_overrides": {},
    "capability_fallback": True,
}

_PDF_STRATEGY_CACHE = None

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
body{{font-family:-apple-system,'Segoe UI',Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 16px;line-height:1.55;color:#1a1a1a}}
table{{border-collapse:collapse}}th,td{{border:1px solid #ccc;padding:4px 8px}}
pre{{background:#f5f5f5;padding:10px;overflow:auto}}code{{background:#f5f5f5}}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _load_config() -> Dict:
    """Read the single source of truth; sane defaults when missing/corrupt."""
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            merged = dict(_DEFAULT_CONFIG)
            merged.update(data)
            return merged
    except Exception:
        pass
    return dict(_DEFAULT_CONFIG)


def _is_sep_row(line: str) -> bool:
    if line.count("|") < 2:
        return False
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells)


def _has_markdown_table(text: str) -> bool:
    lines = (text or "").splitlines()
    for i in range(len(lines) - 1):
        if lines[i].count("|") >= 2 and _is_sep_row(lines[i + 1]):
            return True
    return False


def _has_mermaid(text: str) -> bool:
    return bool(re.search(r"```[ \t]*mermaid", text or "", re.IGNORECASE))


def content_candidates(content: str) -> List[str]:
    """Extra formats implied by the artifact's CONTENT (dynamic heuristics)."""
    out: List[str] = []
    if _has_markdown_table(content):
        out.append("xlsx")
    if _has_mermaid(content):
        out.append("svg")
    return out


def _importable(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _pdf_strategy() -> str:
    """Return the working PDF backend ('reportlab'|'pdf_generator') or ''.

    ``core/pdf_generator`` auto-detects WeasyPrint first, whose native libs are
    broken in this environment (libgobject missing), so prefer reportlab when present.
    """
    global _PDF_STRATEGY_CACHE
    if _PDF_STRATEGY_CACHE is not None:
        return _PDF_STRATEGY_CACHE
    strategy = ""
    if _importable("reportlab"):
        strategy = "reportlab"
    else:
        try:
            from core.pdf_generator import PDFGenerator
            try:
                PDFGenerator()
                strategy = "pdf_generator"
            except Exception:
                strategy = ""
        except Exception:
            strategy = ""
    _PDF_STRATEGY_CACHE = strategy
    return strategy


def _emitter_available(fmt: str) -> bool:
    fmt = (fmt or "").strip().lower()
    if fmt in ("md", "html"):
        return True
    if fmt == "pdf":
        return bool(_pdf_strategy())
    if fmt == "docx":
        return _importable("docx")
    if fmt == "xlsx":
        return _importable("openpyxl")
    if fmt == "pptx":
        return _importable("pptx")
    return False


def _strip_md(s: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s or "")
    return s.replace("**", "").replace("__", "").replace("`", "").strip()


def _title(md: str) -> str:
    for line in (md or "").splitlines():
        m = re.match(r"^#\s+(.*)$", line.strip())
        if m:
            return _strip_md(m.group(1)) or "Artifact"
    return "Artifact"


def _minimal_md_to_html(md: str) -> str:
    import html as _html
    out = []
    for line in (md or "").splitlines():
        s = line.rstrip()
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            n = len(m.group(1))
            out.append(f"<h{n}>{_html.escape(_strip_md(m.group(2)))}</h{n}>")
        elif not s.strip():
            out.append("<br/>")
        else:
            out.append(f"<p>{_html.escape(s)}</p>")
    return "\n".join(out)


def _markdown_to_html(md: str) -> str:
    try:
        import markdown as _markdown
        return _markdown.markdown(md or "", extensions=["tables", "fenced_code", "sane_lists"])
    except Exception:
        return _minimal_md_to_html(md)


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _emit_html(md: str, out_path: str, md_path: str = "") -> str:
    _write_text(out_path, _HTML_TEMPLATE.format(title=_title(md), body=_markdown_to_html(md)))
    return out_path


def _reportlab_pdf(md: str, out_path: str) -> str:
    import html as _html
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(out_path, pagesize=letter)
    story = []
    for line in (md or "").splitlines():
        s = line.rstrip()
        if not s.strip():
            story.append(Spacer(1, 6))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            style = styles["Heading1"] if len(m.group(1)) <= 2 else styles["Heading3"]
            story.append(Paragraph(_html.escape(_strip_md(m.group(2))), style))
        else:
            story.append(Paragraph(_html.escape(s), styles["Normal"]))
    doc.build(story)
    return out_path


def _emit_pdf(md: str, out_path: str, md_path: str = "") -> str:
    strategy = _pdf_strategy()
    if strategy == "reportlab":
        return _reportlab_pdf(md, out_path)
    if strategy == "pdf_generator":
        from core.pdf_generator import PDFGenerator
        html = _HTML_TEMPLATE.format(title=_title(md), body=_markdown_to_html(md))
        if PDFGenerator().html_to_pdf(html, out_path):
            return out_path
    raise RuntimeError("no working PDF backend")


def _emit_docx(md: str, out_path: str, md_path: str = "") -> str:
    from docx import Document
    doc = Document()
    for line in (md or "").splitlines():
        s = line.rstrip()
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            doc.add_heading(_strip_md(m.group(2)), level=min(len(m.group(1)), 6))
        elif re.match(r"^\s*[-*+]\s+", s):
            doc.add_paragraph(_strip_md(re.sub(r"^\s*[-*+]\s+", "", s)), style="List Bullet")
        elif re.match(r"^\s*\d+[.)]\s+", s):
            doc.add_paragraph(_strip_md(re.sub(r"^\s*\d+[.)]\s+", "", s)), style="List Number")
        elif s.strip():
            doc.add_paragraph(_strip_md(s))
    doc.save(out_path)
    return out_path


def _split_row(line: str) -> List[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _extract_tables(md: str):
    tables = []
    lines = (md or "").splitlines()
    i = 0
    while i < len(lines):
        if lines[i].count("|") >= 2 and i + 1 < len(lines) and _is_sep_row(lines[i + 1]):
            header = _split_row(lines[i])
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].count("|") >= 2:
                rows.append(_split_row(lines[j]))
                j += 1
            tables.append((header, rows))
            i = j
        else:
            i += 1
    return tables


def _emit_xlsx(md: str, out_path: str, md_path: str = "") -> str:
    tables = _extract_tables(md)
    if not tables:
        raise ValueError("no markdown tables found")
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for idx, (header, rows) in enumerate(tables, 1):
        ws = wb.create_sheet(title=f"Table{idx}")
        if header:
            ws.append([_strip_md(c) for c in header])
        for r in rows:
            ws.append([_strip_md(c) for c in r])
    wb.save(out_path)
    return out_path


def _split_slides(md: str):
    slides = []
    cur_title, cur_body = None, []
    for line in (md or "").splitlines():
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            if cur_title is not None:
                slides.append((cur_title, "\n".join(cur_body).strip()))
            cur_title, cur_body = _strip_md(m.group(2)), []
        elif cur_title is not None:
            cur_body.append(_strip_md(line))
    if cur_title is not None:
        slides.append((cur_title, "\n".join(cur_body).strip()))
    return slides


def _emit_pptx(md: str, out_path: str, md_path: str = "") -> str:
    slides = _split_slides(md)
    if not slides:
        raise ValueError("no heading structure for a deck")
    from pptx import Presentation
    prs = Presentation()
    layout = prs.slide_layouts[1]
    for title, body in slides:
        slide = prs.slides.add_slide(layout)
        slide.shapes.title.text = title or "Slide"
        if len(slide.placeholders) > 1:
            slide.placeholders[1].text = body or ""
    prs.save(out_path)
    return out_path


_EMITTERS = {
    "html": _emit_html,
    "pdf": _emit_pdf,
    "docx": _emit_docx,
    "xlsx": _emit_xlsx,
    "pptx": _emit_pptx,
}


def formats_for(project: str, agent_id: str, stage_id: str = "",
                kind: str = "", content: str = "") -> List[str]:
    """Return the ordered formats to emit for one artifact.

    Decision order: ``default`` (md first) -> global ``by_agent`` -> global ``by_kind``
    -> ``project_overrides`` (take precedence) -> content heuristics -> capability
    fallback (drop formats whose emitter is unavailable).
    """
    cfg = _load_config()
    default = [str(f).lower() for f in (cfg.get("default") or ["md"])]
    by_agent = cfg.get("by_agent") or {}
    by_kind = cfg.get("by_kind") or {}
    extras: List[str] = []

    def add(items):
        for f in items or []:
            f = str(f).strip().lower()
            if f and f not in extras:
                extras.append(f)

    add(by_agent.get(agent_id))
    if kind:
        add(by_kind.get(kind))

    override = (cfg.get("project_overrides") or {}).get(project)
    if isinstance(override, list):
        extras = []
        add(override)
    elif isinstance(override, dict):
        if agent_id in (override.get("by_agent") or {}):
            for f in (by_agent.get(agent_id) or []):
                f = str(f).strip().lower()
                if f in extras:
                    extras.remove(f)
            add((override.get("by_agent") or {}).get(agent_id))
        if kind and kind in (override.get("by_kind") or {}):
            for f in (by_kind.get(kind) or []):
                f = str(f).strip().lower()
                if f in extras:
                    extras.remove(f)
            add((override.get("by_kind") or {}).get(kind))
        add(override.get("formats"))

    add(content_candidates(content))

    ordered: List[str] = []
    for f in default + extras:
        if f not in ordered:
            ordered.append(f)
    if "md" not in ordered:
        ordered.insert(0, "md")

    if cfg.get("capability_fallback", True):
        ordered = [f for f in ordered if f == "md" or _emitter_available(f)]
    return ordered


def emit(project: str, artifact_path, formats, content: str,
         agent_id: str = "") -> Dict:
    """Derive each non-md format from the canonical ``.md``; never fabricate.

    Returns ``{format: path}`` for formats truly written and
    ``{format: {"error": reason}}`` otherwise. The canonical ``.md`` is returned
    unchanged when it exists. One ``[FORMATS]`` line is logged per artifact.
    """
    result: Dict = {}
    emitted: List[str] = []
    skipped: List[str] = []
    artifact_path = str(artifact_path)
    stem = os.path.splitext(artifact_path)[0]

    for fmt in formats or []:
        fmt = str(fmt).strip().lower()
        if fmt == "md":
            if os.path.exists(artifact_path):
                result["md"] = artifact_path
                emitted.append("md")
            else:
                result["md"] = {"error": "canonical md missing"}
                skipped.append("md:canonical md missing")
            continue
        if not _emitter_available(fmt):
            result[fmt] = {"error": "emitter unavailable"}
            skipped.append(f"{fmt}:emitter unavailable")
            continue
        emitter = _EMITTERS.get(fmt)
        if emitter is None:
            result[fmt] = {"error": f"no emitter for '{fmt}'"}
            skipped.append(f"{fmt}:no emitter")
            continue
        out_path = f"{stem}.{fmt}"
        out, err = None, ""
        try:
            out = emitter(content or "", out_path, artifact_path)
        except Exception as exc:
            err = str(exc) or exc.__class__.__name__
        if out and os.path.exists(out) and os.path.getsize(out) > 0:
            result[fmt] = out
            emitted.append(fmt)
        else:
            result[fmt] = {"error": err or "not produced"}
            skipped.append(f"{fmt}:{err or 'not produced'}")

    extras = [f for f in emitted if f != "md"]
    line = f"[FORMATS] {agent_id or '?'}: md"
    if extras:
        line += " + " + ", ".join(extras)
    if skipped:
        line += " (skipped: " + "; ".join(skipped) + ")"
    print(line)
    return result
