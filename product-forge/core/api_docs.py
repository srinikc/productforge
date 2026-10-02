"""API reference generator (BI-PF-0355): builds a searchable HTML + structured view from the canonical OpenAPI.

Source of truth is ``api/openapi.json`` (generated from ``api.app`` by API-5 governance). This module renders:
  * a structured reference (groups by tag; method/path/summary/params/request/responses),
  * a self-contained HTML page with a sidebar TOC + client-side search (no external assets),
  * optional PDF via the existing ``core.pdf_generator`` (degrades gracefully).

The HTML is DETERMINISTIC (no timestamps) so ``scripts/dev/api_docs_check.py`` can freshness-gate the committed
``docs/api-reference.html`` against the live OpenAPI.
"""
import html as _html
import os
from typing import Any

from core.paths import ROOT

HTML_PATH = os.path.join(ROOT, "docs", "api-reference.html")
METHODS = ("get", "post", "put", "patch", "delete")


def reference() -> dict[str, Any]:
    """Structured API reference from the live OpenAPI schema."""
    from api.app import app
    spec = app.openapi()
    paths = spec.get("paths") or {}
    groups: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(paths):
        for method, op in sorted((paths[path] or {}).items()):
            if method.lower() not in METHODS:
                continue
            tag = (op.get("tags") or ["other"])[0]
            params = [{"name": p.get("name"), "in": p.get("in"), "required": bool(p.get("required"))}
                      for p in (op.get("parameters") or [])]
            rb = op.get("requestBody") or {}
            content = list((rb.get("content") or {}).keys())
            responses = sorted((op.get("responses") or {}).keys())
            groups.setdefault(tag, []).append({
                "method": method.upper(), "path": path,
                "summary": op.get("summary") or op.get("operationId") or "",
                "operation_id": op.get("operationId") or "",
                "params": params, "request_content": content, "request_required": bool(rb.get("required")),
                "responses": responses})
    info = spec.get("info") or {}
    return {"title": info.get("title") or "Product Forge API",
            "version": info.get("version") or "", "openapi": spec.get("openapi") or "",
            "path_count": len(paths), "operation_count": sum(len(v) for v in groups.values()),
            "groups": [{"tag": t, "endpoints": groups[t]} for t in sorted(groups)]}


def _esc(s: Any) -> str:
    return _html.escape(str(s if s is not None else ""))


def render_html(ref: dict[str, Any]) -> str:
    """Self-contained, searchable HTML with a sidebar TOC (deterministic)."""
    toc = []
    sections = []
    for g in ref["groups"]:
        tag = g["tag"]
        tid = "tag-" + _esc(tag).replace(" ", "-")
        toc.append(f'<a href="#{tid}" class="toc">{_esc(tag)} <span>{len(g["endpoints"])}</span></a>')
        cards = []
        for e in g["endpoints"]:
            method = _esc(e["method"])
            params = "".join(
                f'<tr><td>{_esc(p["name"])}</td><td>{_esc(p["in"])}</td><td>{"yes" if p["required"] else "no"}</td></tr>'
                for p in e["params"]) or '<tr><td colspan="3" class="mut">none</td></tr>'
            req = ", ".join(_esc(c) for c in e["request_content"]) or "—"
            card = (
                f'<div class="ep" data-search="{_esc(e["method"] + " " + e["path"] + " " + e["summary"]).lower()}">'
                f'<div class="ep-head"><span class="m m-{method.lower()}">{method}</span> '
                f'<code class="path">{_esc(e["path"])}</code></div>'
                f'<div class="sum">{_esc(e["summary"] or e["operation_id"])}</div>'
                f'<div class="req">request: {req}{" (required)" if e["request_required"] else ""} · '
                f'responses: {_esc(", ".join(e["responses"]))}</div>'
                f'<table class="params"><tr><th>param</th><th>in</th><th>required</th></tr>{params}</table>'
                f'</div>')
            cards.append(card)
        sections.append(f'<section id="{tid}"><h2>{_esc(tag)}</h2>{"".join(cards)}</section>')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(ref["title"])} - API Reference</title>
