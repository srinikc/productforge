"""Agent API (API-3): agent specs + capability vectors (read-only).

Maps to ``core.agent_spec`` (agent-card SSOT in ``agents/*.agent.json``) and ``core.agent_capabilities``
(the capability vector driving model routing). No shadow store.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request

from ..auth import authenticate
from ..envelope import from_request
from ..errors import ApiError

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", dependencies=[Depends(authenticate)])
def agents(request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import agent_spec
    out: List[Dict[str, Any]] = []
    for aid in agent_spec.list_agent_ids():
        card = agent_spec.card_for(aid)
        out.append({"agent_id": aid, "found": bool(card.get("found")),
                    "source": card.get("source", "")})
    return from_request(request, out, resource="agent")


@router.get("/{agent_id}", dependencies=[Depends(authenticate)])
def agent(agent_id: str, request: Request, ctx: Dict[str, Any] = Depends(authenticate)):
    from core import agent_spec
    card = agent_spec.card_for(agent_id)
    if not card.get("found"):
        raise ApiError("NOT_FOUND", "agent not found")
    return from_request(request, card, resource="agent", resource_id=agent_id)


@router.get("/{agent_id}/capabilities", dependencies=[Depends(authenticate)])
def capabilities(agent_id: str, request: Request,
                 ctx: Dict[str, Any] = Depends(authenticate)):
    from core import agent_capabilities, agent_spec
    if not agent_spec.card_for(agent_id).get("found"):
        raise ApiError("NOT_FOUND", "agent not found")
    vec = dict(agent_capabilities.vector(agent_id))
    vec["reasoning_enabled"] = agent_capabilities.reasoning_enabled(agent_id)
    return from_request(request, vec, resource="agent", resource_id=agent_id)
