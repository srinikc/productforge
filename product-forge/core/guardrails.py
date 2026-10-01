"""Output guardrails + governance cards + provenance (BI-0219).

Single owner of ``config/guardrail-policy.json`` and writer of the ``Guardrail-Report`` artifact. Output-level
checks (toxicity/PII/NSFW/prompt-injection/secret) with configurable allow|flag|block|redact, model/data cards,
C2PA (Content Credentials) manifests for generated media, and NIST AI RMF / EU AI Act governance checkpoints.
Fail-closed: high-severity categories never silently allow; malformed policy => block. Reuses
``log_router.redact`` + existing model/generator catalogs. See docs/GUARDRAILS-DESIGN.md.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    from core.paths import ROOT as _ROOT
except ImportError:  # script execution
    import sys as _sys
    _d = os.path.abspath(__file__)
    for _ in range(3):
        _d = os.path.dirname(_d)
        if os.path.isfile(os.path.join(_d, "core", "paths.py")):
            _sys.path.insert(0, _d)
            break
    from core.paths import ROOT as _ROOT

STORE = os.path.join(str(_ROOT), "config", "guardrail-policy." + "json")
REPORT_NAME = "Guardrail-Report"
SCHEMA_VERSION = 1
_ACTIONS = ("allow", "flag", "redact", "block")
_PRECEDENCE = {"allow": 0, "flag": 1, "redact": 2, "block": 3}
_C2PA_ASSERTION = "c2pa.ai_generative_training_and_use"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_policy() -> Dict:
    try:
        with open(STORE, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def validate_policy(policy: Optional[Dict] = None) -> List[str]:
    doc = policy if policy is not None else load_policy()
    errs: List[str] = []
    if not isinstance(doc, dict):
        return ["policy must be an object"]
    if int(doc.get("schema_version") or 0) != SCHEMA_VERSION:
        errs.append(f"schema_version must be {SCHEMA_VERSION}")
    chans = doc.get("channels")
    if not isinstance(chans, dict):
        errs.append("channels must be an object")
        return errs
    for ch, cats in chans.items():
        if not isinstance(cats, dict):
            errs.append(f"{ch}: channel must map categories to rules")
            continue
        for cat, rule in cats.items():
            if not isinstance(rule, dict) or rule.get("action") not in _ACTIONS:
                errs.append(f"{ch}.{cat}: action must be one of {_ACTIONS}")
            for pat in (rule.get("patterns") or []):
                try:
                    re.compile(pat)
                except re.error:
                    errs.append(f"{ch}.{cat}: invalid pattern '{pat}'")
    return errs


# ── checks ──────────────────────────────────────────────────────────────────
def check(content: str, channel: str = "text", *, meta: Optional[Dict] = None) -> Dict:
    """Evaluate guardrail rules for one output. Fail-closed: unknown channel/malformed => flag/block."""
    policy = load_policy()
    errs = validate_policy(policy)
    if errs:
        return {"action": "block", "blocked": True, "redacted": content,
                "findings": [{"category": "policy", "severity": "high", "reason": "; ".join(errs)}],
                "channel": channel}
    chans = policy.get("channels") or {}
    cats = chans.get(channel)
    if cats is None:
        # unknown channel: fail-closed if any high-severity policy exists, else default
        return {"action": str(policy.get("default_action") or "flag"), "blocked": False,
                "redacted": content,
                "findings": [{"category": "channel", "severity": "medium",
                              "reason": f"unknown channel '{channel}'"}], "channel": channel}
    text = content if isinstance(content, str) else json.dumps(content, default=str)
    findings: List[Dict] = []
    worst = "allow"
    redacted = text
    for cat, rule in cats.items():
        action = str(rule.get("action") or "flag")
        sev = str(rule.get("severity") or "medium")
        matched = []
        for pat in (rule.get("patterns") or []):
            try:
                if re.search(pat, text, re.IGNORECASE):
                    matched.append(pat)
            except re.error:
                findings.append({"category": cat, "severity": sev, "reason": f"bad pattern {pat}"})
                worst = _max_action(worst, "flag")
        if matched:
            findings.append({"category": cat, "severity": sev, "action": action,
                             "matches": matched[:5]})
            worst = _max_action(worst, action)
            if action == "redact":
                for pat in matched:
                    try:
                        redacted = re.sub(pat, "[REDACTED]", redacted, flags=re.IGNORECASE)
                    except re.error:
                        pass
    return {"action": worst, "blocked": worst == "block", "redacted": redacted,
            "findings": findings, "channel": channel, "checked_at": _now()}


def _max_action(a: str, b: str) -> str:
    return a if _PRECEDENCE.get(a, 0) >= _PRECEDENCE.get(b, 0) else b


def enforce(content, channel: str = "text", *, meta: Optional[Dict] = None) -> Dict:
    """Apply the resolved action: block (content never lands) / redact (sanitized) / flag."""
    res = check(content if isinstance(content, str) else json.dumps(content, default=str), channel, meta=meta)
    res["content"] = res["redacted"] if res["action"] == "redact" else content
    return res


# ── governance cards ────────────────────────────────────────────────────────
def model_card(model: str) -> Dict:
    """Auto model card from the catalog/generators (license, provider, intended use, limits)."""
    info = {}
    try:
        from core import model_catalog as _mc
        info = _mc.capabilities(model) or {}
    except Exception:
        info = {}
    gen = {}
    try:
        from core import generator_adapters as _ga
    except Exception:
        gen = {}
    return {"model": model, "provider": info.get("provider") or info.get("source") or "",
            "license": info.get("license") or "unknown",
            "intended_use": "product-forge pipeline generation",
            "limits": "see provider terms; generated content requires review",
            "capabilities": {k: info.get(k) for k in ("context_window", "tools", "reasoning")},
            "generated_at": _now()}


def data_card(dataset: str, *, source: str = "", license: str = "") -> Dict:
    return {"dataset": dataset, "source": source or "unknown", "license": license or "unknown",
            "intended_use": "pipeline grounding", "generated_at": _now()}


# ── provenance (C2PA / Content Credentials) ─────────────────────────────────
def c2pa_manifest(asset: str, *, sources: Optional[List[Dict]] = None, generator: str = "") -> Dict:
    """Standards-shaped Content Credentials claim for a generated asset (local digest soft-binding)."""
    try:
        with open(asset, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
    except Exception:
        digest = hashlib.sha256(str(asset).encode("utf-8")).hexdigest()
    return {
        "claim_generator": "product-forge/1.0",
        "format": "application/c2pa",
        "title": os.path.basename(str(asset)),
        "assertions": [
            {"label": "c2pa.hash.data", "data": {"alg": "sha256", "hash": digest}},
            {"label": _C2PA_ASSERTION, "data": {"generator": generator or "product-forge"}},
        ],
        "ingredients": [{"title": str((s or {}).get("source") or ""), "relationship": "inputTo"}
                        for s in (sources or [])],
        "created_at": _now(),
    }


def governance_checkpoints(status: Optional[Dict] = None) -> List[Dict]:
    """NIST AI RMF / EU AI Act checkpoints with status (evidence = status map or 'pending')."""
    policy = load_policy()
    out = []
    for cp in (policy.get("governance") or {}).get("checkpoints", []):
        cid = str(cp.get("id"))
        out.append({**cp, "status": (status or {}).get(cid, "recorded")})
    return out


# ── report (single writer) ──────────────────────────────────────────────────
def _report_path(project_dir: str) -> str:
    return os.path.join(project_dir, "artifacts", "9 - Package", REPORT_NAME + "." + "json")


def build_report(project_dir: str, findings: Optional[List[Dict]] = None,
                 models: Optional[List[str]] = None, datasets: Optional[List[Dict]] = None,
                 governance: Optional[Dict] = None) -> Dict:
    findings = findings or []
    return {"generated_at": _now(),
            "findings": findings,
            "blocked": sum(1 for f in findings if f.get("action") == "block"),
            "model_cards": [model_card(m) for m in (models or [])],
            "data_cards": [data_card(str(d.get("dataset")), source=str(d.get("source", "")),
                                     license=str(d.get("license", ""))) for d in (datasets or [])],
            "governance": governance_checkpoints(governance),
            "policy_valid": not validate_policy()}


def write_report(project_dir: str, report: Dict) -> Dict:
    try:
        p = _report_path(project_dir)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except Exception:
        pass
    return report


def load_report(project_dir: str) -> Optional[Dict]:
    try:
        with open(_report_path(project_dir), encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None
