# DEPRECATED (2026-09-12): superseded by PipelineExecutor + core/orchestrator/*.
# Kept for reference; not part of the generic pipeline. See docs/UNWIRED-MODULES-TRIAGE.md.
"""
Conversation & Idea Ingestion - Intake API

FastAPI router for receiving conversations from ChatGPT, Gemini, Claude,
and manual sources. Handles deduplication, acknowledgment, and routing.
"""

try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import os
import json
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ─── Request/Response Models ──────────────────────────────────────

class MessageInput(BaseModel):
    role: str = Field(..., description="user or assistant")
    content: str = Field(..., description="Message content")

class IntakeRequest(BaseModel):
    source_platform: str = Field("manual", description="chatgpt, gemini, claude, manual")
    conversation_id: str = Field("", description="External conversation ID for dedup")
    intent: str = Field("save_idea", description="save_idea, new_project, new_project_quick, modify_project, add_context")
    target_project_id: str = Field("", description="Required for modify_project, add_context")
    target_project_name: str = Field("", description="Alternative to target_project_id")
    project_name: str = Field("", description="Required for new_project, new_project_quick")
    project_description: str = Field("", description="Optional, auto-generated if empty")
    title: str = Field("", description="Conversation title")
    scope: str = Field("entire", description="entire or last_n")
    scope_n: int = Field(0, description="Number of messages if scope=last_n")
    messages: List[MessageInput] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class IntakeResponse(BaseModel):
    id: str
    status: str
    message: str
    poll_url: str
    ideas_extracted: int = 0
    project_id: str = ""
    pipeline_status: str = ""

class ConversationListResponse(BaseModel):
    conversations: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int

class StatsResponse(BaseModel):
    conversations: int
    ideas: int
    requirements: int
    decisions: int
    change_packages: int
    conversations_by_status: Dict[str, int]
    ideas_by_status: Dict[str, int]

class IdeaActionRequest(BaseModel):
    action: str = Field(..., description="approve, reject, promote")
    project_name: str = Field("", description="For promote action")

class ChangePackageActionRequest(BaseModel):
    action: str = Field(..., description="approve, reject")
    selected_changes: List[str] = Field(default_factory=list)


# ─── Router ───────────────────────────────────────────────────────

router = APIRouter()

# Import conversation store
import sys
sys.path.insert(0, str(_PF_ROOT))
from core.conversation_models import (
    ConversationStore, Conversation, ConversationMessage,
    ExtractedIdea, ExtractedRequirement, ExtractedDecision,
    ChangePackage, ChangeItem,
    SourcePlatform, IntentType, ConversationStatus,
    IdeaStatus, RequirementType, ChangeType, ChangePackageStatus
)

# Singleton store
_store = None

def get_store():
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store


# ─── Intake Endpoint ─────────────────────────────────────────────

@router.post("/intake", response_model=IntakeResponse, status_code=201)
async def intake_conversation(req: IntakeRequest):
    """Receive a conversation from any source platform."""
    store = get_store()

    # Validate intent
    valid_intents = [i.value for i in IntentType]
    if req.intent not in valid_intents:
        raise HTTPException(400, f"Invalid intent: {req.intent}. Must be one of: {valid_intents}")

    # Validate required fields per intent
    if req.intent in ["new_project", "new_project_quick"] and not req.project_name:
        raise HTTPException(400, "project_name is required for new_project and new_project_quick")

    if req.intent in ["modify_project", "add_context"] and not req.target_project_id and not req.target_project_name:
        raise HTTPException(400, "target_project_id or target_project_name is required for modify_project and add_context")

    # Dedup by conversation_id
    if req.conversation_id:
        existing = store.get_conversation_by_source_id(req.conversation_id)
        if existing:
            return IntakeResponse(
                id=existing.id,
                status=existing.status,
                message="Conversation already received",
                poll_url=f"/api/v1/intake/{existing.id}",
                ideas_extracted=len(existing.extracted_ideas)
            )

    # Create conversation
    conv = Conversation(
        source_platform=req.source_platform,
        source_conversation_id=req.conversation_id,
        intent=req.intent,
        target_project_id=req.target_project_id,
        target_project_name=req.target_project_name,
        project_name=req.project_name,
        project_description=req.project_description,
        title=req.title or f"Conversation from {req.source_platform}",
        scope=req.scope,
        scope_n=req.scope_n,
        status=ConversationStatus.RECEIVED.value,
        messages=[
            ConversationMessage(role=m.role, content=m.content, message_order=i)
            for i, m in enumerate(req.messages)
        ],
        raw_messages_json=json.dumps([{"role": m.role, "content": m.content} for m in req.messages]),
        metadata=req.metadata
    )

    conv_id = store.save_conversation(conv)

    return IntakeResponse(
        id=conv_id,
        status="received",
        message="Conversation received. Processing will begin shortly.",
        poll_url=f"/api/v1/intake/{conv_id}"
    )


