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
from .routers import health, intake

API_VERSION = "v1"

app = FastAPI(title="Product Forge API", version="1.0.0", docs_url="/docs", openapi_url="/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

context_middleware(app)
install_handlers(app)

app.include_router(health.router)
app.include_router(intake.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")


def main() -> None:
    import os
    import uvicorn
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT") or 8000)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
