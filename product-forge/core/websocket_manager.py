"""
Conversation & Idea Ingestion - WebSocket Server

Real-time updates for dashboard when conversations are received,
compiled, or when change packages need approval.
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Set, Any
from dataclasses import dataclass, asdict

try:
    from fastapi import WebSocket, WebSocketDisconnect
    from fastapi.websockets import WebSocketState
except ImportError:
    print("FastAPI WebSocket not available")
    exit(1)


# ─── WebSocket Manager ────────────────────────────────────────────

class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[str, Set[WebSocket]] = {}  # topic -> connections

    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"[WebSocket] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        self.active_connections.discard(websocket)
        # Remove from all subscriptions
        for topic in list(self.subscriptions.keys()):
            self.subscriptions[topic].discard(websocket)
        print(f"[WebSocket] Client disconnected. Total: {len(self.active_connections)}")

    async def subscribe(self, websocket: WebSocket, topic: str):
        """Subscribe to a topic."""
        if topic not in self.subscriptions:
            self.subscriptions[topic] = set()
        self.subscriptions[topic].add(websocket)

    async def unsubscribe(self, websocket: WebSocket, topic: str):
        """Unsubscribe from a topic."""
        if topic in self.subscriptions:
            self.subscriptions[topic].discard(websocket)

    async def broadcast(self, event: str, data: Dict[str, Any], topic: str = None):
        """Broadcast event to all connections or subscribers of a topic."""
        message = json.dumps({
            "event": event,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }, default=str)

        targets = self.subscriptions.get(topic, set()) if topic else self.active_connections
        disconnected = set()

        for websocket in targets:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(message)
                else:
                    disconnected.add(websocket)
            except Exception as e:
                print(f"[WebSocket] Error sending to client: {e}")
                disconnected.add(websocket)

        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws)

    async def send_personal(self, websocket: WebSocket, event: str, data: Dict[str, Any]):
        """Send event to a specific client."""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                message = json.dumps({
                    "event": event,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat()
                }, default=str)
                await websocket.send_text(message)
        except Exception as e:
            print(f"[WebSocket] Error sending personal message: {e}")


# Singleton instance
ws_manager = WebSocketManager()


# ─── Event Types ──────────────────────────────────────────────────

class WSEventType:
    # Conversation events
    CONVERSATION_RECEIVED = "conversation.received"
    CONVERSATION_COMPILING = "conversation.compiling"
    CONVERSATION_COMPILED = "conversation.compiled"
    CONVERSATION_FAILED = "conversation.failed"

    # Idea events
    IDEA_CREATED = "idea.created"
    IDEA_APPROVED = "idea.approved"
    IDEA_REJECTED = "idea.rejected"
    IDEA_PROMOTED = "idea.promoted"

    # Project events
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"

    # Pipeline events
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_STAGE_STARTED = "pipeline.stage.started"
    PIPELINE_STAGE_COMPLETED = "pipeline.stage.completed"
    PIPELINE_STAGE_FAILED = "pipeline.stage.failed"
    PIPELINE_COMPLETED = "pipeline.completed"

    # Change package events
    CHANGE_PACKAGE_CREATED = "change_package.created"
    CHANGE_PACKAGE_APPROVED = "change_package.approved"
    CHANGE_PACKAGE_REJECTED = "change_package.rejected"
    CHANGE_PACKAGE_APPLIED = "change_package.applied"

    # Stats events
    STATS_UPDATED = "stats.updated"


# ─── Event Helpers ────────────────────────────────────────────────

async def broadcast_conversation_received(conv_id: str, title: str, source: str, intent: str):
    """Broadcast when a new conversation is received."""
    await ws_manager.broadcast(WSEventType.CONVERSATION_RECEIVED, {
        "conversation_id": conv_id,
        "title": title,
        "source": source,
        "intent": intent
    })
    await ws_manager.broadcast(WSEventType.STATS_UPDATED, {}, topic="stats")


async def broadcast_conversation_compiled(conv_id: str, ideas_count: int, reqs_count: int, decs_count: int):
    """Broadcast when conversation compilation is complete."""
    await ws_manager.broadcast(WSEventType.CONVERSATION_COMPILED, {
        "conversation_id": conv_id,
        "ideas_count": ideas_count,
        "requirements_count": reqs_count,
        "decisions_count": decs_count
    })
    await ws_manager.broadcast(WSEventType.STATS_UPDATED, {}, topic="stats")


async def broadcast_conversation_failed(conv_id: str, error: str):
    """Broadcast when conversation compilation fails."""
    await ws_manager.broadcast(WSEventType.CONVERSATION_FAILED, {
        "conversation_id": conv_id,
        "error": error
    })


async def broadcast_idea_created(idea_id: str, title: str, confidence: float):
    """Broadcast when a new idea is extracted."""
    await ws_manager.broadcast(WSEventType.IDEA_CREATED, {
        "idea_id": idea_id,
        "title": title,
        "confidence": confidence
    })
    await ws_manager.broadcast(WSEventType.STATS_UPDATED, {}, topic="stats")


async def broadcast_project_created(project_name: str, source: str):
    """Broadcast when a new project is created."""
    await ws_manager.broadcast(WSEventType.PROJECT_CREATED, {
        "project_name": project_name,
        "source": source
    })
    await ws_manager.broadcast(WSEventType.STATS_UPDATED, {}, topic="stats")


async def broadcast_change_package_created(cp_id: str, project_id: str, changes_count: int):
    """Broadcast when a change package is created."""
    await ws_manager.broadcast(WSEventType.CHANGE_PACKAGE_CREATED, {
        "change_package_id": cp_id,
        "project_id": project_id,
        "changes_count": changes_count
    })
    await ws_manager.broadcast(WSEventType.STATS_UPDATED, {}, topic="stats")


async def broadcast_pipeline_update(project_name: str, stage: str, status: str, progress: int):
    """Broadcast pipeline status update."""
    await ws_manager.broadcast(WSEventType.PIPELINE_STAGE_STARTED if status == "running" else
                               WSEventType.PIPELINE_STAGE_COMPLETED if status == "completed" else
                               WSEventType.PIPELINE_STAGE_FAILED, {
        "project_name": project_name,
        "stage": stage,
        "status": status,
        "progress": progress
    }, topic=f"pipeline:{project_name}")


# ─── WebSocket Endpoint Handler ───────────────────────────────────

async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connection."""
    await ws_manager.connect(websocket)

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message = json.loads(data)

            action = message.get("action")

            if action == "subscribe":
                topic = message.get("topic", "")
                await ws_manager.subscribe(websocket, topic)
                await ws_manager.send_personal(websocket, "subscribed", {"topic": topic})

            elif action == "unsubscribe":
                topic = message.get("topic", "")
                await ws_manager.unsubscribe(websocket, topic)
                await ws_manager.send_personal(websocket, "unsubscribed", {"topic": topic})

            elif action == "ping":
                await ws_manager.send_personal(websocket, "pong", {})

            elif action == "get_stats":
                from core.conversation_models import ConversationStore
                store = ConversationStore()
                stats = store.get_stats()
                await ws_manager.send_personal(websocket, "stats", stats)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
        ws_manager.disconnect(websocket)


# ─── Integration with Intake API ─────────────────────────────────

def setup_ws_events():
    """Set up WebSocket event hooks in the intake API."""
    # This function is called to wire up WebSocket broadcasts
    # with the intake API endpoints

    import core.intake_api as intake_api

    # Store original endpoint functions
    original_intake = intake_api.intake_conversation
    original_compile = intake_api.compile_conversation

    # Wrap with WebSocket broadcasts
    async def wrapped_intake(req):
        result = await original_intake(req)
        if hasattr(result, 'id'):
            await broadcast_conversation_received(
                result.id,
                req.title or f"Conversation from {req.source_platform}",
                req.source_platform,
                req.intent
            )
        return result

    async def wrapped_compile(conv_id):
        result = await original_compile(conv_id)
        if "error" not in result:
            await broadcast_conversation_compiled(
                conv_id,
                result.get("ideas_saved", 0),
                result.get("requirements_saved", 0),
                result.get("decisions_saved", 0)
            )
        else:
            await broadcast_conversation_failed(conv_id, result["error"])
        return result

    # Replace endpoints
    intake_api.intake_conversation = wrapped_intake
    intake_api.compile_conversation = wrapped_compile
