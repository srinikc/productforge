"""Local dev launcher (BI-PF-1256): start the PF API with the shared local dev token.

One command so `wg work` needs no manual env: it ensures the gitignored dev token
(`data/local/dev-api-token`), sets `PF_DEV=1` + `API_TOKEN`, and runs `uvicorn api.app:app` on 127.0.0.1.
The worker reads the same token via WorkerGrid `token_file`, so both sides agree automatically.

Run from product-forge/:  python scripts/dev/dev_server.py [--host 127.0.0.1] [--port 8000]
"""
import argparse
import os
import sys

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from api import auth  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PF local dev API launcher (BI-PF-1256)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args(argv)

    os.environ["PF_DEV"] = "1"
    tok = auth.ensure_dev_token()
    os.environ["API_TOKEN"] = tok
    print(f"dev API: http://{a.host}:{a.port}  (PF_DEV=1; token file: {auth.TOKEN_PATH})")
    print("worker: `python ../workergrid/wg.py work ...` reads the same token via token_file")
    import uvicorn
    uvicorn.run("api.app:app", host=a.host, port=a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
