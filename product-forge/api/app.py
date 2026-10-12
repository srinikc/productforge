"""Product Forge canonical API (API-first surface).

This is the contract/control-plane foundation defined by the master execution plan. It is intentionally
separate from the frozen legacy ``dashboard/`` app; clients (OpenCode, MCP, CLI, future Dashboard) are
adapters over this surface. Contract: docs/API-0.1-CONTRACT-RECONCILIATION.md.

Launch: ``python -m api.app``  (uvicorn, port from API_PORT, default 8000).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .context import context_middleware
from .errors import install_handlers
from .routers import (
    agents,
    apidocs,
    artifacts,
    audit,
    backlog,
    changes,
    dogfood,
    engineering,
    enterprise,
    events,
    evidence,
    gates,
    github,
    health,
    intake,
    issues,
    packaging,
    pipeline,
    portfolio,
    projects,
    release,
    reservations,
    runs,
    tests,
    tools,
    validation,
    vcs,
    workers,
)

API_VERSION = "v1"

app = FastAPI(title="Product Forge API", version="1.0.0", docs_url="/docs", openapi_url="/openapi.json")

_CORS = ["*"]
try:
    from core import env_flags
    _CORS = [o.strip() for o in str(env_flags.get("API_ALLOW_ORIGINS", "*")).split(",") if o.strip()] or ["*"]
except Exception:
    pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

context_middleware(app)
install_handlers(app)


@app.on_event("startup")
def _start_state_checkpoint():
    """BI-PF-1257: periodic durable-state checkpoint (batch safety net for non-delivery mutations).

    The delivery lane checkpoints per-delivery; this covers grooming/restamp/triage/intake mutations made
    through the API. Interval via PF_STATE_CHECKPOINT_SECONDS (default 900; <=0 disables).
    """
    import threading
    import time
    try:
        from core import env_flags
        interval = int(env_flags.get("PF_STATE_CHECKPOINT_SECONDS", "900") or "900")
    except Exception:
        interval = 900
    if interval <= 0:
        return

    def _loop():
        from core import state_checkpoint
        while True:
            time.sleep(interval)
            try:
                state_checkpoint.checkpoint(note="periodic durable-state checkpoint")
            except Exception:
                pass

    threading.Thread(target=_loop, daemon=True, name="state-checkpoint").start()

app.include_router(health.router)
app.include_router(health.router, prefix="/api/v1")

for _r in (intake.router, projects.router, runs.router, pipeline.router,
           artifacts.router, evidence.router, backlog.router,
           validation.router, tests.router, tools.router, gates.router, issues.router,
           vcs.router, workers.router, agents.router, engineering.router, enterprise.router,
           github.router, events.router, apidocs.router, changes.router, reservations.router,
           release.router, packaging.router, audit.router, dogfood.router, portfolio.router):
    app.include_router(_r, prefix="/api/v1")


def main() -> None:
    import os

    import uvicorn
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT") or 8000)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
