"""
Test Dashboard - Web application for test metrics and reporting
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

# Import framework modules
from core.reporter import TestReporter
from core.defect_tracker import DefectTracker
from core.suite_manager import SuiteManager
from core.rcca import RCCAAnalyzer
from core.agent_integration import AgentIntegration
from dashboard.auth import AuthManager

PORT = 3011

# ── QA console helpers (project-scoped) ──────────────────────────
_REPO = Path(__file__).resolve().parent.parent.parent
_PRODUCTS = _REPO / "products"
_TF_DIR = _REPO / "test-framework"


def _project_dir(project: str) -> Path:
    return _PRODUCTS / project


def _results(project: str) -> Path:
    return _TF_DIR / "results" / project


def _read_json(p):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _builds(project: str) -> Dict[str, Any]:
    pd = _project_dir(project)
    out: Dict[str, Any] = {"latest": _read_json(pd / "build-info.json"), "history": []}
    bdir = pd / "builds"
    if bdir.is_dir():
        for n in sorted(os.listdir(bdir)):
            if n.endswith(".json"):
                d = _read_json(bdir / n)
                if d:
                    out["history"].append({k: d.get(k) for k in
                                           ("build_id", "version", "build_number", "trigger",
                                            "created_at", "status")})
    return out


def _release_notes(project: str, build: Optional[str] = None) -> Dict[str, Any]:
    rel = _project_dir(project) / "docs" / "releases"
    if not rel.is_dir():
        return {"build": build, "notes": ""}
    files = sorted(rel.glob("*.md"))
    f = (rel / f"{build}.md") if build else (files[-1] if files else None)
    try:
        return {"build": (f.stem if f else ""), "notes": f.read_text(encoding="utf-8")}
    except Exception:
        return {"build": build, "notes": ""}


def _cycles(project: str) -> Dict[str, Any]:
    d = _TF_DIR / "results" / "test-cycles"
    out = []
    if d.is_dir():
        for n in os.listdir(d):
            if n.startswith(project + "_") and n.endswith(".json"):
                x = _read_json(d / n)
                if x:
                    out.append({k: x.get(k) for k in
                                ("cycle_id", "project", "phase", "stage", "status",
                                 "build_version", "started_at", "completed_at")})
    out.sort(key=lambda c: c.get("started_at", ""))
    idx = _read_json(_results(project) / "cycles.json") or {}
    return {"cycles": out, "suites": idx.get("suites", {}), "definitions": idx.get("cycles", {})}


def _quality_status(project: str) -> Dict[str, Any]:
    qir = _read_json(_results(project) / "qir.json") or {}
    gng = _read_json(_results(project) / "go-no-go.json") or {}
    sr = _read_json(_results(project) / "spec-review.json") or {}
    ins = _read_json(_results(project) / "insights.json") or {}
    rag = {"no-go": "red", "go-with-risk": "yellow", "go": "green"}.get(
        str(gng.get("decision", "")).lower(), qir.get("band", "unknown"))
    return {"project": project, "rag": rag,
            "qir": {"number": qir.get("number"), "band": qir.get("band"), "trend": qir.get("trend")},
            "decision": gng.get("decision"),
            "spec_review": sr.get("summary", {}), "insights": ins.get("summary", {}),
            "top_risks": (gng.get("rationale") or [])[:5]}


def _delivery(project: str) -> Dict[str, Any]:
    m = _read_json(_project_dir(project) / "qa-manifest.json") or {}
    qir = _read_json(_results(project) / "qir.json") or {}
    gng = _read_json(_results(project) / "go-no-go.json") or {}
    return {"project": project,
            "dashboard_url": f"http://localhost:{PORT}/?project={project}",
            "manifest": m, "qir": qir.get("number"), "decision": gng.get("decision")}


def _checkins(project: str, limit: int = 100) -> Dict[str, Any]:
    """Commit/PR history for the project (for any UI)."""
    try:
        import sys as _sys
        if _REPO.as_posix() not in [p.replace("\\", "/") for p in _sys.path[:5]]:
            _sys.path.insert(0, str(_REPO))
        from core.vcs import VCSManager
        pd = _project_dir(project)
        cfg = _read_json(pd / "project.json") or {}
        v = VCSManager(str(pd), cfg.get("vcs") or {})
        if not v.is_repo():
            return {"project": project, "checkins": [], "note": "no repository"}
        return {"project": project, "checkins": v.checkins(limit)}
    except Exception as e:
        return {"project": project, "checkins": [], "error": str(e)}


def _pr_gate(project: str) -> Dict[str, Any]:
    """PR merge-checklist status (what must pass before merging to develop/main)."""
    try:
        import sys as _sys
        if str(_REPO) not in _sys.path:
            _sys.path.insert(0, str(_REPO))
        from core.pr_gate import can_merge
        return can_merge(project, str(_project_dir(project)))
    except Exception as e:
        return {"can_merge": False, "reason": str(e)}


BASE_DIR = Path(__file__).parent

class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler for test dashboard"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)
        self.auth_manager = AuthManager()
        self.suite_manager = SuiteManager()
        self.rcca_analyzer = RCCAAnalyzer()
        self.agent_integration = AgentIntegration()
        
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        
        # API endpoints
        if path.startswith('/api/'):
            self.handle_api(path, query)
            return
        
        # Static files
        if path == '/' or path == '':
            self.path = '/templates/login.html'
        elif path == '/dashboard':
            self.path = '/templates/index.html'
        
        return super().do_GET()
    
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b''
        
        try:
            data = json.loads(post_data) if post_data else {}
        except:
            data = {}
        
        if path == '/api/login':
            self.handle_login(data)
        elif path == '/api/logout':
            self.handle_logout(data)
        elif path == '/api/defects':
            self.handle_create_defect(data)
        elif path == '/api/test-comments':
            self.handle_add_comment(data)
        else:
            self.send_response(404)
            self.end_headers()
    
    def handle_login(self, data: Dict):
        """Handle login"""
        username = data.get("username", "")
        password = data.get("password", "")
        
        token = self.auth_manager.authenticate(username, password)
        
        if token:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "token": token}).encode())
        else:
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": "Invalid credentials"}).encode())
    
    def handle_logout(self, data: Dict):
        """Handle logout"""
        token = data.get("token", "")
        self.auth_manager.logout(token)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": True}).encode())
    
    def handle_api(self, path: str, query: Dict[str, List[str]]):
        """Handle API requests"""
        try:
            # Check authentication for protected endpoints
            token = query.get('token', [None])[0]
            if path != '/api/login' and not self.auth_manager.validate_session(token):
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Unauthorized"}).encode())
                return
            
            if path == '/api/projects':
                data = list(self.suite_manager.projects_config.get("projects", {}).keys())
            elif path == '/api/suites':
                data = self.suite_manager.list_suites()
            elif path == '/api/metrics':
                project = query.get('project', ['myworld'])[0]
                reporter = TestReporter(project)
                data = reporter.get_metrics()
            elif path == '/api/trends':
                project = query.get('project', ['myworld'])[0]
                days = int(query.get('days', [30])[0])
                reporter = TestReporter(project)
                data = reporter.get_trends(days)
            elif path == '/api/features':
                project = query.get('project', ['myworld'])[0]
                reporter = TestReporter(project)
                data = reporter.get_feature_status()
            elif path == '/api/regressions':
                project = query.get('project', ['myworld'])[0]
                reporter = TestReporter(project)
                data = reporter.detect_regressions()
            elif path == '/api/defects':
                project = query.get('project', ['myworld'])[0]
                tracker = DefectTracker(project)
                defects = tracker.get_open_defects()
                data = [{"defect_id": d.defect_id, "title": d.title,
                        "severity": d.severity.value, "status": d.status.value,
                        "created_at": d.created_at.isoformat()}
                       for d in defects]
            elif path == '/api/defects/summary':
                project = query.get('project', ['myworld'])[0]
                tracker = DefectTracker(project)
                data = tracker.get_summary()
            elif path == '/api/rcca':
                data = self.rcca_analyzer.get_rcca_summary()
            elif path == '/api/rcca/report':
                defect_id = query.get('defect_id', [None])[0]
                if defect_id:
                    report = self.rcca_analyzer.get_rcca_report(defect_id)
                    data = {"defect_id": defect_id, "report": report.__dict__ if report else None}
                else:
                    data = {"error": "defect_id required"}
            elif path == '/api/agents/history':
                agent_name = query.get('agent', ['ideation'])[0]
                data = self.agent_integration.get_agent_prevention_history(agent_name)
            elif path == '/api/summary':
                project = query.get('project', ['myworld'])[0]
                reporter = TestReporter(project)
                data = reporter.generate_summary()
            elif path == '/api/builds':
                project = query.get('project', ['myworld'])[0]
                data = _builds(project)
            elif path == '/api/release-notes':
                project = query.get('project', ['myworld'])[0]
                build = query.get('build', [None])[0]
                data = _release_notes(project, build)
            elif path == '/api/cycles':
                project = query.get('project', ['myworld'])[0]
                data = _cycles(project)
            elif path == '/api/spec-review':
                project = query.get('project', ['myworld'])[0]
                data = _read_json(_results(project) / 'spec-review.json') or {"summary": {}}
            elif path == '/api/traceability':
                project = query.get('project', ['myworld'])[0]
                try:
                    data = TestReporter(project).get_traceability_matrix()
                except Exception as e:
                    data = {"error": str(e)}
            elif path == '/api/insights':
                project = query.get('project', ['myworld'])[0]
                data = _read_json(_results(project) / 'insights.json') or {"insights": [], "summary": {}}
            elif path == '/api/qir':
                project = query.get('project', ['myworld'])[0]
                data = _read_json(_results(project) / 'qir.json') or {}
            elif path == '/api/gonogo':
                project = query.get('project', ['myworld'])[0]
                data = _read_json(_results(project) / 'go-no-go.json') or {}
            elif path == '/api/quality/status':
                project = query.get('project', ['myworld'])[0]
                data = _quality_status(project)
            elif path == '/api/delivery-report':
                project = query.get('project', ['myworld'])[0]
                data = _delivery(project)
            elif path == '/api/checkins':
                project = query.get('project', ['myworld'])[0]
                limit = int(query.get('limit', ['100'])[0])
                data = _checkins(project, limit)
            elif path == '/api/pr-gate':
                project = query.get('project', ['myworld'])[0]
                data = _pr_gate(project)
            elif path == '/api/test-comments':
                project = query.get('project', ['myworld'])[0]
                phase = query.get('phase', [None])[0]
                try:
                    data = TestReporter(project).get_test_comments(phase)
                except Exception as e:
                    data = {"error": str(e)}
            else:
                data = {"error": "Unknown endpoint"}
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data, default=str).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def handle_add_comment(self, data: Dict):
        """Add a test comment (3.4)."""
        try:
            project = data.get("project", "myworld")
            TestReporter(project).add_test_comment(
                test_id=data.get("test_id", ""), comment=data.get("comment", ""),
                phase=data.get("phase", ""))
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

    def handle_create_defect(self, data: Dict):
        """Handle defect creation"""
        try:
            project = data.get("project", "myworld")
            tracker = DefectTracker(project)
            
            from core.defect_tracker import Severity
            
            defect = tracker.log_defect(
                title=data.get("title", ""),
                description=data.get("description", ""),
                severity=Severity(data.get("severity", "medium")),
                test_id=data.get("test_id", ""),
                test_name=data.get("test_name", ""),
                suite_name=data.get("suite_name", ""),
                stack_trace=data.get("stack_trace"),
                affected_features=data.get("affected_features")
            )
            
            self.send_response(201)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"defect_id": defect.defect_id}).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def log_message(self, format, *args):
        pass

def run_dashboard():
    """Run the test dashboard server"""
    with HTTPServer(('', PORT), DashboardHandler) as httpd:
        print(f'Test Dashboard running at http://localhost:{PORT}')
        print(f'Default login: admin / admin123')
        print(f'Press Ctrl+C to stop')
        httpd.serve_forever()

if __name__ == '__main__':
    run_dashboard()
