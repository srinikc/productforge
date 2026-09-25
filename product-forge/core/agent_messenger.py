"""
Agent Messenger
Inter-agent communication layer with pub/sub and message queueing.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict


class MessageType(Enum):
    """Types of agent messages."""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    BROADCAST = "broadcast"
    HANDOFF = "handoff"
    ERROR = "error"
    ACK = "ack"


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class AgentMessage:
    """A message between agents."""
    message_id: str
    sender: str
    recipient: str
    message_type: MessageType
    topic: str = ""
    payload: Dict = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    created_at: str = ""
    read_at: str = ""
    reply_to: str = ""
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.message_id:
            self.message_id = f"msg-{uuid.uuid4().hex[:12]}"


class AgentMessenger:
    """Agent messaging system with pub/sub and queues."""

    def __init__(self, products_dir: str = "products", project: str = "default"):
        self.products_dir = products_dir
        self.project = project
        self.message_dir = Path(products_dir) / project / "messages"
        self.message_dir.mkdir(parents=True, exist_ok=True)

        self.queues: Dict[str, List[AgentMessage]] = defaultdict(list)
        self.subscribers: Dict[str, List[str]] = defaultdict(list)
        self.history: List[AgentMessage] = []
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)

        self._load()

    def send(
        self,
        sender: str,
        recipient: str,
        message_type: MessageType = MessageType.NOTIFICATION,
        payload: Dict = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        topic: str = "",
        reply_to: str = "",
        metadata: Dict = None
    ) -> str:
        """Send a message. Returns the message ID."""
        message = AgentMessage(
            message_id=f"msg-{uuid.uuid4().hex[:12]}",
            sender=sender,
            recipient=recipient,
            message_type=message_type,
            topic=topic,
            payload=payload or {},
            priority=priority,
            reply_to=reply_to,
            metadata=metadata or {}
        )

        self.history.append(message)

        if recipient == "broadcast" or message_type == MessageType.BROADCAST:
            self._broadcast(message)
        elif topic and topic in self.subscribers:
            self._publish(message, topic)
        else:
            self._deliver(message)

        self._trigger_handlers(message)

        if len(self.history) % 10 == 0:
            self._save()

        return message.message_id

    def _deliver(self, message: AgentMessage):
        self.queues[message.recipient].append(message)
        priority_order = {
            MessagePriority.URGENT: 0,
            MessagePriority.HIGH: 1,
            MessagePriority.NORMAL: 2,
            MessagePriority.LOW: 3
        }
        self.queues[message.recipient].sort(
            key=lambda m: (priority_order.get(m.priority, 2), m.created_at)
        )

    def _broadcast(self, message: AgentMessage):
        all_agents = set(self.queues.keys())
        for msg in self.history:
            all_agents.add(msg.sender)
            if msg.recipient not in ("broadcast", ""):
                all_agents.add(msg.recipient)

        for agent in all_agents:
            if agent != message.sender:
                copy = AgentMessage(
                    message_id=message.message_id,
                    sender=message.sender,
                    recipient=agent,
                    message_type=MessageType.BROADCAST,
                    topic=message.topic,
                    payload=message.payload,
                    priority=message.priority,
                    created_at=message.created_at,
                    metadata=message.metadata
                )
                self.queues[agent].append(copy)

    def _publish(self, message: AgentMessage, topic: str):
        for subscriber in self.subscribers.get(topic, []):
            if subscriber != message.sender:
                self._deliver(AgentMessage(
                    message_id=message.message_id,
                    sender=message.sender,
                    recipient=subscriber,
                    message_type=MessageType.NOTIFICATION,
                    topic=topic,
                    payload=message.payload,
                    priority=message.priority,
                    created_at=message.created_at,
                    metadata=message.metadata
                ))

    def receive(
        self,
        agent_id: str,
        mark_read: bool = True,
        message_type: MessageType = None,
        topic: str = ""
    ) -> List[AgentMessage]:
        """Receive all messages for an agent."""
        messages = list(self.queues.get(agent_id, []))

        if message_type:
            messages = [m for m in messages if m.message_type == message_type]

        if topic:
            messages = [m for m in messages if m.topic == topic]

        if mark_read:
            now = datetime.now().isoformat()
            for msg in messages:
                if not msg.read_at:
                    msg.read_at = now

        return messages

    def get_message(self, message_id: str) -> Optional[AgentMessage]:
        for msg in self.history:
            if msg.message_id == message_id:
                return msg
        return None

    def subscribe(self, agent_id: str, topic: str):
        if agent_id not in self.subscribers[topic]:
            self.subscribers[topic].append(agent_id)

    def unsubscribe(self, agent_id: str, topic: str):
        if agent_id in self.subscribers.get(topic, []):
            self.subscribers[topic].remove(agent_id)

    def on(self, event: str, handler: Callable):
        self.handlers[event].append(handler)

    def _trigger_handlers(self, message: AgentMessage):
        event = f"message:{message.message_type.value}"
        for handler in self.handlers.get(event, []):
            try:
                handler(message)
            except Exception as e:
                print(f"[Messenger] Handler error: {e}")

        if message.topic:
            for handler in self.handlers.get(f"topic:{message.topic}", []):
                try:
                    handler(message)
                except Exception as e:
                    print(f"[Messenger] Topic handler error: {e}")

    def clear_queue(self, agent_id: str) -> int:
        count = len(self.queues.get(agent_id, []))
        self.queues[agent_id] = []
        return count

    def get_stats(self) -> Dict:
        return {
            "total_messages": len(self.history),
            "agents_with_messages": len(self.queues),
            "total_queued": sum(len(q) for q in self.queues.values()),
            "topics": len(self.subscribers),
            "total_subscriptions": sum(len(s) for s in self.subscribers.values()),
            "by_type": {
                mt.value: sum(1 for m in self.history if m.message_type == mt)
                for mt in MessageType
            }
        }

    def _save(self):
        try:
            data = {
                "history": [asdict(m) for m in self.history[-500:]],
                "queues": {a: [asdict(m) for m in msgs] for a, msgs in self.queues.items()},
                "subscribers": dict(self.subscribers)
            }
            file_path = self.message_dir / "messages.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"[Messenger] Save error: {e}")

    def _load(self):
        file_path = self.message_dir / "messages.json"
        if not file_path.exists():
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for msg_data in data.get("history", []):
                msg = AgentMessage(
                    message_id=msg_data["message_id"],
                    sender=msg_data["sender"],
                    recipient=msg_data["recipient"],
                    message_type=MessageType(msg_data["message_type"]),
                    topic=msg_data.get("topic", ""),
                    payload=msg_data.get("payload", {}),
                    priority=MessagePriority(msg_data.get("priority", "normal")),
                    created_at=msg_data.get("created_at", ""),
                    read_at=msg_data.get("read_at", ""),
                    reply_to=msg_data.get("reply_to", ""),
                    metadata=msg_data.get("metadata", {})
                )
                self.history.append(msg)

            for agent, msgs in data.get("queues", {}).items():
                for msg_data in msgs:
                    msg = AgentMessage(
                        message_id=msg_data["message_id"],
                        sender=msg_data["sender"],
                        recipient=msg_data["recipient"],
                        message_type=MessageType(msg_data["message_type"]),
                        topic=msg_data.get("topic", ""),
                        payload=msg_data.get("payload", {}),
                        priority=MessagePriority(msg_data.get("priority", "normal")),
                        created_at=msg_data.get("created_at", "")
                    )
                    self.queues[agent].append(msg)

            for topic, subs in data.get("subscribers", {}).items():
                self.subscribers[topic] = subs
        except Exception as e:
            print(f"[Messenger] Load error: {e}")
