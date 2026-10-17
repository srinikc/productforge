"""Gate 2.5 / Gate 1.5 - second-model Architect review helper (BI-PF-1427, docs/REVIEW-GATES-LIFECYCLE.md).

Provider- and model-AGNOSTIC. The reviewer is a SEPARATE fresh-context sub-agent on a configurable model
(default from config/architect-review.json, e.g. mimo-v2.6-flash; override --model / PF_ARCHITECT_REVIEW_MODEL
to gemini/claude/anything). Nothing here is coupled to OpenCode or Mimo: `run` launches whatever command the
config `launch_command` names.

Commands:
  emit   --item ID [--mode design|diff]                 : print the fresh-context reviewer prompt.
  run    --item ID [--mode design|diff] [--apply]        : call the provider endpoint directly (LLM), ingest.
  ingest --item ID --file review.md [--apply]            : ingest an externally-produced review.

ingest parses BLOCKER/MAJOR/MINOR/NIT -> engineering/reviews/<item>-<sha>.json; --apply appends the summary
to the item context. Exit 1 when a BLOCKER is present (objectively verifiable only). NOT inside precheck.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVID = ROOT / "engineering" / "reviews"
CONFIG = ROOT / "config" / "architect-review.json"
API = os.environ.get("PF_API_URL", "http://127.0.0.1:8010/api/v1")
SEVERITIES = ("BLOCKER", "MAJOR", "MINOR", "NIT")

PROMPT = """You are a Principal Enterprise System Architect performing an independent review.

Review the {target}. Judge from an ENTERPRISE, LONG-TERM perspective: integrity, adaptability, scalability,
security, observability, maintainability, reuse (no duplication), and "are we doing the right thing".
Do NOT rewrite code; produce findings.

Item: {item}
Acceptance Criteria:
{ac}

Standards: follow AGENTS.md, docs/ENGINEERING_OPERATING_STANDARD.md, docs/ARCHITECTURE-DECISIONS.md
(language rule: new shipped logic -> Go; edits to shipped Python allowed; tooling Python OK).

{body}

