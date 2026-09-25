"""
Notification System - Notifies humans of important events
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

import time
import json
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum

class NotificationType(Enum):
    STAGE_COMPLETE = "stage_complete"
    STAGE_FAILED = "stage_failed"
    AGENT_ERROR = "agent_error"
    DEFECT_FOUND = "defect_found"
    DEFECT_FIXED = "defect_fixed"
    HUMAN_REQUIRED = "human_required"
    BUDGET_WARNING = "budget_warning"
    CIRCUIT_BREAKER = "circuit_breaker"
    PIPELINE_COMPLETE = "pipeline_complete"
    CUSTOM = "custom"

@dataclass
class Notification:
    notification_id: str
    notification_type: str
    title: str
    message: str
    agent: str
    stage: int
    timestamp: str
    read: bool
    priority: str  # low, medium, high, critical

class NotificationSystem:
    """Notification system for pipeline events"""
    
    def __init__(self, project: str):
        self.project = project
        self.notifications_file = _PF_ROOT / "products" / project / "notifications.json"
        self.notifications: List[Notification] = self._load_notifications()
    
    def _load_notifications(self) -> List[Notification]:
        if self.notifications_file.exists():
            with open(self.notifications_file) as f:
                data = json.load(f)
                return [Notification(**n) for n in data]
        return []
    
    def _save_notifications(self):
        with open(self.notifications_file, 'w') as f:
            json.dump([asdict(n) for n in self.notifications], f, indent=2)
    
    def send_notification(self, notification_type: NotificationType, title: str, 
                         message: str, agent: str = "", stage: int = -1, 
                         priority: str = "medium") -> Notification:
        """Send a notification"""
        notification = Notification(
            notification_id=f"NOTIF-{len(self.notifications)+1:04d}",
            notification_type=notification_type.value,
            title=title,
            message=message,
            agent=agent,
            stage=stage,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            read=False,
            priority=priority
        )
        self.notifications.append(notification)
        self._save_notifications()
        return notification
    
    def get_notifications(self, unread_only: bool = False) -> List[Notification]:
        """Get notifications"""
        if unread_only:
            return [n for n in self.notifications if not n.read]
        return self.notifications
    
    def mark_read(self, notification_id: str):
        """Mark notification as read"""
        for n in self.notifications:
            if n.notification_id == notification_id:
                n.read = True
                self._save_notifications()
                break
    
    def mark_all_read(self):
        """Mark all notifications as read"""
        for n in self.notifications:
            n.read = True
        self._save_notifications()
    
    def get_unread_count(self) -> int:
        """Get unread count"""
        return len([n for n in self.notifications if not n.read])
    
    def get_by_priority(self, priority: str) -> List[Notification]:
        """Get notifications by priority"""
        return [n for n in self.notifications if n.priority == priority]
    
    def clear_old(self, days: int = 30):
        """Clear notifications older than N days"""
        cutoff = time.time() - (days * 86400)
        self.notifications = [
            n for n in self.notifications
            if time.mktime(time.strptime(n.timestamp, "%Y-%m-%dT%H:%M:%S")) > cutoff
        ]
        self._save_notifications()
