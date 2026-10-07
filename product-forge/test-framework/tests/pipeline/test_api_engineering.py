"""API-3: engineering/validation APIs — validation, tests, gates, issues, vcs, workers, agents."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
os.environ.setdefault("API_ALLOW_ANON", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.app import app  # noqa: E402
from core import paths as _paths  # noqa: E402

_SCRATCH = "_test_api3_eng"


def _force_rmtree(p) -> None:
    """rmtree that clears read-only bits (git objects on Windows) before removing."""
    p = Path(p)
    if not p.exists():
        return
    for root, _dirs, files in os.walk(p, topdown=False):
        for name in files:
            try:
                os.chmod(os.path.join(root, name), 0o700)
            except Exception:
                pass
    shutil.rmtree(p, ignore_errors=True)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def scratch_project():
    d = Path(_paths.PRODUCTS_DIR) / _SCRATCH
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "project.json").write_text("{}", encoding="utf-8")
    yield _SCRATCH
    if d.exists():
        shutil.rmtree(d)


@pytest.fixture()
def git_project():
    """A scratch project that is its own git repo (isolated worktrees, no main-repo pollution)."""
    name = "_test_api4_worker"
    d = Path(_paths.PRODUCTS_DIR) / name
    wtroot = Path(_paths.PRODUCTS_DIR) / (name + "-worktrees")
    for p in (wtroot, d):
        _force_rmtree(p)
    d.mkdir(parents=True, exist_ok=True)

    def g(*a):
        subprocess.run(["git", *a], cwd=str(d), capture_output=True, text=True)

    g("init", "-q")
    g("config", "user.email", "t@local")
    g("config", "user.name", "test")
    (d / "README.md").write_text("x\n", encoding="utf-8")
    g("add", "-A")
    g("commit", "-q", "-m", "init")
    yield name
    try:
        from core.vcs import VCSManager
        m = VCSManager(str(d))
        for w in m.list_worktrees():
            if os.path.normcase(w.get("path", "")).startswith(os.path.normcase(str(wtroot))):
                m.remove_worktree(os.path.basename(w.get("path", "")))
    except Exception:
        pass
    for p in (wtroot, d):
        _force_rmtree(p)


def test_agents_list_and_capabilities(client):
    r = client.get("/api/v1/agents")
    assert r.status_code == 200
    agents = r.json()["data"]
    assert agents and agents[0]["agent_id"]
    r2 = client.get(f"/api/v1/agents/{agents[0]['agent_id']}/capabilities")
    assert r2.status_code == 200
    assert "reasoning_enabled" in r2.json()["data"]


def test_agent_not_found_contract(client):
    r = client.get("/api/v1/agents/nope-xyz")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_workers_queue_and_capacity(client):
    r = client.get("/api/v1/workers/queue")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "jobs" in data and "limits" in data
    r2 = client.get("/api/v1/workers/capacity")
    assert r2.status_code == 200
    assert "limits" in r2.json()["data"]


def test_issues_stats_and_unknown_not_found(client):
    r = client.get("/api/v1/issues/stats")
    assert r.status_code == 200
    r2 = client.get("/api/v1/issues/IS-NOPE-9999", params={"scope": "product_forge"})
    assert r2.status_code == 404
    assert r2.json()["error"]["code"] == "NOT_FOUND"


def test_issue_create_requires_title(client):
    r = client.post("/api/v1/issues", json={"scope": "product_forge"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_FAILED"


def test_project_scoped_reads_unknown_project_404(client):
    for path in ("/api/v1/validation", "/api/v1/gates/pr", "/api/v1/vcs",
                 "/api/v1/tests/matrix", "/api/v1/gates/quality"):
        r = client.get(path, params={"project": "does-not-exist-xyz"})
        assert r.status_code == 404, path
        assert r.json()["error"]["code"] == "NOT_FOUND", path


def test_project_scoped_reads_on_scratch(client, scratch_project):
    for path in ("/api/v1/validation", "/api/v1/validation/policy", "/api/v1/tests/matrix",
                 "/api/v1/tests/cycles", "/api/v1/gates/quality", "/api/v1/vcs",
                 "/api/v1/vcs/status", "/api/v1/vcs/branches", "/api/v1/vcs/commits"):
        r = client.get(path, params={"project": scratch_project})
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert "data" in r.json(), path


def test_engineering_flow_is_valid_and_covered(client):
    from core import engineering_flow
    res = engineering_flow.validate()
    assert res["ok"], res["errors"]
    assert res["checked"] > 0
    r = client.get("/api/v1/engineering")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data.get("flow") and data.get("invariants") and data.get("forbidden")
    assert data.get("external_ingestion")  # Intake is a separate, independent path
    assert data["flow"][0]["id"] == "task_contract"  # direct engineering entry
    r2 = client.get("/api/v1/engineering/coverage")
    assert r2.status_code == 200
    assert r2.json()["data"]["total"] == res["engineering"]
    assert r2.json()["data"]["direct_entry"] == "task_contract"


def test_engineering_stage_lookup(client):
    r = client.get("/api/v1/engineering/stages")
    assert r.status_code == 200
    steps = r.json()["data"]
    assert steps
    sid = steps[0]["id"]
    r2 = client.get(f"/api/v1/engineering/stages/{sid}")
    assert r2.status_code == 200
    assert r2.json()["data"]["id"] == sid
    r3 = client.get("/api/v1/engineering/stages/does-not-exist-xyz")
    assert r3.status_code == 404


def test_github_overview_evidence_and_unknown(client, scratch_project):
    scope = {"scope": "project", "project": scratch_project}
    ev = client.get("/api/v1/github/evidence", params=scope)
    assert ev.status_code == 200
    for k in ("run_id", "task_id", "commit_sha", "validation", "artifacts"):
        assert k in ev.json()["data"], k
    ov = client.get("/api/v1/github", params=scope)
    assert ov.status_code == 200 and "prs" in ov.json()["data"]
    missing = client.get("/api/v1/github/pr/999", params=scope)
    assert missing.status_code == 404
    unknown = client.get("/api/v1/github", params={"scope": "project", "project": "nope-xyz"})
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "NOT_FOUND"


def test_worker_providers_and_run_noop(client, git_project):
    r = client.get("/api/v1/engineering/worker-providers")
    assert r.status_code == 200
    names = {p["name"] for p in r.json()["data"]}
    assert {"noop", "human", "command", "opencode"} <= names

    scope = {"scope": "project", "project": git_project}
    created = client.post("/api/v1/engineering/tasks",
                          json=dict(scope, title="t", objective="o", acceptance_criteria=["a"]))
    tid = created.json()["resource_id"]
    rr = client.post(f"/api/v1/engineering/tasks/{tid}/run", json=dict(scope, provider="noop"))
    assert rr.status_code == 200, rr.text
    data = rr.json()["data"]
    assert data["status"] == "NEEDS_REVIEW" and data["worktree_id"]
    res = client.get(f"/api/v1/engineering/tasks/{tid}/results", params=scope)
    assert res.status_code == 200 and len(res.json()["data"]) == 1
    task = client.get(f"/api/v1/engineering/tasks/{tid}", params=scope).json()["data"]
    assert task["status"] == "review"


def test_worker_run_unknown_task_404(client, scratch_project):
    r = client.post("/api/v1/engineering/tasks/TC-NOPE-9999/run",
                    json={"scope": "project", "project": scratch_project, "provider": "noop"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_vcs_branch_name_and_worktrees(client, scratch_project):
    r = client.get("/api/v1/vcs/branch-name", params={"task_id": "TC-PF-0001", "area": "Web UI"})
    assert r.status_code == 200
    assert r.json()["data"]["feature"] == "feature/web-ui/tc-pf-0001"
    r2 = client.get("/api/v1/vcs/worktrees", params={"project": scratch_project})
    assert r2.status_code == 200
    assert "worktrees" in r2.json()["data"] and "root" in r2.json()["data"]


def test_vcs_worktree_naming_and_protection_unit():
    from core.vcs import VCSManager
    assert VCSManager.feature_branch_name("eng", "TC-PF-0002") == "feature/eng/tc-pf-0002"
    assert VCSManager.validation_branch_name("run-1") == "validation/run-1"
    m = VCSManager.__new__(VCSManager)
    m.protected = {"main"}
    m.integration_branch = "develop"
    m.release_branch = "main"
    assert m.is_protected("main") and m.is_protected("develop")


def test_engineering_schedule(client):
    # worker/scheduler registry was decoupled into WorkerGrid (ADR-0002); the schedule/eligibility read stays.
    r2 = client.get("/api/v1/engineering/schedule")
    assert r2.status_code == 200
    counts = r2.json()["data"]["counts"]
    assert counts["assigned"] <= counts["capacity"]


def test_scheduler_plan_unit():
    from core import scheduler
    slots = [{"slot_id": "s-1", "worker_id": "w", "type": "local-agent",
              "capabilities": ["python"], "max_concurrency": 1}]
    tasks = [
        {"task_id": "T1", "status": "ready", "priority": "P1", "risk": "low",
         "dependencies": [], "blocked_by": [], "allowed_paths": ["src/a.py"],
         "affected_files": [], "required_capabilities": ["python"], "required_worker_type": ""},
        {"task_id": "T2", "status": "ready", "priority": "P0", "risk": "low",
         "dependencies": ["T1"], "blocked_by": [], "allowed_paths": ["src/b.py"],
         "affected_files": [], "required_capabilities": ["python"], "required_worker_type": ""},
    ]
    p = scheduler.plan(tasks=tasks, slots=slots)
    assert {a["task_id"] for a in p["assignments"]} == {"T1"}
    assert any(b["task_id"] == "T2" for b in p["blocked"])


def test_task_contract_validate_unit():
    from core import task_contract
    assert task_contract.validate({"title": "t"})["ok"] is False
    ok = task_contract.validate({"title": "t", "objective": "o", "acceptance_criteria": ["a"]})
    assert ok["ok"] is True, ok["errors"]


def test_task_contract_api_roundtrip(client, scratch_project):
    scope = {"scope": "project", "project": scratch_project}
    body = dict(scope, title="Add CSV export", objective="Export table to CSV",
                acceptance_criteria=["CSV has headers", "UTF-8"], risk="low", priority="P1")
    r = client.post("/api/v1/engineering/tasks", json=body)
    assert r.status_code == 200, r.text
    tid = r.json()["resource_id"]
    assert tid.startswith("TC-")

    r2 = client.get("/api/v1/engineering/tasks", params=scope)
    assert r2.status_code == 200
    assert any(t["task_id"] == tid for t in r2.json()["data"])

    r3 = client.get(f"/api/v1/engineering/tasks/{tid}", params=scope)
    assert r3.status_code == 200
    assert r3.json()["data"]["objective"] == "Export table to CSV"

    r4 = client.post(f"/api/v1/engineering/tasks/{tid}/status", json=dict(scope, status="ready"))
    assert r4.status_code == 200
    assert r4.json()["data"]["status"] == "ready"

    bad = client.post("/api/v1/engineering/tasks", json=dict(scope, title="no criteria"))
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "VALIDATION_FAILED"