# ─── Status/Polling Endpoints ────────────────────────────────────

@router.post("/intake/{conv_id}/compile")
async def compile_conversation(conv_id: str):
    """Trigger compilation of a conversation."""
    from core.intent_router import IntentRouter
    router = IntentRouter()
    result = router.process_conversation(conv_id)
    if "error" in result:
        raise HTTPException(500, result["error"])
    return result


@router.post("/intake/{conv_id}/approve")
async def approve_conversation(conv_id: str):
    """Approve a conversation and trigger action."""
    store = get_store()
    conv = store.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    from core.intent_router import IntentRouter
    router = IntentRouter()
    result = router.process_conversation(conv_id)
    return result


@router.post("/intake/{conv_id}/reject")
async def reject_conversation(conv_id: str):
    """Reject a conversation."""
    store = get_store()
    conv = store.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    conv.status = ConversationStatus.REJECTED.value
    conv.updated_at = datetime.utcnow().isoformat()
    store.update_conversation(conv)
    return {"id": conv_id, "status": "rejected"}


@router.get("/intake/{conv_id}")
async def get_conversation(conv_id: str):
    """Get conversation status and extracted data."""
    store = get_store()
    conv = store.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    return {
        "id": conv.id,
        "source_platform": conv.source_platform,
        "intent": conv.intent,
        "title": conv.title,
        "status": conv.status,
        "project_name": conv.project_name,
        "target_project_id": conv.target_project_id,
        "compiled_summary": conv.compiled_summary,
        "ideas_extracted": len(conv.extracted_ideas),
        "requirements_extracted": len(conv.extracted_requirements),
        "decisions_extracted": len(conv.extracted_decisions),
        "change_package_id": conv.change_package.id if conv.change_package else "",
        "error_message": conv.error_message,
        "retry_count": conv.retry_count,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "compiled_at": conv.compiled_at
    }


@router.get("/intake/{conv_id}/messages")
async def get_conversation_messages(conv_id: str):
    """Get conversation messages."""
    store = get_store()
    conv = store.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    return {
        "id": conv.id,
        "title": conv.title,
        "messages": [
            {"role": m.role, "content": m.content, "order": m.message_order}
            for m in conv.messages
        ]
    }


# ─── List Conversations ──────────────────────────────────────────

@router.get("/conversations")
async def list_conversations(
    source: str = None,
    intent: str = None,
    status: str = None,
    page: int = 1,
    page_size: int = 20
):
    """List all conversations with optional filters."""
    store = get_store()
    offset = (page - 1) * page_size
    convs = store.list_conversations(
        source_platform=source,
        intent=intent,
        status=status,
        limit=page_size,
        offset=offset
    )
    total = store.count_conversations(status=status)

    return {
        "conversations": [
            {
                "id": c.id,
                "source_platform": c.source_platform,
                "intent": c.intent,
                "title": c.title,
                "status": c.status,
                "project_name": c.project_name,
                "ideas_count": len(c.extracted_ideas),
                "requirements_count": len(c.extracted_requirements),
                "decisions_count": len(c.extracted_decisions),
                "created_at": c.created_at,
                "updated_at": c.updated_at
            }
            for c in convs
        ],
        "total": total,
        "page": page,
        "page_size": page_size
    }


# ─── Ideas Endpoints ─────────────────────────────────────────────

