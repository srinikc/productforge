"""Product Forge canonical API (API-first surface).

This is the contract/control-plane foundation defined by the master execution plan. It is intentionally
separate from the frozen legacy ``dashboard/`` app; clients (OpenCode, MCP, CLI, future Dashboard) are
adapters over this surface. Contract: docs/API-0.1-CONTRACT-RECONCILIATION.md.

Launch: ``python -m api.app``  (uvicorn, port from API_PORT, default 8000).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import authenticate
from .context import context_middleware
from .errors import install_handlers
from .routers import (agents, artifacts, backlog, engineering, enterprise, events, evidence, gates, github,
                      health, intake, issues, pipeline, projects, runs, tests, validation, vcs, workers)

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

app.include_router(health.router)
app.include_router(health.router, prefix="/api/v1")

for _r in (intake.router, projects.router, runs.router, pipeline.router,
           artifacts.router, evidence.router, backlog.router,
           validation.router, tests.router, gates.router, issues.router,
           vcs.router, workers.router, agents.router, engineering.router, enterprise.router,
           github.router, events.router):
    app.include_router(_r, prefix="/api/v1")


def main() -> None:
    import os
    import uvicorn
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT") or 8000)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
