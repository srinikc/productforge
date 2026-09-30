"""A2A (Agent2Agent) interop — framework-agnostic, contract-based, pipeline-tracked (BI-0197).

Exposes our agents (Agent Card + JSON-RPC ``message/send`` / ``tasks/get``) and consumes remote A2A agents
(``delegate``) — **without any opencode dependency** (agent identity comes from ``core.agent_spec`` /
``agents/*.agent.json``) and with **every exchange structured + validated + recorded** in the pipeline's own
owners (``delegations.json`` ledger via ``core.delegation`` + ``core.events`` stream). No ad-hoc side
channels: the pipeline always knows. See docs/A2A-DESIGN.md.
"""

import json
import os
import uuid
from typing import Dict, List, Optional

try:
    from core.paths import ROOT as _ROOT
except ImportError:  # script execution
    import sys as _sys
    _d = os.path.abspath(__file__)
    for _ in range(3):
        _d = os.path.dirname(_d)
        if os.path.isfile(os.path.join(_d, "core", "paths.py")):
            _sys.path.insert(0, _d)
            break
    from core.paths import ROOT as _ROOT

REMOTES_STORE = os.path.join(str(_ROOT), "config", "a2a-remotes." + "json")
CONTRACT = "a2a/v1"


# ── agent card (from AGNOSTIC AgentSpec — never .opencode) ──────────────────
def _load_specs() -> Dict:
    from core.agent_spec import load_specs
    try:
        return load_specs(os.path.join(str(_ROOT), "agents"))
    except Exception:
        return {}


def agent_card(spec_id: Optional[str] = None, specs: Optional[Dict] = None) -> Dict:
    """A2A Agent Card JSON built from a Product Forge AgentSpec (framework-agnostic)."""
    specs = specs if specs is not None else _load_specs()
    if spec_id:
        s = specs.get(spec_id)
        if s is None:
            return {}
        return {"name": s.id, "description": s.description or s.name,
                "version": "1.0", "protocolVersion": CONTRACT,
                "capabilities": {"streaming": False, "pushNotifications": False},
                "defaultInputModes": s.allowed_inputs or ["text"],
                "defaultOutputModes": s.outputs or ["text"],
                "skills": [{"id": k, "name": k} for k in (s.skills or [])]}
    # well-known orchestrator card advertising the skill set
    skills = []
    for s in specs.values():
        for k in (s.skills or []):
            skills.append({"id": k, "name": k, "agent": s.id})
    return {"name": "product-forge", "description": "Product Forge multi-agent pipeline",
            "version": "1.0", "protocolVersion": CONTRACT,
            "capabilities": {"streaming": False, "pushNotifications": False},
            "skills": skills}


# ── contract validation (fail-closed) ───────────────────────────────────────
def validate_message(msg: Dict, specs: Optional[Dict] = None) -> Optional[str]:
    """Return an error string if the A2A message violates the contract, else None."""
    if not isinstance(msg, dict):
        return "message must be an object"
    if str(msg.get("contract") or "") != CONTRACT:
        return f"unsupported contract: {msg.get('contract')!r}"
    if not str(msg.get("correlation_id") or "").strip():
        return "missing correlation_id"
    tgt = msg.get("to") or {}
    if not str(tgt.get("agent") or "").strip():
        return "missing to.agent"
    task = msg.get("task") or {}
    if not str(task.get("skill") or "").strip():
        return "missing task.skill"
    specs = specs if specs is not None else _load_specs()
    s = specs.get(str(tgt.get("agent")))
    if s is not None:
        if s.skills and str(task.get("skill")) not in s.skills:
            return f"skill '{task.get('skill')}' not offered by {s.id}"
        exp = set(str(x) for x in (msg.get("expected_outputs") or []))
        allowed = set(str(x) for x in (s.outputs or []))
        if exp and allowed and not exp.issubset(allowed):
            return "expected_outputs not in agent contract"
    return None


def validate_result(result: Dict, expected_outputs: Optional[List[str]] = None) -> Optional[str]:
    if not isinstance(result, dict):
        return "result must be an object"
    if str(result.get("correlation_id") or "") and not str(result.get("status") or ""):
        return "missing status"
    return None


def new_message(from_agent: str, to_agent: str, skill: str, correlation_id: str = "",
                input_refs: Optional[List[str]] = None, params: Optional[Dict] = None,
                expected_outputs: Optional[List[str]] = None,
                max_tokens: int = 0, max_cost: float = 0.0) -> Dict:
    return {"contract": CONTRACT, "id": str(uuid.uuid4()),
            "correlation_id": correlation_id or str(uuid.uuid4()),
            "from": {"agent": from_agent, "system": "product-forge"},
            "to": {"agent": to_agent, "system": ""},
            "task": {"skill": skill, "input_refs": input_refs or [], "params": params or {}},
            "budget": {"max_tokens": max_tokens, "max_cost": max_cost},
            "expected_outputs": expected_outputs or []}


