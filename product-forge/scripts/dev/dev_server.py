"""Local dev launcher (BI-PF-1256): start the PF API with the shared local dev token.

One command so `wg work` needs no manual env: it ensures the gitignored dev token
(`data/local/dev-api-token`), sets `PF_DEV=1` + `API_TOKEN`, and runs `uvicorn api.app:app` on 127.0.0.1.
The worker reads the same token via WorkerGrid `token_file`, so both sides agree automatically.

BI-PF-1261: the PF API is the single assignment authority - this launcher refuses to start a SECOND live
instance (a second authority would let two sessions claim the same item). It records a lock and blocks while a
PF API already answers on the target port.

Run from product-forge/:  python scripts/dev/dev_server.py [--host 127.0.0.1] [--port 8000]
"""
import argparse
import atexit
import json
import os
import sys
import urllib.request

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from core.paths import ROOT as _PF_ROOT  # noqa: E402

_LOCK = os.path.join(str(_PF_ROOT), "data", "local", "pf-api.lock")


def _live(host: str, port: int, timeout: float = 2.0) -> bool:
    """True when a PF API already answers health on host:port."""
    try:
        with urllib.request.urlopen(f"http://{host}:{int(port)}/api/v1/health", timeout=timeout) as r:
            return int(getattr(r, "status", 0)) == 200
    except Exception:
        return False


def _write_lock(host: str, port: int) -> None:
    try:
        os.makedirs(os.path.dirname(_LOCK), exist_ok=True)
        with open(_LOCK, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"pid": os.getpid(), "host": host, "port": int(port)}, f)
        atexit.register(lambda: os.path.exists(_LOCK) and os.remove(_LOCK))
    except Exception:
        pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PF local dev API launcher (BI-PF-1256)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args(argv)

    # BI-PF-1261: single assignment authority - never start a second live instance on an occupied port.
    if _live(a.host, a.port):
        print(f"refusing to start: a PF API is already serving http://{a.host}:{a.port} "
              "(the assignment authority must be SINGLE).\n"
              "Use that instance, stop it, or start on a different --port.")
        return 1

    os.environ["PF_DEV"] = "1"
    from api import auth
    tok = auth.ensure_dev_token()
    os.environ["API_TOKEN"] = tok
    _write_lock(a.host, a.port)
    print(f"dev API: http://{a.host}:{a.port}  (PF_DEV=1; token file: {auth.TOKEN_PATH})")
    print("worker: `python ../workergrid/wg.py work ...` reads the same token via token_file")
    import uvicorn
    uvicorn.run("api.app:app", host=a.host, port=a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