Output format (exact headings, bullet findings):
### BLOCKER
- <objectively verifiable blocker, e.g. data loss, secret, RLS bypass, missing migration/test, language-rule violation>
### MAJOR
- <design/robustness issue>
### MINOR
- <minor>
### NIT
- <nit>
### SUMMARY
- <2-5 lines: overall verdict + top risks>
"""


def _config() -> dict:
    """Provider/model-agnostic config (config/architect-review.json). Any model id is valid."""
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _token() -> str:
    tok = os.environ.get("PF_API_TOKEN", "")
    if tok:
        return tok
    try:
        return (ROOT / "data" / "local" / "dev-api-token").read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _get_item(item: str) -> dict:
    req = urllib.request.Request(f"{API.rstrip('/')}/backlog/items/{item}", method="GET")
    req.add_header("Authorization", f"Bearer {_token()}")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8")).get("data") or {}


# The review sha must NOT change when the review itself (evidence) or its baseline is committed, so both are
# excluded from the hashed diff. The SAME exclusions are used by scripts/dev/architect_review_check.py.
EXCLUDE = [":(exclude)engineering/reviews/**", ":(exclude)config/architect-review-baseline.json"]


def _merge_base() -> str:
    try:
        mb = subprocess.run(["git", "merge-base", "origin/develop", "HEAD"], cwd=str(ROOT),
                            capture_output=True, text=True, timeout=30).stdout.strip()
        return mb or "origin/develop"
    except Exception:
        return "origin/develop"


def _git_diff() -> str:
    # Committed diff only (merge-base..HEAD): stable across precheck's own writing gates and equal to the CI PR
    # diff. The developer commits the change, runs the review (evidence committed next), then pushes.
    try:
        return subprocess.run(["git", "diff", "--no-color", f"{_merge_base()}..HEAD", "--", ".", *EXCLUDE],
                              cwd=str(ROOT), capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return ""


def changed_files() -> list:
    try:
        out = subprocess.run(["git", "diff", "--name-only", f"{_merge_base()}..HEAD", "--", ".", *EXCLUDE],
                             cwd=str(ROOT), capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def diff_sha() -> str:
    return hashlib.sha256(_git_diff().encode("utf-8")).hexdigest()[:12]


def _design_body(item: dict) -> str:
    keys = ("objective", "approach", "in_scope", "out_of_scope", "acceptance_criteria",
            "affected_components", "affected_files", "risks", "rollback")
    return "Design / Gate-1 context:\n" + "\n".join(f"- {k}: {item.get(k)}" for k in keys if item.get(k))


def parse_review(text: str) -> dict:
    out = {s: [] for s in SEVERITIES}
    out["SUMMARY"] = []
    cur = None
    for line in text.splitlines():
        m = re.match(r"^\s*#{2,4}\s*(BLOCKER|MAJOR|MINOR|NIT|SUMMARY)\s*$", line, re.IGNORECASE)
        if m:
            cur = m.group(1).upper()
            continue
        if cur and re.match(r"^\s*[-*]\s+", line):
            out[cur].append(re.sub(r"^\s*[-*]\s+", "", line).strip())
    return out


ARCHITECT_SYSTEM = (
    "You are a Principal Enterprise System Architect performing an independent review. Judge from an "
    "enterprise, long-term lens (integrity, adaptability, scalability, security, observability, "
    "maintainability, reuse). Output ONLY the sections: ### BLOCKER, ### MAJOR, ### MINOR, ### NIT, ### SUMMARY "
    "(bullet findings; write '- none' under an empty section). Do not rewrite code.")


def _api_key() -> str:
    key = (os.environ.get("OPENCODE_ZEN_API_KEY") or os.environ.get("PF_ARCHITECT_REVIEW_KEY") or "").strip()
    if key:
        return key
    for p in (ROOT / ".opencode" / "opencode.key", ROOT / "opencode.key"):
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return ""


def _llm_call(prompt: str, model: str) -> str:
    """Call the OpenAI-compatible provider endpoint DIRECTLY (no nested CLI/agent runtime).

    Default: OpenCode Go gateway (provider `opencode-go`) which serves `mimo-v2.6-flash`; it requires the
    routing header `x-opencode-session`. Model/provider/base are all configurable (config or env), so any
    gateway/model can be used.
    """
    cfg = _config()
    base = (os.environ.get("PF_ARCHITECT_REVIEW_BASE_URL") or cfg.get("base_url")
            or "https://opencode.ai/zen/go/v1")
    key = _api_key()
    if not key:
        raise RuntimeError("no API key (set OPENCODE_ZEN_API_KEY or provide .opencode/opencode.key)")
    body = json.dumps({"model": model, "temperature": 0.2, "max_tokens": 4000, "messages": [
        {"role": "system", "content": ARCHITECT_SYSTEM},
        {"role": "user", "content": prompt}]}).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", cfg.get("user_agent", "opencode/1.18.35"))
    req.add_header("x-opencode-session", str(uuid.uuid4()))
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read().decode("utf-8"))
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    return msg.get("content") or msg.get("reasoning_content") or ""


def _build_prompt(item: dict, item_id: str, mode: str) -> str:
    ac = "\n".join(f"- {c}" for c in (item.get("acceptance_criteria") or [])) or "- (none)"
    body = _design_body(item) if mode == "design" else "Diff:\n```diff\n" + _git_diff()[:60000] + "\n```"
    return PROMPT.format(target=("design" if mode == "design" else "implementation diff"),
                         item=item_id, ac=ac, body=body)


def _post_context(item_id: str, lines: list) -> None:
    body = json.dumps({"verification": lines}).encode("utf-8")
    req = urllib.request.Request(f"{API.rstrip('/')}/backlog/items/{item_id}/context", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {_token()}")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Roles", "operator")
    urllib.request.urlopen(req, timeout=15).read()


def _ingest(item_id: str, text: str, model: str, apply: bool) -> int:
    findings = parse_review(text)
    sha = diff_sha()
    EVID.mkdir(parents=True, exist_ok=True)
    out = EVID / f"{item_id}-{sha}.json"
    out.write_text(json.dumps({"item": item_id, "sha": sha, "model": model, "findings": findings},
                              indent=2), encoding="utf-8")
    counts = {s: len(findings[s]) for s in SEVERITIES}
    print(f"review captured: {out} {counts}")
    blockers = findings["BLOCKER"]
    if apply:
        summary = "; ".join(blockers) if blockers else "no blockers"
        _post_context(item_id, [f"Gate2.5 architect review ({counts}): {summary}"])
        print("summary appended to item context")
    return 1 if blockers else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Gate 2.5 / 1.5 architect review (BI-PF-1427).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    default_model = os.environ.get("PF_ARCHITECT_REVIEW_MODEL") or _config().get("model", "mimo-v2.6-flash")
    e = sub.add_parser("emit")
    e.add_argument("--item", required=True)
    e.add_argument("--mode", choices=["design", "diff"], default="diff")
    e.add_argument("--model", default=default_model, help="reviewer model label (configurable)")
    rn = sub.add_parser("run")
    rn.add_argument("--item", required=True)
    rn.add_argument("--mode", choices=["design", "diff"], default="diff")
    rn.add_argument("--apply", action="store_true")
    rn.add_argument("--model", default=default_model, help="reviewer model id (configurable)")
    ing = sub.add_parser("ingest")
    ing.add_argument("--item", required=True)
    ing.add_argument("--file", required=True)
    ing.add_argument("--apply", action="store_true")
    ing.add_argument("--model", default=default_model, help="reviewer model label recorded in evidence")
    a = ap.parse_args(argv)

    item = _get_item(a.item)
    if a.cmd == "emit":
        print(f"Reviewer model: {a.model}\n")
        print(_build_prompt(item, a.item, a.mode))
        return 0
    if a.cmd == "ingest":
        return _ingest(a.item, Path(a.file).read_text(encoding="utf-8"), a.model, a.apply)

    prompt = _build_prompt(item, a.item, a.mode)
    try:
        out = _llm_call(prompt, a.model)
    except Exception as e:
        print(f"review call failed: {e}")
        return 2
    if not out.strip():
        print("review call returned empty content")
        return 2
    return _ingest(a.item, out, a.model, a.apply)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