# ── tracking (pipeline owners only — never a private log) ───────────────────
def _record(project: str, products_dir: str, from_agent: str, to_agent: str, skill: str,
            status: str, correlation_id: str, message_id: str, remote: str = "",
            payload_chars: int = 0) -> None:
    """Append to the pipeline's single delegation ledger AND emit pipeline events."""
    try:
        from core import events as _E
        pdir = os.path.join(products_dir, project)
        _E.emit(pdir, "a2a.message." + ("sent" if status.startswith("requested") else status),
                run_id=correlation_id, agent=from_agent, remote=remote, to=to_agent,
                skill=skill, message_id=message_id)
    except Exception:
        pass
    try:
        path = os.path.join(products_dir, project, "delegations." + "json")
        recs = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                recs = json.load(f) or []
        recs.append({"stage_id": "a2a", "from_agent": from_agent, "to_agent": to_agent,
                     "signal": skill, "payload_chars": payload_chars, "status": status,
                     "tokens": 0, "cost": 0.0, "message_id": message_id,
                     "remote": remote, "contract": CONTRACT, "correlation_id": correlation_id,
                     "timestamp": _now()})
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(recs, f, indent=2)
    except Exception:
        pass


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


# ── server side (our agent invoked by an A2A client) ────────────────────────
def _rpc_ok(rid, result) -> Dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _rpc_err(rid, code: int, message: str) -> Dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle(request: Dict, project: str = "default", products_dir: str = "products",
           budgets: Optional[Dict] = None) -> Dict:
    """Handle one A2A JSON-RPC request. Never raises; unknown method/message -> error."""
    rid = (request or {}).get("id")
    method = str((request or {}).get("method") or "")
    params = (request or {}).get("params") or {}
    try:
        if method == "message/send":
            msg = params.get("message") or params
            err = validate_message(msg)
            if err:
                return _rpc_err(rid, -32602, f"invalid message: {err}")
            to_agent = str((msg.get("to") or {}).get("agent"))
            corr = str(msg.get("correlation_id") or "")
            # budget: remote exchanges draw from the pipeline budget (fail-closed)
            b = (budgets or {}).setdefault(to_agent, {"total": 0, "max": 8})
            if b["total"] >= b["max"]:
                return _rpc_err(rid, -32010, "budget exceeded")
            b["total"] += 1
            mid = str(msg.get("id") or uuid.uuid4())
            _record(project, products_dir, str((msg.get("from") or {}).get("agent") or "remote"),
                    to_agent, str((msg.get("task") or {}).get("skill")), "received", corr, mid)
            task = {"id": mid, "correlation_id": corr, "status": "submitted",
                    "contract": CONTRACT, "to": to_agent}
            return _rpc_ok(rid, {"task": task})
        if method == "tasks/get":
            tid = str(params.get("id") or "")
            if not tid:
                return _rpc_err(rid, -32602, "missing task id")
            # state derives from the pipeline event stream (no parallel store)
            state = _task_state(project, products_dir, tid)
            if state is None:
                return _rpc_err(rid, -32004, f"task not found: {tid}")
            return _rpc_ok(rid, {"task": {"id": tid, "status": state, "contract": CONTRACT}})
        return _rpc_err(rid, -32601, f"method not found: {method}")
    except Exception as e:
        return _rpc_err(rid, -32603, f"internal error: {e}")


def _task_state(project: str, products_dir: str, task_id: str) -> Optional[str]:
    try:
        from core import events as _E
        pdir = os.path.join(products_dir, project)
        p = _E.path(pdir) if hasattr(_E, "path") else os.path.join(pdir, "events." + "jsonl")
        if not os.path.exists(p):
            return None
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if str(ev.get("message_id")) == task_id:
                    return "working" if "received" in str(ev.get("type")) else "submitted"
        return None
    except Exception:
        return None


# ── client side (consume remote A2A agents) ─────────────────────────────────
def _remotes() -> Dict:
    try:
        with open(REMOTES_STORE, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def list_remotes() -> List[Dict]:
    return [{"name": k, **v} for k, v in (_remotes().get("remotes") or {}).items()]


def _remote(name: str) -> Optional[Dict]:
    return (_remotes().get("remotes") or {}).get(name)


def send(remote: Dict, message: Dict, project: str = "default", products_dir: str = "products",
         timeout: int = 30) -> Dict:
    """Send a contract-validated A2A message to a remote agent; fail-closed."""
    err = validate_message(message)
    if err:
        return {"ok": False, "error": f"invalid message: {err}"}
    url = str((remote or {}).get("url") or "")
    if not url:
        return {"ok": False, "error": "remote has no url"}
    try:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "message/send",
                           "params": {"message": message}}).encode("utf-8")
        import urllib.request
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode("utf-8"))
        if "error" in resp:
            return {"ok": False, "error": resp["error"].get("message", "rpc error")}
        return {"ok": True, "result": resp.get("result")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def delegate(remote_name: str, message: Dict, project: str = "default",
             products_dir: str = "products") -> Dict:
    """Consume a remote A2A agent, tracked in the pipeline ledger + events (opt-in, whitelisted)."""
    if str(os.environ.get("A2A_ENABLE_CONSUME", "")).strip().lower() not in ("1", "true", "yes"):
        return {"ok": False, "error": "A2A consume disabled (set A2A_ENABLE_CONSUME=1)"}
    remote = _remote(remote_name)
    if remote is None:
        return {"ok": False, "error": f"unwhitelisted remote: {remote_name}"}
    corr = str(message.get("correlation_id") or "")
    mid = str(message.get("id") or uuid.uuid4())
    skill = str((message.get("task") or {}).get("skill") or "")
    from_agent = str((message.get("from") or {}).get("agent") or "orchestrator")
    r = send(remote, message, project, products_dir)
    status = "completed" if r.get("ok") else "failed"
    _record(project, products_dir, from_agent, str((message.get("to") or {}).get("agent") or remote_name),
            skill, status, corr, mid, remote=remote_name,
            payload_chars=len(json.dumps(message)))
    return r
