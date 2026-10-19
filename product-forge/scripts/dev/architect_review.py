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
DISPOSITION_STATUSES = ("PENDING", "ACTIONED", "ACCEPTED", "DEFERRED", "REJECTED")
if str(ROOT / "scripts" / "dev") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "dev"))
from review_sig import digest as _finding_digest  # noqa: E402  (shared with review_learnings)
from gitutil import git_text as _git_text_shared  # noqa: E402  (shared UTF-8/fail-closed git policy)

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


def _ba():
    """In-process Backlog API module (no dev_server/URL/port)."""
    p = str(ROOT / "scripts" / "dev")
    if p not in sys.path:
        sys.path.insert(0, p)
    import backlog_api
    return backlog_api


def _get_item(item: str) -> dict:
    try:
        return _ba().get_item(item) or {}
    except Exception:
        from core import backlog as _b
        return _b.get_epic("product_forge", None, item) or {}


# The review sha covers SOURCE changes only - it must not change when derived/generated artifacts move
# (committed evidence, the baseline, the derived backlog projections that --apply itself writes). The SAME
# exclusions are used by scripts/dev/architect_review_check.py.
EXCLUDE = [":(exclude)engineering/**", ":(exclude)config/architect-review-baseline.json",
           ":(exclude)data/backlog/**"]


def _git_text(args: list[str], timeout: int = 30) -> str:
    """Run git through the shared UTF-8/fail-closed helper (BI-PF-1464)."""
    return _git_text_shared(args, ROOT, timeout)


def _merge_base() -> str:
    mb = _git_text(["merge-base", "origin/develop", "HEAD"]).strip()
    return mb or "origin/develop"


def _git_diff() -> str:
    # Committed diff only (merge-base..HEAD): stable across precheck's own writing gates and equal to the CI PR
    # diff. The developer commits the change, runs the review (evidence committed next), then pushes.
    return _git_text(["diff", "--no-color", f"{_merge_base()}..HEAD", "--", ".", *EXCLUDE])


def changed_files() -> list:
    out = _git_text(["diff", "--name-only", f"{_merge_base()}..HEAD", "--", ".", *EXCLUDE])
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
    prompt = PROMPT.format(target=("design" if mode == "design" else "implementation diff"),
                           item=item_id, ac=ac, body=body)
    if mode == "design":
        try:
            from design_guardrails import render as _render_guardrails  # BI-PF-1467: design-time learnings
            prompt += "\n\n" + _render_guardrails(item, item_id)
        except Exception:
            cl = [str(q) for q in (_config().get("design_checklist") or []) if str(q).strip()]
            if cl:
                prompt += ("\n\nDesign pre-check checklist (verify each is addressed; report a finding for any gap):\n"
                           + "\n".join(f"- {q}" for q in cl))
    return prompt


def _post_context(item_id: str, payload: dict) -> None:
    # In-process Backlog API (no dev_server/URL/port).
    _ba().set_context(item_id, payload)


def review_block(findings: dict, model: str, sha: str, mode: str) -> str:
    """Human-readable findings block (BLOCKER/MAJOR/MINOR/NIT/SUMMARY + recommendation), stated IN the gate review."""
    gate = "1.5" if mode == "design" else "2.5"
    lines = [f"Gate {gate} architect review - model={model} sha={sha}"]
    for s in SEVERITIES:
        lines.append(f"{s}:")
        lines += [f"  - {x}" for x in findings.get(s, [])] or ["  - none"]
    lines.append("SUMMARY:")
    lines += [f"  - {x}" for x in findings.get("SUMMARY", [])] or ["  - none"]
    rec = "BLOCKED - objectively verifiable blocker(s) present" if findings.get("BLOCKER") else \
        "no hard blocker (MAJOR/MINOR/NIT advisory; HIL decides)"
    lines.append(f"RECOMMENDATION: {rec}")
    return "\n".join(lines)


def _latest_review(item_id: str, mode: str):
    if not EVID.is_dir():
        return None
    best, best_m = None, -1.0
    for fp in EVID.glob(f"{item_id}-*.json"):
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (d.get("mode") or "diff") == mode and fp.stat().st_mtime > best_m:
            best, best_m = d, fp.stat().st_mtime
    return best


