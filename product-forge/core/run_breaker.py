"""
Run Breaker & Alerts

A single hard wall for a pipeline run plus rate-based loop detection, as
recommended by agent-cost practice:
  - hard cost/token breach            -> STOP
  - soft budget beyond variance band  -> THROTTLE (degrade) + alert
  - token rate spike (runaway loop)   -> THROTTLE then STOP + alert
Alerts are de-duplicated and persisted to products/<project>/alerts.json.
"""
import json
import os
import time
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional


WARN_PCT = 70.0
CRIT_PCT = 90.0


@dataclass
class BreakerDecision:
    action: str  # continue | warn | throttle | stop
    reason: str = ""
    metric: str = ""


class RunBreaker:
    def __init__(self, project: str, products_dir: str = "products",
                 budget_spec: Optional[Dict] = None,
                 rate_window_s: int = 60,
                 rate_limit_tokens_per_min: Optional[int] = None):
        self.project = project
        self.products_dir = products_dir
        self.alerts_file = os.path.join(products_dir, project, "alerts.json")
        spec = budget_spec or {}

        def _pos(v):
            """Treat missing/zero/negative budgets as UNSET (never 'instantly reached')."""
            try:
                v = float(v)
            except (TypeError, ValueError):
                return None
            return v if v > 0 else None

        self.soft_cost = _pos(spec.get("soft_cost"))
        self.hard_cost = _pos(spec.get("hard_cost"))
        self.soft_tokens = _pos(spec.get("soft_tokens"))
        self.hard_tokens = _pos(spec.get("hard_tokens"))
        self.variance = float(spec.get("variance_percent")
                              or spec.get("tolerance_percent") or 10)
        self.rate_limit = int(rate_limit_tokens_per_min
                              or spec.get("rate_limit_tokens_per_min") or 400000)
        self.rate_window = rate_window_s

        self.total_tokens = 0
        self.total_cost = 0.0
        self.usage = deque()  # (timestamp, tokens)
        self.alerts: List[Dict] = []
        self._fired = set()
        self._stopped = False
        self._load()

    # ── persistence ──────────────────────────────────────────────
    def _load(self):
        try:
            if os.path.exists(self.alerts_file):
                with open(self.alerts_file, "r", encoding="utf-8") as f:
                    self.alerts = json.load(f)
                    for a in self.alerts:
                        self._fired.add(a.get("key", ""))
        except Exception:
            self.alerts = []

    def _save(self):
        try:
            with open(self.alerts_file, "w", encoding="utf-8") as f:
                json.dump(self.alerts, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _alert(self, key: str, level: str, metric: str, message: str):
        if key in self._fired:
            return
        self._fired.add(key)
        self.alerts.append({
            "key": key, "level": level, "metric": metric,
            "message": message, "timestamp": datetime.now().isoformat(),
        })
        self._save()
        print(f"[BREAKER:{level.upper()}] {message}")

    # ── evaluation ───────────────────────────────────────────────
    def add_usage(self, tokens: int, cost: float, now: Optional[float] = None) -> BreakerDecision:
        if self._stopped:
            return BreakerDecision("stop", "run already stopped", "run")
        now = now or time.time()
        self.total_tokens += int(tokens or 0)
        self.total_cost += float(cost or 0.0)
        self.usage.append((now, int(tokens or 0)))
        while self.usage and (now - self.usage[0][0]) > self.rate_window:
            self.usage.popleft()

        # 1) rate-based loop detection
        window_tokens = sum(t for _, t in self.usage)
        if window_tokens > self.rate_limit:
            self._alert("rate", "critical", "rate",
                        f"Token rate {window_tokens}/{self.rate_window}s exceeds {self.rate_limit} "
                        f"(possible runaway loop)")
            self._stopped = True
            return BreakerDecision("stop", "token-rate loop detected", "rate")

        # 2) hard ceilings -> STOP
        if self.hard_cost is not None and self.total_cost >= self.hard_cost:
            self._alert("hard_cost", "critical", "cost",
                        f"Hard cost budget reached (${self.total_cost:.4f} >= ${self.hard_cost})")
            self._stopped = True
            return BreakerDecision("stop", "hard cost budget reached", "cost")
        if self.hard_tokens is not None and self.total_tokens >= self.hard_tokens:
            self._alert("hard_tokens", "critical", "tokens",
                        f"Hard token budget reached ({self.total_tokens} >= {self.hard_tokens})")
            self._stopped = True
            return BreakerDecision("stop", "hard token budget reached", "tokens")

        # 3) soft budget beyond variance band -> THROTTLE
        if self.soft_cost is not None:
            limit = self.soft_cost * (1 + self.variance / 100.0)
            if self.total_cost > limit:
                self._alert("soft_cost_tol", "critical", "cost",
                            f"Soft cost +{self.variance:.0f}% exceeded (${self.total_cost:.4f} > ${limit:.4f})")
                return BreakerDecision("throttle", "soft cost beyond variance", "cost")
            if self.total_cost >= self.soft_cost * (CRIT_PCT / 100.0):
                self._alert("soft_cost_crit", "warning", "cost",
                            f"Cost at {self.total_cost / self.soft_cost * 100:.0f}% of soft budget")
        if self.soft_tokens is not None:
            limit = self.soft_tokens * (1 + self.variance / 100.0)
            if self.total_tokens > limit:
                self._alert("soft_tokens_tol", "critical", "tokens",
                            f"Soft token +{self.variance:.0f}% exceeded ({self.total_tokens} > {int(limit)})")
                return BreakerDecision("throttle", "soft tokens beyond variance", "tokens")
            if self.total_tokens >= self.soft_tokens * (CRIT_PCT / 100.0):
                self._alert("soft_tokens_crit", "warning", "tokens",
                            f"Tokens at {self.total_tokens / self.soft_tokens * 100:.0f}% of soft budget")

        # 4) soft warning thresholds
        if self.soft_cost is not None and self.total_cost >= self.soft_cost * (WARN_PCT / 100.0):
            self._alert("soft_cost_warn", "warning", "cost",
                        f"Cost at {self.total_cost / self.soft_cost * 100:.0f}% of soft budget")
        if self.soft_tokens is not None and self.total_tokens >= self.soft_tokens * (WARN_PCT / 100.0):
            self._alert("soft_tokens_warn", "warning", "tokens",
                        f"Tokens at {self.total_tokens / self.soft_tokens * 100:.0f}% of soft budget")

        return BreakerDecision("continue", "")

    def status(self) -> Dict:
        return {
            "project": self.project,
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 8),
            "soft_cost": self.soft_cost,
            "hard_cost": self.hard_cost,
            "variance_percent": self.variance,
            "rate_limit_tokens_per_min": self.rate_limit,
            "stopped": self._stopped,
            "alerts": self.alerts,
        }

    def get_alerts(self) -> List[Dict]:
        return self.alerts
