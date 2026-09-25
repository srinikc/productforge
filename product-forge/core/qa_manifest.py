"""
QA manifest + static console snapshot.

Aggregates the QA/quality artifacts for a project into a single index
(products/<project>/qa-manifest.json) and a self-contained HTML snapshot
(test-framework/reports/<project>/index.html) for offline delivery. The pipeline
final report embeds the summary (decision, QIR, console URL, coverage).
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

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

_REPO = str(_PF_ROOT)
_TF = os.path.join(_REPO, "test-framework")
_PORT = 3011


def _rj(p):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _policy(project_dir: str):
    try:
        from core.verification_policy import policy
        return policy(project_dir)
    except Exception:
        return {}


def _flags(project_dir: str):
    try:
        from core.feature_flags import decisions
        return decisions(project_dir)
    except Exception:
        return {}


def _cycles(project: str):
    d = os.path.join(_TF, "results", "test-cycles")
    out = []
    if os.path.isdir(d):
        for n in os.listdir(d):
            if n.startswith(project + "_") and n.endswith(".json"):
                x = _rj(os.path.join(d, n))
                if x:
                    out.append({k: x.get(k) for k in
                                ("cycle_id", "phase", "status", "build_version", "started_at")})
    out.sort(key=lambda c: c.get("started_at", ""))
    return out


def build_manifest(project: str, project_dir: str) -> Dict[str, Any]:
    res = os.path.join(_TF, "results", project)
    builds = _rj(os.path.join(project_dir, "build-info.json")) or {}
    qir = _rj(os.path.join(res, "qir.json")) or {}
    gng = _rj(os.path.join(res, "go-no-go.json")) or {}
    spec = _rj(os.path.join(res, "spec-review.json")) or {}
    ins = _rj(os.path.join(res, "insights.json")) or {}
    cycles_idx = _rj(os.path.join(res, "cycles.json")) or {}
    try:
        from core.nfr_coverage import compute_nfr_coverage
        cov = compute_nfr_coverage(project_dir)
    except Exception:
        cov = {}

    dashboard_url = f"http://localhost:{_PORT}/?project={project}"
    manifest = {
        "project": project,
        "generated_at": datetime.now().isoformat(),
        "dashboard_url": dashboard_url,
        "build": {"build_id": builds.get("build_id"), "version": builds.get("version"),
                  "build_number": builds.get("build_number")},
        "release_notes": builds.get("release_notes", ""),
        "suites": (cycles_idx.get("suites") or {}),
        "cycles": _cycles(project),
        "qir": {"number": qir.get("number"), "band": qir.get("band"), "trend": qir.get("trend")},
        "qir_profile": qir.get("profile", []),
        "go_no_go": {"decision": gng.get("decision"), "matrix": gng.get("matrix", [])},
        "spec_review": spec.get("summary", {}),
        "insights": ins.get("summary", {}),
        "coverage": {"fr": f"{cov.get('fr_covered',0)}/{cov.get('fr_total',0)}",
                     "nfr": f"{cov.get('covered',0)}/{cov.get('total',0)}"},
        "verification_policy": _policy(project_dir),
        "feature_flags": _flags(project_dir),
        "artifacts": {
            "manifest": os.path.relpath(os.path.join(project_dir, "qa-manifest.json"), _REPO),
            "qir": os.path.relpath(os.path.join(res, "qir.json"), _REPO),
            "go_no_go": os.path.relpath(os.path.join(res, "go-no-go.json"), _REPO),
            "spec_review": os.path.relpath(os.path.join(res, "spec-review.json"), _REPO),
            "insights": os.path.relpath(os.path.join(res, "insights.json"), _REPO),
        },
    }
    with open(os.path.join(project_dir, "qa-manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    try:
        from core.pipeline_capabilities import safe_write_json
        safe_write_json(os.path.join(project_dir, "qa-manifest.json"), manifest)
    except Exception:
        pass
    manifest["snapshot"] = _snapshot(project, manifest)
    return manifest


def _snapshot(project: str, m: Dict) -> str:
    out_dir = os.path.join(_TF, "reports", project)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "index.html")

    def rows(items, cols):
        return "".join("<tr>" + "".join(f"<td>{i.get(c,'')}</td>" for c in cols) + "</tr>"
                       for i in items)

    gng = m["go_no_go"].get("matrix", [])
    matrix = "".join(f"<tr><td>{r['dimension']}</td><td class='{r['rag']}'>{r['rag']}</td>"
                     f"<td>{r['detail']}</td></tr>" for r in gng)
    profile = "".join(f"<tr><td>{c['characteristic']}</td><td>{c['weight']}</td>"
                      f"<td>{c['score']}</td><td>{c.get('evidence','')}</td></tr>"
                      for c in (m.get("qir_profile") or []))
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>QA Report — {project}</title>
<style>body{{font-family:system-ui;background:#0d1117;color:#e6edf3;padding:24px}}
table{{border-collapse:collapse;width:100%;margin:8px 0}}td,th{{border-bottom:1px solid #30363d;padding:8px;text-align:left;font-size:.85rem}}
.red{{color:#f85149}}.yellow{{color:#d29922}}.green{{color:#3fb950}}h1{{font-size:1.3rem}}code{{color:#8b949e}}</style></head><body>
<h1>QA Report — {project}</h1>
<p>Generated: {m['generated_at']}</p>
<p>Build: <b>{m['build'].get('build_id') or 'n/a'}</b> &nbsp; QIR: <b>{m['qir'].get('number')}</b> ({m['qir'].get('band')}) &nbsp;
Go/No-Go: <b>{m['go_no_go'].get('decision')}</b></p>
<p>Coverage: FR {m['coverage'].get('fr')} &middot; NFR {m['coverage'].get('nfr')}</p>
<p>Live console: <code>{m['dashboard_url']}</code></p>
<h2>Go/No-Go Matrix</h2><table><tr><th>Dimension</th><th>RAG</th><th>Detail</th></tr>{matrix}</table>
<h2>QIR Profile</h2><table><tr><th>Characteristic</th><th>Weight</th><th>Score</th><th>Evidence</th></tr>{profile}</table>
<h2>Spec Review</h2><p>blocking={m['spec_review'].get('blocking_open',0)} optional={m['spec_review'].get('optional_open',0)}</p>
<h2>Cycles</h2><table><tr><th>cycle</th><th>phase</th><th>status</th><th>build</th></tr>{rows(m['cycles'],['cycle_id','phase','status','build_version'])}</table>
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return os.path.relpath(path, _REPO)
