"""
Authentication module for test dashboard
"""

import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path

class AuthManager:
    """Simple admin authentication"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path or Path(__file__).parent.parent / "config")
        self.config = self._load_config()
        self.sessions: Dict[str, dict] = {}
        self.login_attempts: Dict[str, list] = {}
        
    def _load_config(self) -> Dict[str, Any]:
        """Load auth config"""
        config_file = self.config_path / "framework.yaml"
        if config_file.exists():
            import yaml
            with open(config_file) as f:
                config = yaml.safe_load(f)
                return config.get("auth", {})
        return {
            "enabled": True,
            "admin_user": "admin",
            "admin_password": "admin123",
            "max_login_attempts": 5,
            "lockout_duration": 300
        }
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return session token"""
        if not self.config.get("enabled", True):
            return self._create_session(username)
        
        # Check lockout
        if self._is_locked_out(username):
            return None
        
        # Verify credentials
        if (username == self.config.get("admin_user") and 
            password == self.config.get("admin_password")):
            self._clear_login_attempts(username)
            return self._create_session(username)
        
        self._record_failed_attempt(username)
        return None
    
    def _create_session(self, username: str) -> str:
        """Create a new session"""
        token = secrets.token_hex(32)
        self.sessions[token] = {
            "username": username,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=1)).isoformat()
        }
        return token
    
    def validate_session(self, token: str) -> bool:
        """Validate a session token"""
        if not token or token not in self.sessions:
            return False
        
        session = self.sessions[token]
        expires_at = datetime.fromisoformat(session["expires_at"])
        
        if datetime.now() > expires_at:
            del self.sessions[token]
            return False
        
        return True
    
    def logout(self, token: str):
        """Logout and invalidate session"""
        if token in self.sessions:
            del self.sessions[token]
    
    def _is_locked_out(self, username: str) -> bool:
        """Check if user is locked out"""
        if username not in self.login_attempts:
            return False
        
        attempts = self.login_attempts[username]
        max_attempts = self.config.get("max_login_attempts", 5)
        lockout_duration = self.config.get("lockout_duration", 300)
        
        if len(attempts) >= max_attempts:
            last_attempt = attempts[-1]
            lockout_until = last_attempt + timedelta(seconds=lockout_duration)
            if datetime.now() < lockout_until:
                return True
            else:
                self.login_attempts[username] = []
        
        return False
    
    def _record_failed_attempt(self, username: str):
        """Record a failed login attempt"""
        if username not in self.login_attempts:
            self.login_attempts[username] = []
        self.login_attempts[username].append(datetime.now())
    
    def _clear_login_attempts(self, username: str):
        """Clear login attempts for user"""
        if username in self.login_attempts:
            del self.login_attempts[username]