def _item_dispositions(item_id: str, mode: str) -> dict:
    """Dispositions are MAIN-THREAD-owned and stored ON THE ITEM (context.review_dispositions[gate]),
    not in the reviewer tool. The reviewer only produces findings; the owner records the response/action."""
    try:
        item = _get_item(item_id)
    except Exception:
        return {}
    d = item.get("review_dispositions") or {}
    if isinstance(d, dict):
        return d.get(mode) or d.get("design" if mode == "design" else "diff") or {}
    return {}


def finding_sig(text: str) -> str:
    """Stable content key for a finding (shared implementation; so dispositions survive reordering)."""
    return _finding_digest(text)


def _disp_for(dispositions: dict, n: int, text: str) -> dict:
    """Disposition for a finding: a non-PENDING content-hash key wins, then ordinal (legacy).

    A ``sig:<digest>`` entry that is still PENDING must not shadow a valid ordinal disposition.
    Unknown statuses are treated as PENDING (fail-closed).
    """
    d = dispositions or {}
    sig = d.get("sig:" + finding_sig(text)) or {}
    ordi = d.get(str(n)) or {}
    for cand in (sig, ordi):
        if _is_resolved(cand):
            return cand
    return sig or ordi


def _is_resolved(d: dict) -> bool:
    st = str((d or {}).get("status") or "").upper()
    return st in DISPOSITION_STATUSES and st != "PENDING"


def iter_findings(findings: dict):
    """Yield (severity, text) in the canonical severity order (stable disposition numbering).

    The reviewer's explicit ``- none`` placeholder for an empty section is not a finding.
    """
    for sev in SEVERITIES:
        for text in (findings or {}).get(sev, []) or []:
            if str(text).strip().lower() in ("none", "", "-"):
                continue
            yield sev, text


def pending_blocking(findings: dict, dispositions: dict):
    """Return (total, pending, blocking) for a review.

    ``blocking`` lists (n, severity, text) for BLOCKER/MAJOR findings that have no non-PENDING
    disposition. A finding is matched by its content-hash key (``sig:<digest>``) first, then by
    ordinal for legacy records. Pending MINOR/NIT never block (BI-PF-1449).
    """
    total = pending = 0
    blocking = []
    for n, (sev, text) in enumerate(iter_findings(findings), 1):
        total += 1
        if not _is_resolved(_disp_for(dispositions, n, text)):
            pending += 1
            if sev in ("BLOCKER", "MAJOR"):
                blocking.append((n, sev, text))
    return total, pending, blocking


def gate_view(item_id: str, mode: str = "design") -> dict | None:
    """Public: latest review + dispositions + pending/blocking counts (shared by `gate` + gate1_check)."""
    rev = _latest_review(item_id, mode)
    if not rev:
        return None
    findings = rev.get("findings") or {}
    disp = _item_dispositions(item_id, mode)
    total, pending, blocking = pending_blocking(findings, disp)
    return {"review": rev, "dispositions": disp, "total": total, "pending": pending, "blocking": blocking,
            "parsed_ok": rev.get("parsed_ok", True)}


def render_gate_view(view: dict, mode: str) -> str:
    """Public renderer for a gate view (reuses the ONE consolidated renderer)."""
    return _render_review(view["review"], view["dispositions"], mode)


def _render_review(rev: dict, disp: dict, mode: str) -> str:
    """ONE consolidated section: each finding with OUR response + status beside it."""
    gate = "1.5" if mode == "design" else "2.5"
    f = rev.get("findings") or {}
    lines = [f"Gate {gate} - Findings & Dispositions (model={rev.get('model','?')} sha={rev.get('sha','?')})",
             "status: PENDING | actioned | accepted | deferred | rejected"]
    n, pending = 0, 0
    for n, (sev, text) in enumerate(iter_findings(f), 1):
        d = _disp_for(disp, n, text)
        st = (d.get("status") or "PENDING").upper()
        if not _is_resolved(d):
            pending += 1
        lines.append(f"[{sev}] #{n} ({st})")
        lines.append(f"  finding : {text}")
        lines.append(f"  response: {d.get('note') or '(no response yet)'}")
    lines.append("--- SUMMARY (review) ---")
    lines += [f"  {x}" for x in f.get("SUMMARY", [])]
    lines.append(f"=== {n} finding(s), {pending} pending ===")
    return "\n".join(lines)


