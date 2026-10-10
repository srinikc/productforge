"""PF Go-core runtime invocation (B1, BI-PF-0394): invoke the compiled native Go core.

"Go-first for new work" (LOCKED delivery baseline BI-PF-0387 / ADR BI-PF-0388): new shipped/sensitive
logic lands in the Go core (``product-forge/go/pfcore``) and is invoked from the PF runtime through
the A1 wire contract (``core.contracts`` <-> ``go/pfcore-host``).

Single writer for the Go-host invocation concern (registered: core/go_host.py). Read-only on the
backlog; writes nothing but the response it returns. Never raises: every failure mode (binary
missing, build needed, non-zero exit, bad JSON) is a fail-closed invalid response.
Build (``go build``/``go vet``/``go test`` gates) lives with the Go sources; packaging/signing is
A3 (BI-PF-0398) â€” this module only invokes an already-built binary, building it on demand when absent.
"""
import contextlib
import json
import os
import subprocess
from typing import Any

from core.paths import ROOT

_FILENAME = "pfcore-host.exe" if os.name == "nt" else "pfcore-host"
_BINARY = os.path.join(str(ROOT), "go", "pfcore", _FILENAME)


def binary_path() -> str:
    """Where the compiled pfcore host binary is expected."""
    return _BINARY


def build() -> dict[str, Any]:
    """Compile the pfcore host binary (go build). Best-effort; returns {ok, error}."""
    try:
        r = subprocess.run(["go", "build", "-o", _BINARY, "."], cwd=os.path.dirname(_BINARY),
                           capture_output=True, text=True, timeout=180)
        return {"ok": r.returncode == 0, "error": (r.stderr or "")[-400:] if r.returncode else ""}
    except FileNotFoundError:
        return {"ok": False, "error": "go toolchain not found on PATH"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _ensure_binary() -> tuple[str, str]:
    """Return (binary_path, error). Builds once if the binary is missing."""
    if os.path.isfile(_BINARY):
        return _BINARY, ""
    b = build()
    return _BINARY, (b.get("error") or "" if not b.get("ok") else "")


def invoke(op: str, contract_name: str = "", payload: dict | None = None, *,
           req_id: str = "", source: str = "python") -> dict[str, Any]:
    """Invoke the native Go core through the A1 wire contract; returns the canonical wire response.

    Never raises (fail-closed): invalid/missing binary or a non-zero host exit is an ``ok=False``
    error response with ``host="go"`` semantics preserved where known.
    """
    from core import contracts
    import uuid
    req_id = str(req_id or "") or f"pfcore-{op}-{uuid.uuid4().hex[:8]}"
    req = contracts.wire_request(op, contract_name, payload, id=req_id, source=source)
    binary, err = _ensure_binary()
    if err or not os.path.isfile(binary):
        return contracts._wire_response(str(req.get("id") or ""), op, False, "error", "go",
                                        contract_name, error="pfcore host unavailable: " + (err or "not built"))
    try:
        r = subprocess.run([binary], input=json.dumps(req), capture_output=True, text=True, timeout=60)
    except Exception as e:  # noqa: BLE001
        return contracts._wire_response(str(req.get("id") or ""), op, False, "error", "go",
                                        contract_name, error=f"{type(e).__name__}: {e}")
    if r.returncode != 0:
        return contracts._wire_response(str(req.get("id") or ""), op, False, "error", "go",
                                        contract_name, error=(r.stderr or f"exit={r.returncode}")[-400:])
    try:
        resp = json.loads(r.stdout)
    except Exception as e:  # noqa: BLE001
        return contracts._wire_response(str(req.get("id") or ""), op, False, "error", "go",
                                        contract_name, error=f"invalid wire-response: {e}")
    check = contracts.validate("wire-response", resp)
    if not check.get("valid"):
        return contracts._wire_response(str(req.get("id") or ""), op, False, "error", "go",
                                        contract_name, error="wire-response failed validation: "
                                        + "; ".join(check.get("errors") or [])[:200])
    return resp


def status() -> dict[str, Any]:
    """Operator-visible state of the native Go core (probe; read-only)."""
    r = invoke("ping", req_id="status")
    data = r if isinstance(r, dict) else {}
    present = os.path.isfile(_BINARY)
    with contextlib.suppress(Exception):
        from core import contracts
        names = contracts.contract_names()
    return {"binary": _BINARY, "binary_present": present, "ok": bool(data.get("ok")),
            "host": data.get("host"), "version": (data.get("result") or {}).get("version"),
            "go_version": (data.get("result") or {}).get("go_version"),
            "capabilities": (data.get("result") or {}).get("capabilities"), "contracts": names}
