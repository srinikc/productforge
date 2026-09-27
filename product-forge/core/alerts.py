"""Alerts — out-of-band notification (email) + human ask-and-wait for doubts.

Config: config/alerts.json (owner: this module). Email is opt-in and stores only the
ENV VAR NAME for the password (never the secret). Used when the pipeline is in doubt
(e.g., unclear product brief): send an email AND ask the user, waiting for an answer.

Owner: this module.
"""
import json
import os
import smtplib
from email.mime.text import MIMEText
from typing import Dict, List, Optional

_CFG_REL = ("config", "alerts.json")
_PRIORITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _cfg() -> Dict:
    try:
        from core.paths import ROOT
        with open(os.path.join(str(ROOT), *_CFG_REL), "r", encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _email_cfg() -> Dict:
    return (_cfg().get("email") or {})


def email(subject: str, message: str, priority: str = "high") -> Dict:
    """Best-effort email alert. Returns {sent, reason}. Never raises."""
    c = _email_cfg()
    minp = str(_cfg().get("email_min_priority", "high")).lower()
    if not c.get("enabled"):
        return {"sent": False, "reason": "email disabled"}
    if _PRIORITY_ORDER.get(str(priority).lower(), 1) < _PRIORITY_ORDER.get(minp, 2):
        return {"sent": False, "reason": f"below email_min_priority ({minp})"}
    host = c.get("smtp_host")
    to = c.get("to") or []
    if not host or not to:
        return {"sent": False, "reason": "smtp_host/recipients not configured"}
    user = c.get("username") or ""
    pwd = os.getenv(str(c.get("password_env") or "ALERT_SMTP_PASSWORD"), "")
    if user and not pwd:
        return {"sent": False, "reason": f"password env '{c.get('password_env')}' not set"}
    try:
        msg = MIMEText(str(message), "plain", "utf-8")
        msg["Subject"] = str(subject)
        msg["From"] = c.get("from") or user or "product-forge@localhost"
        msg["To"] = ", ".join(to)
        port = int(c.get("smtp_port", 587) or 587)
        s = smtplib.SMTP(host, port, timeout=30)
        try:
            if c.get("use_tls", True):
                s.starttls()
            if user:
                s.login(user, pwd)
            s.sendmail(msg["From"], list(to), msg.as_string())
        finally:
            try:
                s.quit()
            except Exception:
                pass
        return {"sent": True, "reason": "ok"}
    except Exception as e:
        return {"sent": False, "reason": f"send failed: {e}"}


def ask_and_wait(question: str, project_dir: str = "",
                 subject: str = "Clarification needed", timeout: Optional[float] = None) -> str:
    """Email the doubt, then ASK the human and WAIT for the answer.

    Bridges headlessly (writes prompts.json) so it can wait even in auto runs; the
    wait honours a cross-process control=stop. clarify_timeout_seconds=0 => wait.
    """
    try:
        email(subject, question, priority="high")
    except Exception:
        pass
    try:
        os.environ.setdefault("PIPELINE_INTERACTIVE", "1")
        from core import interactive
        if timeout is None:
            t = float(_cfg().get("clarify_timeout_seconds", 0) or 0)
            timeout = 10 ** 9 if t <= 0 else t
        return interactive.ask(question, default="", project_dir=project_dir,
                               kind="clarify", timeout=timeout) or ""
    except Exception:
        return ""


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Alerts: email + ask-and-wait")
    ap.add_argument("--test-email", action="store_true")
    a = ap.parse_args()
    if a.test_email:
        print(json.dumps(email("[Product Forge] test alert", "This is a test alert.",
                               priority="high"), indent=2))
    else:
        print(json.dumps({"email_config": _email_cfg()}, indent=2))