<style>
 :root{{--bg:#0f1420;--card:#171e2e;--fg:#e6ebf5;--mut:#9aa7bd;--acc:#6ea8fe;--line:#26304a}}
 *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,Segoe UI,Roboto,Arial}}
 header{{position:sticky;top:0;background:#141b2a;border-bottom:1px solid var(--line);padding:14px 20px;z-index:2}}
 h1{{margin:0;font-size:18px}} .meta{{color:var(--mut);font-size:12px}}
 #q{{margin-top:8px;width:100%;max-width:520px;padding:8px 10px;border-radius:8px;border:1px solid var(--line);background:#0b101a;color:var(--fg)}}
 .layout{{display:flex;gap:0;align-items:flex-start}}
 nav{{position:sticky;top:92px;width:240px;padding:14px;border-right:1px solid var(--line);height:calc(100vh - 92px);overflow:auto}}
 nav .toc{{display:flex;justify-content:space-between;color:var(--fg);text-decoration:none;padding:5px 6px;border-radius:6px}}
 nav .toc:hover{{background:#1c2436}} nav .toc span{{color:var(--mut)}}
 main{{flex:1;padding:16px 22px 60px;max-width:1000px}}
 h2{{border-left:3px solid var(--acc);padding-left:8px;font-size:15px;margin:22px 0 10px}}
 .ep{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:8px 0}}
 .ep-head{{display:flex;align-items:center;gap:8px}} .path{{background:#0b101a;padding:2px 6px;border-radius:5px}}
 .m{{font-size:11px;font-weight:700;padding:2px 7px;border-radius:6px;color:#06122b}}
 .m-get{{background:#2f7d4f}} .m-post{{background:#6ea8fe}} .m-put{{background:#b06a00}} .m-patch{{background:#8a5a00}} .m-delete{{background:#b23b3b}}
 .sum{{color:var(--fg);margin:6px 0}} .mut{{color:var(--mut)}}
 .req{{color:var(--mut);font-size:12px}}
 table.params{{border-collapse:collapse;margin-top:8px;font-size:12px;width:auto}}
 table.params th,table.params td{{border:1px solid var(--line);padding:3px 8px;text-align:left}}
 .hidden{{display:none}}
</style></head><body>
<header><h1>{_esc(ref["title"])}</h1>
 <div class="meta">OpenAPI {_esc(ref["openapi"])} · version {_esc(ref["version"])} · {ref["path_count"]} paths · {ref["operation_count"]} operations</div>
 <input id="q" placeholder="Search endpoints (path, method, summary)..." oninput="filter()">
</header>
<div class="layout">
 <nav>{''.join(toc)}</nav>
 <main id="doc">{''.join(sections)}</main>
</div>
<script>
function filter(){{var q=(document.getElementById('q').value||'').toLowerCase();
 document.querySelectorAll('.ep').forEach(function(e){{
   var t=e.getAttribute('data-search')||''; e.classList.toggle('hidden', q && t.indexOf(q)<0); }});
 document.querySelectorAll('main section').forEach(function(s){{
   var any=Array.prototype.some.call(s.querySelectorAll('.ep'),function(e){{return !e.classList.contains('hidden');}});
   s.classList.toggle('hidden', !any); }});}}
</script>
</body></html>"""


def write_html(path: str = HTML_PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_html(reference()))
    return path


def render_pdf(out_path: str) -> dict[str, Any]:
    """Render the reference to PDF via the existing PDF owner; degrade if no backend is usable."""
    try:
        from core.pdf_generator import PDFGenerator
        gen = PDFGenerator()
        if gen.backend == "none":
            return {"ok": False, "path": "", "reason": "no PDF backend available"}
        ok = gen.html_to_pdf(render_html(reference()), out_path)
        return {"ok": bool(ok), "path": out_path if ok else "", "backend": gen.backend,
                "reason": "" if ok else "pdf conversion failed"}
    except Exception as e:
        return {"ok": False, "path": "", "reason": str(e)}