@router.get("/ideas")
async def list_ideas(
    status: str = None,
    source: str = None,
    min_confidence: float = 0.0,
    page: int = 1,
    page_size: int = 20
):
    """List all extracted ideas."""
    store = get_store()
    offset = (page - 1) * page_size
    ideas = store.list_ideas(
        status=status,
        source=source,
        min_confidence=min_confidence,
        limit=page_size,
        offset=offset
    )
    total = store.count_ideas(status=status)

    return {
        "ideas": [
            {
                "id": i.id,
                "conversation_id": i.conversation_id,
                "project_id": i.project_id,
                "title": i.title,
                "description": i.description,
                "confidence": i.confidence,
                "status": i.status,
                "created_at": i.created_at
            }
            for i in ideas
        ],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/ideas/{idea_id}")
async def get_idea(idea_id: str):
    """Get idea detail."""
    store = get_store()
    idea = store.get_idea(idea_id)
    if not idea:
        raise HTTPException(404, "Idea not found")

    return {
        "id": idea.id,
        "conversation_id": idea.conversation_id,
        "project_id": idea.project_id,
        "title": idea.title,
        "description": idea.description,
        "confidence": idea.confidence,
        "status": idea.status,
        "source_messages": idea.source_messages,
        "metadata": idea.metadata,
        "created_at": idea.created_at
    }


@router.post("/ideas/{idea_id}/action")
async def idea_action(idea_id: str, req: IdeaActionRequest):
    """Approve, reject, or promote an idea."""
    store = get_store()
    idea = store.get_idea(idea_id)
    if not idea:
        raise HTTPException(404, "Idea not found")

    if req.action == "approve":
        idea.status = IdeaStatus.APPROVED.value
    elif req.action == "reject":
        idea.status = IdeaStatus.REJECTED.value
    elif req.action == "promote":
        idea.status = IdeaStatus.PROMOTED.value
        if req.project_name:
            idea.project_id = req.project_name
    else:
        raise HTTPException(400, f"Invalid action: {req.action}")

    store.update_idea(idea)
    return {"id": idea.id, "status": idea.status, "message": f"Idea {req.action}d"}


# ─── Projects Endpoint ───────────────────────────────────────────

@router.get("/projects")
async def list_projects():
    """List all projects in products/ folder."""
    products_dir = os.path.join(str(_PF_ROOT), "products")
    projects = []
    if os.path.exists(products_dir):
        for entry in os.listdir(products_dir):
            proj_path = os.path.join(products_dir, entry)
            if os.path.isdir(proj_path) and not entry.startswith(".") and entry != ".pipeline":
                # Check if it has pipeline config
                has_pipeline = os.path.exists(os.path.join(proj_path, "pipeline.json")) or \
                               os.path.exists(os.path.join(proj_path, "pipeline-definition.json"))
                projects.append({
                    "name": entry,
                    "path": proj_path,
                    "has_pipeline": has_pipeline
                })
    return {"projects": projects}


# ─── Change Packages Endpoints ───────────────────────────────────

@router.get("/change-packages")
async def list_change_packages(
    project_id: str = None,
    status: str = None
):
    """List all change packages."""
    store = get_store()
    cps = store.list_change_packages(project_id=project_id, status=status)
    return {
        "change_packages": [
            {
                "id": cp.id,
                "conversation_id": cp.conversation_id,
                "project_id": cp.project_id,
                "status": cp.status,
                "changes_count": len(cp.changes),
                "risks_count": len(cp.risks),
                "created_at": cp.created_at,
                "approved_at": cp.approved_at,
                "applied_at": cp.applied_at
            }
            for cp in cps
        ]
    }


@router.get("/change-packages/{cp_id}")
async def get_change_package(cp_id: str):
    """Get change package detail."""
    store = get_store()
    cp = store.get_change_package(cp_id)
    if not cp:
        raise HTTPException(404, "Change package not found")

    return {
        "id": cp.id,
        "conversation_id": cp.conversation_id,
        "project_id": cp.project_id,
        "status": cp.status,
        "changes": [
            {
                "id": c.id,
                "change_type": c.change_type,
                "target": c.target,
                "description": c.description,
                "priority": c.priority,
                "confidence": c.confidence,
                "files_affected": c.files_affected
            }
            for c in cp.changes
        ],
        "risks": cp.risks,
        "open_questions": cp.open_questions,
        "impact_analysis": cp.impact_analysis,
        "created_at": cp.created_at,
        "approved_at": cp.approved_at,
        "applied_at": cp.applied_at
    }


@router.post("/change-packages/{cp_id}/action")
async def change_package_action(cp_id: str, req: ChangePackageActionRequest):
    """Approve or reject a change package."""
    store = get_store()
    cp = store.get_change_package(cp_id)
    if not cp:
        raise HTTPException(404, "Change package not found")

    if req.action == "approve":
        cp.status = ChangePackageStatus.APPROVED.value
        cp.approved_at = datetime.utcnow().isoformat()
    elif req.action == "reject":
        cp.status = ChangePackageStatus.REJECTED.value
    else:
        raise HTTPException(400, f"Invalid action: {req.action}")

    store.update_change_package(cp)
    return {"id": cp.id, "status": cp.status, "message": f"Change package {req.action}d"}


# ─── Stats Endpoint ──────────────────────────────────────────────

@router.get("/stats")
async def get_stats():
    """Get ingestion statistics."""
    store = get_store()
    return store.get_stats()


# ─── Health Check ────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """Health check for intake API."""
    return {"status": "healthy", "service": "conversation-intake"}
