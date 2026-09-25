"""Static, centralized HTML views (no dashboard needed): log index + traceability.

Produces self-contained HTML pages you can open in a browser *before* the dashboard
is built:
  * Logs:        products/<project>/logs/index.html            (runs -> agents -> log files)
                 product-forge/logs/index.html                 (backend logs)
  * Traceability products/<project>/traceability.html          (id hub matrix + gaps)

Static-first: reads the same stores the dashboard will consume (log INDEX.json,
traceability.json id_index), so the UI and the dashboard agree by construction.
Wired: `python -m core.views --project <p>` (and called at run end).
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

import html
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

REPO_ROOT = str(_PF_ROOT)

_CSS = """
body{font-family:system-ui,Segoe UI,Arial;margin:0;background:#0f1115;color:#e6e6e6}
header{padding:16px 24px;background:#151922;border-bottom:1px solid #262c3a}
h1{margin:0;font-size:18px} h2{margin:22px 0 8px;font-size:15px;color:#9fb0c8}
a{color:#6fb1ff;text-decoration:none} a:hover{text-decoration:underline}
table{border-collapse:collapse;width:100%;margin:6px 0 18px}
th,td{border:1px solid #262c3a;padding:6px 10px;font-size:13px;text-align:left;vertical-align:top}
th{background:#1b2130;color:#cdd6e6} tr:nth-child(even){background:#131722}
.tag{border-radius:10px;padding:1px 8px;font-size:11px;background:#20304a}
.warn{color:#ffb86b} .bad{color:#ff7a7a} .ok{color:#7ee08a}
.muted{color:#8a94a6} code{background:#1b2130;padding:1px 5px;border-radius:4px}
.kpi{display:inline-block;margin:0 18px 0 0} .kpi b{font-size:20px}
"""


def _page(title: str, body: str) -> str:
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{html.escape(title)}</title><style>{_CSS}</style></head>"
            f"<body><header><h1>{html.escape(title)}</h1>"
            f"<div class='muted'>generated {datetime.now().isoformat(timespec='seconds')} "
            f"by core/views.py</div></header><main style='padding:16px 24px'>{body}</main>"
            f"</body></html>")


def _cfg_layout(key: str) -> str:
    try:
        from core import log_router
        return log_router.config()["layout"].get(key, "")
    except Exception:
        return ""


# ── Logs index ───────────────────────────────────────────────────────────────

def render_logs_html(project_dir: str) -> str:
    """Centralized index.html for a project's logs (runs -> agents -> files)."""
    logs_root = os.path.join(project_dir, "logs")
    rows_runs: List[str] = []
    if os.path.isdir(logs_root):
        for run_id in sorted(os.listdir(logs_root)):
            d = os.path.join(logs_root, run_id)
            if not os.path.isdir(d):
                continue
            idx = {}
            ip = os.path.join(d, "INDEX.json")
            if os.path.exists(ip):
                try:
                    idx = json.load(open(ip, encoding="utf-8"))
                except Exception:
                    idx = {}
            files = [f for f in sorted(os.listdir(d)) if f.endswith(".log")]
            rows = []
            for f in files:
                p = os.path.join(d, f)
                sz = os.path.getsize(p)
                rel = os.path.relpath(p, logs_root).replace("\\", "/")
                rows.append(f"<tr><td><a href='{html.escape(rel)}'>{html.escape(f)}</a></td>"
                            f"<td>{sz:,}</td></tr>")
            rows_runs.append(
                f"<h2>Run <code>{html.escape(run_id)}</code> "
                f"<span class='tag'>{len(files)} log(s)</span></h2>"
                f"<table><tr><th>File</th><th>Size (B)</th></tr>{''.join(rows)}</table>")
    backend = _backend_log_link()
    body = (f"<p class='kpi'><b>{len(rows_runs)}</b> run(s) with logs</p>"
            f"{backend}"
            + ("".join(rows_runs) or "<p class='muted'>No logs yet.</p>"))
    return _page(f"Logs - {os.path.basename(project_dir)}", body)


def _backend_log_link() -> str:
    try:
        from core import log_router
        bp = log_router.backend_log_path()
        if os.path.exists(bp):
            return (f"<p>Pipeline backend log: <code>{html.escape(os.path.relpath(bp))}</code> "
                    f"({os.path.getsize(bp):,} B)</p>")
    except Exception:
        pass
    return ""


def write_logs_index(project_dir: str) -> str:
    p = os.path.join(project_dir, "logs", "index.html")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_logs_html(project_dir))
    return p


# ── Traceability view ────────────────────────────────────────────────────────

def render_traceability_html(project_dir: str) -> str:
    """Centralized traceability.html from traceability.json id_index."""
    tp = os.path.join(project_dir, "traceability.json")
    data = {}
    if os.path.exists(tp):
        try:
            data = json.load(open(tp, encoding="utf-8-sig"))
        except Exception:
            data = {}
    hub = (data.get("id_index") or {}) if isinstance(data, dict) else {}
    ids = hub.get("ids") or {}
    cov = hub.get("coverage") or {}
    undeclared = hub.get("undeclared") or {}

    def fam_rows(prefixes):
        rows = []
        for iid, rec in sorted(ids.items(), key=lambda kv: (kv[1].get("family", ""), kv[0])):
            if rec.get("family") not in prefixes:
                continue
            rows.append(
                f"<tr><td><code>{html.escape(iid)}</code></td>"
                f"<td>{html.escape(str(rec.get('family','')))}</td>"
                f"<td>{html.escape(str(rec.get('stage','')))}</td>"
                f"<td>{html.escape(str(rec.get('artifact','')))}</td>"
                f"<td>{rec.get('refs',0)}</td>"
                f"<td>{'yes' if rec.get('defined') else ''}</td></tr>")
        return "".join(rows)

    def table(title, prefixes):
        rows = fam_rows(prefixes)
        if not rows:
            return f"<h2>{title}</h2><p class='muted'>none</p>"
        return (f"<h2>{title} <span class='tag'>{len(rows.split('</tr>'))-1} ids</span></h2>"
                f"<table><tr><th>Id</th><th>Family</th><th>Stage</th><th>Artifact</th>"
                f"<th>Refs</th><th>Defined</th></tr>{rows}</table>")

    c = cov.get("counts", {})
    kpis = (f"<p class='kpi'><b>{c.get('must_or_kf',0)}</b> must/KF</p>"
            f"<p class='kpi'><b>{c.get('features',0)}</b> features</p>"
            f"<p class='kpi'><b>{c.get('requirements',0)}</b> requirements</p>"
            f"<p class='kpi'><b>{c.get('tests',0)}</b> tests</p>")
    warn = ""
    if undeclared:
        warn = (f"<p class='warn'>undeclared (invented) id prefixes: "
                + html.escape(json.dumps(undeclared)) + "</p>")
    gaps = ""
    for k in ("must_have_without_feature", "requirements_without_test",
              "features_without_requirement"):
        v = cov.get(k) or []
        if v:
            gaps += f"<p class='bad'>{k}: {html.escape(', '.join(v[:20]))}</p>"
    body = (kpis + warn + gaps
            + table("Features (F)", {"F"})
            + table("Requirements (FR/NFR/US)", {"FR", "NFR", "US"})
            + table("Business scope (KF/M/N/G)", {"KF", "M", "N", "G"})
            + table("Architecture (ADR/CMP/DM)", {"ADR", "CMP", "DM"})
            + table("Tests (T/V/OQ/TC)", {"T", "V", "OQ", "TC"}))
    return _page(f"Traceability - {os.path.basename(project_dir)}", body)


def write_traceability_html(project_dir: str) -> str:
    p = os.path.join(project_dir, "traceability.html")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_traceability_html(project_dir))
    return p


def write_all(project_dir: str) -> Dict[str, str]:
    """Write the static views. Best-effort (never raises)."""
    out = {}
    try:
        out["logs"] = write_logs_index(project_dir)
    except Exception:
        pass
    try:
        out["traceability"] = write_traceability_html(project_dir)
    except Exception:
        pass
    try:
        out["queue"] = write_queue_html()
    except Exception:
        pass
    try:
        out["verification"] = write_verification_html(project_dir)
    except Exception:
        pass
    try:
        out["backlog"] = write_backlog_html()
    except Exception:
        pass
    return out


# ── Queue / jobs view (centralized) ──────────────────────────────────────────

def render_queue_html() -> str:
    """queue.html — queued/scheduled/running/paused/done with source/run_id/item."""
    from core import job_manager as jm
    try:
        st = jm.status()
    except Exception:
        st = {"jobs": [], "by_state": {}, "limits": {}}
    rows = []
    for j in st.get("jobs", []):
        why = ""
        if j.get("state") == "scheduled" and j.get("not_before"):
            why = f"until {j['not_before']}"
        elif j.get("state") == "paused" and j.get("resume_after"):
            why = f"waiting on {j['resume_after']}"
        rows.append(
            f"<tr><td><code>{html.escape(str(j.get('job_id') or j.get('project')))}</code></td>"
            f"<td>{html.escape(str(j.get('project','')))}</td>"
            f"<td><span class='tag'>{html.escape(str(j.get('state','')))}</span></td>"
            f"<td>{html.escape(str(j.get('priority','')))}</td>"
            f"<td>{html.escape(str(j.get('source') or ''))}</td>"
            f"<td>{html.escape(str(j.get('actor') or ''))}</td>"
            f"<td><code>{html.escape(str(j.get('run_id') or ''))}</code></td>"
            f"<td>{html.escape(str(j.get('item_ids') or ''))}</td>"
            f"<td class='muted'>{html.escape(why)}</td></tr>")
    by = st.get("by_state", {})
    kpis = "".join(f"<p class='kpi'><b>{by.get(s,0)}</b> {s}</p>"
                   for s in ("running", "queued", "scheduled", "paused"))
    body = (f"<p class='muted'>limits: {html.escape(json.dumps(st.get('limits') or {}))} "
            f"| running: {st.get('running_count',0)}</p>{kpis}"
            f"<table><tr><th>Job</th><th>Project</th><th>State</th><th>Prio</th><th>Source</th>"
            f"<th>Actor</th><th>Run id</th><th>Backlog item</th><th>Waiting</th></tr>"
            f"{''.join(rows)}</table>")
    return _page("Queue / Jobs", body)


def write_queue_html() -> str:
    p = os.path.join(REPO_ROOT, "data", "portfolio", "queue.html")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_queue_html())
    return p


def render_verification_html(project_dir: str) -> str:
    """verification.html — close-on-verify status + attached report links."""
    try:
        from core import close_loop
        v = close_loop.verify_run(project_dir)
    except Exception as e:
        v = {"verified": False, "reasons": [str(e)], "evidence": {}, "reports": {}}
    rows = "".join(
        f"<tr><td>{html.escape(k)}</td><td class='{'ok' if ok else 'bad'}'>"
        f"{'pass' if ok else 'fail'}</td></tr>"
        for k, ok in (v.get("evidence") or {}).items())
    reps = "".join(
        f"<tr><td>{html.escape(k)}</td><td><code>{html.escape(os.path.relpath(p))}</code></td></tr>"
        for k, p in (v.get("reports") or {}).items())
    reasons = "".join(f"<p class='bad'>{html.escape(r)}</p>" for r in (v.get("reasons") or []))
    badge = "<span class='ok'>VERIFIED</span>" if v.get("verified") else "<span class='bad'>NOT VERIFIED</span>"
    body = (f"<p class='kpi'>scope <b>{html.escape(str(v.get('scope','')))}</b> — {badge}</p>"
            f"{reasons}"
            f"<h2>Evidence</h2><table><tr><th>Criterion</th><th>Result</th></tr>{rows}</table>"
            f"<h2>Attached reports</h2><table><tr><th>Kind</th><th>Path</th></tr>{reps}</table>")
    return _page(f"Verification - {os.path.basename(project_dir)}", body)


def write_verification_html(project_dir: str) -> str:
    p = os.path.join(project_dir, "verification.html")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_verification_html(project_dir))
    return p


_TERMINAL = {"completed", "done", "closed", "wontfix", "merged", "duplicate"}


def _all_backlog_items():
    """All items (open + closed) across both scopes, with computed buckets."""
    from core import backlog
    rows = []
    scopes = [("product_forge", None)]
    proj_root = os.path.join(REPO_ROOT, "products")
    if os.path.isdir(proj_root):
        for name in sorted(os.listdir(proj_root)):
            if os.path.isdir(os.path.join(proj_root, name, "backlog")):
                scopes.append(("project", name))
    for scope, proj in scopes:
        for store, items in (("open", backlog.list_open(scope, proj, order=False)),
                             ("closed", backlog.list_closed(scope, proj))):
            for it in items:
                st = str(it.get("status") or "new")
                rows.append({
                    "id": it.get("id", ""), "scope": proj or "product_forge",
                    "status": st, "type": it.get("type", ""), "origin": it.get("origin", ""),
                    "moscow": it.get("moscow", ""), "source": it.get("source", ""),
                    "title": (it.get("title") or ""), "store": store,
                })
    return rows


def render_backlog_html() -> str:
    """backlog.html — offline SNAPSHOT that, when the local API is reachable, LIVE-refreshes
    (fetch /api/backlog/all). Sortable + filterable columns; counts (total/open/closed/
    completed/parked). Works with no server (shows the baked snapshot)."""
    rows = _all_backlog_items()
    cols = ["Id", "Scope", "Status", "Type", "Origin", "MoSCoW", "Source", "Title", "Store"]
    head = "".join(
        "<th onclick=\"sortBy(%d)\">%s &#8693;</th>" % (i, c) for i, c in enumerate(cols))
    filt = "".join(
        "<th><input class='f' data-col='%d' oninput='filterCols()' placeholder='filter'></th>" % i
        for i in range(len(cols)))
    snap = json.dumps(rows)
    controls = ("<div style='margin:8px 0'>"
                "<label class='muted'><input type='checkbox' id='auto' onchange='toggleAuto()'> "
                "auto-refresh (15s)</label> "
                "<button onclick='refresh()'>Refresh now</button> "
                "<span id='src' class='muted'></span> "
                "<span class='muted' id='shown2'></span></div>")
    js = """<script>
const SNAP = __SNAP__;
const TERM = new Set(["completed","done","closed","wontfix","merged","duplicate"]);
let CUR = SNAP, timer = null;
function esc(s){return (s==null?"":String(s)).replace(/[&<>]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c];});}
function renderRows(rows){document.getElementById("body").innerHTML = rows.map(function(r){
  var cls = TERM.has(r.status) ? "done" : "";
  return "<tr class='"+cls+"'><td>"+esc(r.id)+"</td><td>"+esc(r.scope)+"</td>"
    +"<td><span class='tag'>"+esc(r.status)+"</span></td><td>"+esc(r.type)+"</td>"
    +"<td>"+esc(r.origin)+"</td><td>"+esc(r.moscow)+"</td><td>"+esc(r.source)+"</td>"
    +"<td>"+esc((r.title||"").slice(0,120))+"</td><td>"+esc(r.store)+"</td></tr>";}).join("");
  document.getElementById("shown").textContent = rows.length;
  var o=0,c=0,p=0,comp=0;
  rows.forEach(function(r){ if(TERM.has(r.status))c++; else o++; if(r.status==="parked")p++; if(r.status==="completed")comp++; });
  var k=document.querySelectorAll(".kpi b");
  if(k.length>=5){k[0].textContent=rows.length;k[1].textContent=o;k[2].textContent=c;k[3].textContent=comp;k[4].textContent=p;}
}
function sortBy(c){var t=document.getElementById("bk");var rows=[].slice.call(t.tBodies[0].rows);
 var dir=t.dataset.dirc===String(c)?-1:1; t.dataset.dirc=(dir===1?String(c):"");
 rows.sort(function(a,b){var x=a.cells[c].innerText.trim(),y=b.cells[c].innerText.trim();
  return dir*x.localeCompare(y,undefined,{numeric:true});});
 rows.forEach(function(r){t.tBodies[0].appendChild(r);});}
function filterCols(){var t=document.getElementById("bk");var rows=[].slice.call(t.tBodies[0].rows);
 var fs=[].slice.call(document.querySelectorAll("input.f")).map(function(i){return [i.dataset.col,i.value.toLowerCase()];});
 var n=0;rows.forEach(function(r){var ok=fs.every(function(f){return !f[1]||r.cells[f[0]].innerText.toLowerCase().indexOf(f[1])>=0;});
  r.style.display=ok?"":"none"; if(ok)n++;});document.getElementById("shown").textContent=n;}
function refresh(){location.reload();}
function toggleAuto(){var on=document.getElementById("auto").checked;
 if(on&&!timer)timer=setInterval(refresh,15000); if(!on&&timer){clearInterval(timer);timer=null;}}
renderRows(CUR);
</script>"""
    js = js.replace("__SNAP__", snap)
    body = (f"<p class='kpi'><b>0</b> total</p><p class='kpi'><b>0</b> open</p>"
            f"<p class='kpi'><b>0</b> closed</p><p class='kpi'><b>0</b> completed</p>"
            f"<p class='kpi'><b>0</b> parked</p>{controls}"
            f"<p class='muted'>showing <b id='shown'>{len(rows)}</b> items. Click a header to sort; "
            f"type in the filter row to filter. "
            f"(completed=work verified &amp; finished; closed=terminal/archived; parked=deferred.)</p>"
            f"<table id='bk'><thead><tr>{head}</tr><tr>{filt}</tr></thead><tbody id='body'></tbody></table>"
            + js)
    return _page("Backlog", body)


def write_backlog_html() -> str:
    p = os.path.join(REPO_ROOT, "data", "backlog", "index.html")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_backlog_html())
    return p


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Static views (logs/traceability/queue/verification/backlog)")
    ap.add_argument("--project", default="ProductForge-Dashboard")
    ap.add_argument("--products-dir", default="products")
    ap.add_argument("--serve", action="store_true",
                    help="Serve the views on a local URL, REGENERATING on every request "
                         "(so browser refresh shows live data — no dashboard needed).")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=3030)
    a = ap.parse_args(argv)
    pj = os.path.join(a.products_dir, a.project)
    if not a.serve:
        print(json.dumps(write_all(pj), indent=2))
        return 0
    # Regenerate-on-request static server (standalone; NOT the dashboard).
    import http.server
    import socketserver

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kw):
            super().__init__(*args, directory=REPO_ROOT, **kw)

        def do_GET(self):
            try:
                write_all(pj)
            except Exception:
                pass
            return super().do_GET()

        def log_message(self, *a):
            pass

    with socketserver.ThreadingTCPServer((a.host, a.port), Handler) as httpd:
        print(f"Views at http://{a.host}:{a.port}/  "
              f"(e.g. /product-forge/backlog/index.html) — regenerates on each refresh. "
              f"Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