def _ingest(item_id: str, text: str, model: str, apply: bool, mode: str = "diff") -> int:
    findings = parse_review(text)
    # BI-PF-1465: fail closed - evidence that did not parse must never look like a clean review.
    parsed_ok = bool(re.search(r"^\s*#{2,4}\s*(BLOCKER|MAJOR|MINOR|NIT|SUMMARY)\s*$", text, re.I | re.M))
    sha = diff_sha()
    EVID.mkdir(parents=True, exist_ok=True)
    out = EVID / f"{item_id}-{sha}.json"
    out.write_text(json.dumps({"item": item_id, "sha": sha, "model": model, "mode": mode,
                               "parsed_ok": parsed_ok, "findings": findings}, indent=2), encoding="utf-8")
    counts = {s: len(findings[s]) for s in SEVERITIES}
    print(f"review captured: {out} {counts}")
    blockers = findings["BLOCKER"]
    if apply:
        gate = "1.5" if mode == "design" else "2.5"
        item = _get_item(item_id)
        ev = list(item.get("evidence") or [])
        ev.append(review_block(findings, model, sha, mode))
        _post_context(item_id, {"evidence": ev,
                                "verification": [f"Gate {gate} architect review ({model}): {counts}"]})
        print(f"Gate {gate} findings stored on item (evidence + verification)")
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
    g = sub.add_parser("gate")
    g.add_argument("--item", required=True)
    g.add_argument("--gate", choices=["1", "2"], required=True)
    ck = sub.add_parser("checklist")
    ck.add_argument("--item", required=True)
    ck.add_argument("--record", action="store_true", help="append the completed checklist to item evidence")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if a.cmd == "checklist":
        questions = [str(q) for q in (_config().get("design_checklist") or []) if str(q).strip()]
        print("Design pre-check (answer BEFORE Gate 1.5; BI-PF-1449):")
        for i, q in enumerate(questions, 1):
            print(f"  {i}. [ ] {q}")
        if not questions:
            print("  (config/architect-review.json has no design_checklist entries)")
        if a.record and questions:
            item = _get_item(a.item)
            marker = f"Design pre-check ({a.item}):"
            ev = list(item.get("evidence") or [])
            if any(str(x).startswith(marker) for x in ev):
                print("already recorded on item evidence (idempotent)")
            else:
                ev.append(f"{marker} answered {len(questions)} checklist item(s) before Gate 1.5")
                _post_context(a.item, {"evidence": ev})
                print("recorded on item evidence")
        return 0
    if a.cmd == "emit":
        item = _get_item(a.item)
        print(f"Reviewer model: {a.model}\n")
        print(_build_prompt(item, a.item, a.mode))
        return 0
    if a.cmd == "ingest":
        return _ingest(a.item, Path(a.file).read_text(encoding="utf-8"), a.model, a.apply)
    if a.cmd == "gate":
        mode = "design" if a.gate == "1" else "diff"
        gate = "1.5" if mode == "design" else "2.5"
        print(f"=== GATE {a.gate} REVIEW - {a.item} (informed by Gate {gate}) ===")
        view = gate_view(a.item, mode)
        if not view:
            print(f"(no Gate {gate} evidence - run: python scripts/dev/architect_review.py run "
                  f"--item {a.item} --mode {mode})")
            return 1
        print(render_gate_view(view, mode))
        if a.gate == "1" and not view.get("parsed_ok", True):
            print("gate1: FAIL - review evidence could not be parsed (indeterminate); re-run the review")
            return 2
        if a.gate == "1" and view["blocking"]:
            print(f"gate1: FAIL - {len(view['blocking'])} BLOCKER/MAJOR finding(s) still PENDING - "
                  "disposition them before approving Gate 1")
            return 1
        return 0

    if a.mode == "design":
        n = len([q for q in (_config().get("design_checklist") or []) if str(q).strip()])
        print(f"design pre-check: {n} checklist item(s) included in the review prompt")
    item = _get_item(a.item)
    prompt = _build_prompt(item, a.item, a.mode)
    try:
        out = _llm_call(prompt, a.model)
    except Exception as e:
        print(f"review call failed: {e}")
        return 2
    if not out.strip():
        print("review call returned empty content")
        return 2
    return _ingest(a.item, out, a.model, a.apply, a.mode)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
