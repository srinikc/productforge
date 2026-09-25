"""
Multi-model review (4.2).

Sends a design/architecture artifact to several independent models and
aggregates their verdicts (majority pass/fail) with per-model reasoning.
Provider/endpoint/key are resolved by the caller (ModelRouter) - nothing is
hardcoded here.
"""
import json
import re
from typing import Dict, List, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


_KIND_PROMPTS = {
    "architecture": ("architecture document",
                     "Does it cover: architecture style + rationale, tech stack, components, "
                     "file structure, data model, deployment, integration points, security, and ADRs?"),
    "design": ("design document",
               "Does it cover: functional requirements (FR-*), non-functional requirements (NFR-*), "
               "user stories (US-*), design direction, components, data models, and API contracts?"),
}

_REVIEW_INSTRUCTION = (
    "You are a strict, independent reviewer. Read the {kind} and answer: {question}\n"
    "Respond with ONLY JSON (no prose, no fences):\n"
    '{{"verdict": "pass"|"fail", "confidence": 0.0, "issues": ["..."], "summary": "<one line>"}}'
)


def build_prompt(kind: str, files_text: str) -> str:
    desc, question = _KIND_PROMPTS.get(kind, ("document", "Is it complete and correct?"))
    instr = _REVIEW_INSTRUCTION.format(kind=desc, question=question)
    return instr + "\n\n--- DOCUMENT ---\n" + (files_text or "")[:24000]


def _post(reviewer: Dict, prompt: str, timeout: int = 120) -> Optional[Dict]:
    if requests is None:
        return None
    provider = reviewer.get("provider", "")
    endpoint = reviewer.get("api_endpoint", "")
    key = reviewer.get("api_key", "")
    model = reviewer.get("model", "")
    if not endpoint or not key or not model:
        return None
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
               "User-Agent": "product-forge-pipeline/1.0"}
    if provider in ("opencode-go", "opencode-zen"):
        headers["x-opencode-session"] = "multi-review"
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://opencode.ai"
        headers["X-Title"] = "ProductForgePipeline"
    try:
        r = requests.post(endpoint, json={"model": model,
                                          "messages": [{"role": "user", "content": prompt}],
                                          "max_tokens": 1200, "temperature": 0.2},
                          headers=headers, timeout=timeout)
        if r.status_code != 200:
            return None
        content = (r.json().get("choices", [{}])[0].get("message", {}) or {}).get("content", "") or ""
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text).strip()
        try:
            obj = json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            obj = json.loads(m.group(0)) if m else {}
        verdict = str(obj.get("verdict", "")).lower()
        if verdict not in ("pass", "fail"):
            return None
        return {"model": model, "verdict": verdict,
                "confidence": float(obj.get("confidence", 0.5) or 0.5),
                "issues": obj.get("issues", []) or [], "summary": obj.get("summary", "")}
    except Exception:
        return None


def review(kind: str, files_text: str, reviewers: List[Dict]) -> Optional[Dict]:
    """Call each reviewer; return aggregated verdict or None if none responded."""
    prompt = build_prompt(kind, files_text)
    results = []
    for rev in reviewers:
        out = _post(rev, prompt)
        if out:
            results.append(out)
    if not results:
        return None
    passes = [r for r in results if r["verdict"] == "pass"]
    passed = len(passes) > (len(results) / 2)
    issues = [i for r in results for i in (r.get("issues") or [])]
    return {
        "kind": kind,
        "passed": passed,
        "consensus": f"{len(passes)}/{len(results)}",
        "reviewers": results,
        "issues": issues[:20],
    }
