"""Projects API (API-2): create/read/update projects via canonical services.

Projects are a directory-per-project under ``products/``. This router reads the canonical ``project.json``
(owner ``core.project_store``) and lists projects from the products dir. It does not manipulate files directly.
"""

import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate, require_operator
from ..envelope import from_request
from ..errors import ApiError
from ..pagination import paginate

router = APIRouter(prefix="/projects", tags=["projects"])

_NAME_OK = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


def _products_dir() -> str:
    from core import paths
    return paths.PRODUCTS_DIR


def _valid_name(name: str) -> str:
    name = str(name or "").strip()
    if not name or any(c not in _NAME_OK for c in name) or name in (".", ".."):
        raise ApiError("VALIDATION_FAILED", "invalid project name",
                       details={"allowed": "letters, digits, - _ ."})
    return name


def _project_dir(name: str) -> str:
    return os.path.join(_products_dir(), name)


@router.get("")
def list_projects(request: Request, limit: int = 50, cursor: str = "",
                  ctx: Dict[str, Any] = Depends(authenticate)):
    base = _products_dir()
    names = []
    if os.path.isdir(base):
        for n in sorted(os.listdir(base)):
            if n.startswith(".") or n.startswith("_test"):
                continue
            d = os.path.join(base, n)
            if os.path.isdir(d) and os.path.isfile(os.path.join(d, "project.json")):
                names.append(n)
    page, links = paginate([{"project_id": n} for n in names], limit=limit, cursor=cursor)
    return from_request(request, page, resource="project", links=links)


@router.get("/{project}")
def get_project(project: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import project_store
    name = _valid_name(project)
    d = _project_dir(name)
    if not os.path.isdir(d):
        raise ApiError("NOT_FOUND", "project not found")
    cfg = project_store.load(name, os.path.basename(_products_dir()))
    return from_request(request, cfg, resource="project", resource_id=name)


@router.post("", dependencies=[Depends(authenticate)])
def create_project(body: Dict[str, Any], request: Request,
                   ctx: Dict[str, Any] = Depends(authenticate)):
    from core import project_store
    name = _valid_name(str(body.get("project_id") or body.get("name") or ""))
    d = _project_dir(name)
    if os.path.isdir(d):
        raise ApiError("CONFLICT", "project already exists")
    os.makedirs(d, exist_ok=True)
    cfg = {"name": name, "title": str(body.get("title") or name),
           "description": str(body.get("description") or "")}
    project_store.save(name, cfg, os.path.basename(_products_dir()))
    return from_request(request, cfg, resource="project", resource_id=name, status="ok")


@router.get("/{project}/repo", dependencies=[Depends(authenticate)])
def get_project_repo(project: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    """Recommended GitHub repo name + current product remote (stage-0 repo setup)."""
    from core import project_store, repo_setup
    name = _valid_name(project)
    d = _project_dir(name)
    if not os.path.isdir(d):
        raise ApiError("NOT_FOUND", "project not found")
    idea = str((project_store.load(name, os.path.basename(_products_dir())) or {}).get("idea") or "")
    return from_request(request, repo_setup.status(name, d, idea), resource="project", resource_id=name)


@router.post("/{project}/repo", dependencies=[Depends(require_operator)])
def set_project_repo(project: str, body: Dict[str, Any], request: Request,
                     ctx: Dict[str, Any] = Depends(require_operator)):
    """Confirm/name -> create the GitHub repo -> connect the product remote (fail-closed local-only)."""
    from core import project_store, repo_setup
    name = _valid_name(project)
    d = _project_dir(name)
    if not os.path.isdir(d):
        raise ApiError("NOT_FOUND", "project not found")
    idea = str((project_store.load(name, os.path.basename(_products_dir())) or {}).get("idea") or "")
    res = repo_setup.setup(name, d, name=str(body.get("name") or ""), idea=idea,
                           private=bool(body.get("private", True)), confirm=bool(body.get("confirm")),
                           owner=str(body.get("owner") or ""), create=bool(body.get("create", True)))
    return from_request(request, res, resource="project", resource_id=name)
