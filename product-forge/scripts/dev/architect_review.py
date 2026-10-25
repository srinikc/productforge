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
import fnmatch
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVID = ROOT / "engineering" / "reviews"
CONFIG = ROOT / "config" / "architect-review.json"
API = os.environ.get("PF_API_URL", "http://127.0.0.1:8010/api/v1")
SEVERITIES = ("BLOCKER", "MAJOR", "MINOR", "NIT")
DISPOSITION_STATUSES = ("PENDING", "ACTIONED", "ACCEPTED", "DEFERRED", "REJECTED", "SCOPE")
if str(ROOT / "scripts" / "dev") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "dev"))
from gitutil import (  # noqa: E402  (shared UTF-8/fail-closed git policy)
    git_text as _git_text_shared,
)
from review_sig import digest as _finding_digest  # noqa: E402  (shared with review_learnings)

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
EXCLUDE = [
    ":(exclude,glob)**/engineering/**",
    ":(exclude,glob)**/config/architect-review-baseline.json",
    ":(exclude,glob)**/data/backlog/**",
    ":(exclude,glob)**/docs/BACKLOG-SUMMARY.md",
    ":(exclude,glob)**/docs/documentation-index.html",
]


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


_DESIGN_KEYS = ("objective", "approach", "in_scope", "out_of_scope", "acceptance_criteria",
                "affected_components", "affected_files", "risks", "rollback")


def design_sha(item: dict) -> str:
    """Canonical design hash: fixed key set, sorted JSON, absent fields as null.

    Design evidence must bind to the DESIGN, not to the (usually empty) diff: otherwise every design review
    collides on sha256("") and a re-designed item silently reuses the old approval.
    """
    payload = {k: item.get(k) for k in _DESIGN_KEYS}
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]


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


_LAST_USAGE: dict = {}

ARCHITECT_SYSTEM = (
    "You are a Principal Enterprise System Architect performing an independent review. Judge from an "
    "enterprise, long-term lens (integrity, adaptability, scalability, security, observability, "
    "maintainability, reuse). Output ONLY the sections: ### BLOCKER, ### MAJOR, ### MINOR, ### NIT, ### SUMMARY "
    "(bullet findings; write '- none' under an empty section). Do not rewrite code. "
    "Do NOT show any reasoning, analysis, preamble or sign-off: your reply MUST begin with the literal string "
    "'### BLOCKER' and contain no text before it. Keep each finding to at most 3 lines.")


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
    # Gateways intermittently answer 502/429 or an empty (reasoning-only) message; retry a few times
    # with backoff instead of failing the whole gate. Wrong-content still fails closed downstream.
    timeout = float(cfg.get("request_timeout") or os.environ.get("PF_ARCHITECT_REVIEW_TIMEOUT") or 300)
    attempts = int(cfg.get("attempts") or 3)
    last_err = None
    for attempt in range(1, attempts + 1):
        nudge = "" if attempt == 1 else (
            "\n\nIMPORTANT: the previous attempt returned no content. Respond with ONLY the required "
            "BLOCKER/MAJOR/MINOR/NIT/SUMMARY sections.")
        body = json.dumps({"model": model, "temperature": 0.2,
                           "max_tokens": int(cfg.get("max_tokens") or 16000), "messages": [
            {"role": "system", "content": ARCHITECT_SYSTEM},
            {"role": "user", "content": prompt + nudge}]}).encode("utf-8")
        req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, method="POST")
        req.add_header("Authorization", f"Bearer {key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", cfg.get("user_agent", "opencode/1.18.35"))
        req.add_header("x-opencode-session", str(uuid.uuid4()))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code not in (408, 425, 429, 500, 502, 503, 504) or attempt == attempts:
                raise RuntimeError(f"review call failed (model={model} attempt={attempt}/{attempts}): HTTP {e.code}") from e
            print(f"architect-review: attempt {attempt} HTTP {e.code}; retrying", file=sys.stderr)
            time.sleep(min(30, 5 * (2 ** (attempt - 1))))
            continue
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            if attempt == attempts:
                raise
            print(f"architect-review: attempt {attempt} failed ({e}); retrying", file=sys.stderr)
            time.sleep(min(30, 5 * (2 ** (attempt - 1))))
            continue
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        # Never treat chain-of-thought as the review: empty content stays fail-closed.
        content = (msg.get("content") or "").strip()
        if content:
            try:
                u = data.get("usage") or {}
                _LAST_USAGE.clear()
                _LAST_USAGE.update({"input_tokens": int(u.get("prompt_tokens") or 0),
                                    "output_tokens": int(u.get("completion_tokens") or 0),
                                    "cached_tokens": int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0),
                                    "model": model})
            except Exception:
                pass
            return content
        last_err = RuntimeError("review call returned empty content")
        print(f"architect-review: attempt {attempt} returned empty content; retrying", file=sys.stderr)
        if attempt < attempts:
            time.sleep(min(30, 5 * (2 ** (attempt - 1))))
    raise last_err or RuntimeError("review call failed")


def _build_prompt(item: dict, item_id: str, mode: str) -> str:
    ac = "\n".join(f"- {c}" for c in (item.get("acceptance_criteria") or [])) or "- (none)"
    body = _design_body(item) if mode == "design" else "Diff:\n```diff\n" + _git_diff()[:180000] + "\n```"
    prompt = PROMPT.format(target=("design" if mode == "design" else "implementation diff"),
                           item=item_id, ac=ac, body=body)
    if mode == "design":
        try:
            from design_guardrails import (
                render as _render_guardrails,  # BI-PF-1467: design-time learnings
            )
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


def _latest_review(item_id: str, mode: str, prefer_sha: str = ""):
    """Prefer the review for the CURRENT design/diff sha; fall back to newest mtime.

    mtime is not stable across checkouts (CI writes files in tree order), so sha selection is the only
    deterministic choice when a matching artifact exists.
    """
    if not EVID.is_dir():
        return None
    best, best_m = None, -1.0
    for fp in EVID.glob(f"{item_id}-*.json"):
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (d.get("mode") or "diff") != mode:
            continue
        if prefer_sha and str(d.get("sha") or "") == prefer_sha:
            return d
        if fp.stat().st_mtime > best_m:
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


def gate_view_sha(item_id: str, mode: str, sha: str) -> dict | None:
    """View for a SPECIFIC evidence sha (deterministic completion checks on data-only PRs)."""
    fp = EVID / f"{item_id}-{sha}.json"
    try:
        rev = json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return None
    findings = rev.get("findings") or {}
    disp = _item_dispositions(item_id, mode)
    total, pending, blocking = pending_blocking(findings, disp)
    return {"review": rev, "dispositions": disp, "total": total, "pending": pending,
            "blocking": blocking, "parsed_ok": rev.get("parsed_ok", True)}


def gate_view(item_id: str, mode: str = "design") -> dict | None:
    """Public: latest review + dispositions + pending/blocking counts (shared by `gate` + gate1_check)."""
    prefer = ""
    try:
        prefer = design_sha(_get_item(item_id)) if mode == "design" else diff_sha()
    except Exception:
        prefer = ""
    rev = _latest_review(item_id, mode, prefer)
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


def _norm_status(status) -> str:
    st = str(status or "PENDING").upper()
    return st if st in DISPOSITION_STATUSES else "PENDING"


def _is_resolved_status(status) -> bool:
    return _norm_status(status) not in ("PENDING",)


def overall_recommendation(rows: list[tuple[str, str]], parsed_ok: bool = True) -> tuple[str, str]:
    """Pure overall verdict from (severity, disposition-status) rows (worst wins).

    Fail closed: unparsable evidence or a pending BLOCKER/MAJOR is NOT READY. A resolved BLOCKER/MAJOR that
    was accepted/deferred/scope/rejected is APPROVE WITH ATTENTION; otherwise APPROVE. Unknown statuses are
    normalized to PENDING. Pending MINOR/NIT are advisory and do not block (they are counted).
    """
    counts = {s: 0 for s in SEVERITIES}
    dispo: dict[str, int] = {}
    blocking = 0
    attention = 0
    for sev, status in rows:
        sev = str(sev or "").upper()
        counts[sev] = counts.get(sev, 0) + 1
        st = _norm_status(status)
        dispo[st] = dispo.get(st, 0) + 1
        if sev in ("BLOCKER", "MAJOR"):
            if not _is_resolved_status(st):
                blocking += 1
            elif st in ("ACCEPTED", "DEFERRED", "SCOPE", "REJECTED"):
                attention += 1
    total = len(rows)
    counts_txt = (f"Findings: {total} (BLOCKER {counts.get('BLOCKER', 0)} / MAJOR {counts.get('MAJOR', 0)} / "
                  f"MINOR {counts.get('MINOR', 0)} / NIT {counts.get('NIT', 0)}); dispositions: "
                  + (", ".join(f"{k.lower()} {v}" for k, v in sorted(dispo.items())) or "none"))
    if not parsed_ok:
        return "NOT READY", f"{counts_txt}; review evidence is unparsable/missing"
    if blocking:
        return "NOT READY", f"{counts_txt}; {blocking} blocking finding(s) pending"
    if attention:
        return "APPROVE WITH ATTENTION", (f"{counts_txt}; {attention} blocker/major finding(s) "
                                          "accepted/deferred/scope/rejected")
    return "APPROVE", f"{counts_txt}; all blockers/majors actioned"


def _pending_count(rows: list[tuple[str, str]]) -> int:
    """ONE pending predicate shared by the verdict and the footer."""
    return sum(1 for _, st in rows if not _is_resolved_status(st))


def _cell(text) -> str:
    return (str(text or "").replace("\\", "\\\\").replace("|", "\\|")
            .replace("\r", " ").replace("\n", " ").strip())


def _render_review(rev: dict, disp: dict, mode: str) -> str:
    """ONE consolidated decision table: finding + disposition + response, plus the overall verdict."""
    gate = "1.5" if mode == "design" else "2.5"
    f = rev.get("findings") or {}
    rows: list[tuple[str, str, str, str]] = []
    for n, (sev, text) in enumerate(iter_findings(f), 1):
        d = _disp_for(disp, n, text)
        st = _norm_status(d.get("status"))
        rows.append((sev, st, text, d.get("note") or "(no response yet)"))
    pairs = [(r[0], r[1]) for r in rows]
    verdict, counts = overall_recommendation(pairs, parsed_ok=bool(rev.get("parsed_ok", True)))
    pending = _pending_count(pairs)
    lines = [f"Gate {gate} - Findings & Dispositions (model={rev.get('model', '?')} sha={rev.get('sha', '?')})",
             f"**Overall architect recommendation: {verdict}**",
             counts,
             "status: PENDING | ACTIONED | ACCEPTED | DEFERRED | REJECTED | SCOPE",
             "",
             "| # | Severity | Finding | Disposition | Response / resolution |",
             "|---|---|---|---|---|"]
    for n, (sev, st, text, note) in enumerate(rows, 1):
        lines.append(f"| {n} | {sev} | {_cell(text)} | {st} | {_cell(note)} |")
    lines.append("")
    lines.append("--- SUMMARY (review) ---")
    lines += [f"  {x}" for x in f.get("SUMMARY", [])]
    lines.append(f"=== {len(rows)} finding(s), {pending} pending ===")
    return "\n".join(lines)



def review_budget() -> dict:
    cfg = _config().get("review_budget") or {}
    warn = int(cfg.get("warn_after", 2))
    fail = int(cfg.get("fail_after", 4))
    if warn < 0 or fail <= warn:
        raise ValueError(f"review_budget: require 0 <= warn_after < fail_after (got {warn}, {fail})")
    return {"warn_after": warn, "fail_after": fail,
            "attesters": [str(x) for x in (cfg.get("attesters") or []) if str(x).strip()],
            "reason_max_chars": int(cfg.get("reason_max_chars", 500)),
            "scope": str(cfg.get("scope", "after_gate1"))}


def diff_reviews(item_id: str, committed: bool = False) -> list[dict]:
    """Diff-mode review evidence for an item (working tree or the committed HEAD tree)."""
    out: list[dict] = []
    if committed:
        tree = _git_text(["ls-tree", "-r", "--name-only", "HEAD", "--", "engineering/reviews"])
        if not tree.strip():
            raise RuntimeError("review evidence tree is unreadable or empty")
        for rel in tree.splitlines():
            base = Path(rel).name
            if not (base.startswith(item_id + "-") and base.endswith(".json")):
                continue
            raw = _git_text(["show", f"HEAD:{rel}"])
            if not raw:
                raise RuntimeError(f"cannot read committed review evidence {rel}")
            try:
                data = json.loads(raw)
            except Exception as e:
                raise RuntimeError(f"corrupt review evidence {rel}: {e}") from e
            if data.get("mode") == "diff":
                out.append({"path": rel, "sha": str(data.get("sha") or ""),
                            "at": str(data.get("at") or ""), "review": data})
    else:
        if not EVID.exists():
            raise RuntimeError(f"review evidence directory is missing: {EVID}")
        for fp in EVID.glob(f"{item_id}-*.json"):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except Exception as e:
                raise RuntimeError(f"corrupt review evidence {fp.name}: {e}") from e
            if data.get("mode") == "diff":
                out.append({"path": fp.name, "sha": str(data.get("sha") or ""),
                            "at": str(data.get("at") or ""), "review": data})
    out.sort(key=lambda r: (r["path"], r["sha"]))
    return out


def review_epoch(item: dict) -> str:
    """The latest Gate 1 decision in the append-only ledger order (not mtime)."""
    epoch = ""
    for d in (item.get("decisions") or []):
        try:
            g = int(d.get("gate") or 0)
        except Exception:
            g = 0
        if g == 1:
            epoch = str(d.get("at") or "")
    return epoch


def _after_epoch(at: str, epoch: str) -> bool:
    if not epoch:
        return True
    try:
        a = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        e = datetime.fromisoformat(epoch.replace("Z", "+00:00"))
        return a >= e
    except Exception:
        return True  # unparsable -> count (fail closed)


def redact_reason(s: str) -> str:
    """Redact token-like values, THEN cap (so a cap never clips a redaction marker)."""
    t = str(s or "")
    t = re.sub(r"(?i)\b(api[_-]?key|token|secret|password|authorization)\b\s*[:=]\s*\S+",
               r"\1=[REDACTED]", t)
    t = re.sub(r"(?i)\b(bearer)\s+\S+", r"\1 [REDACTED]", t)
    t = re.sub(r"(?i)(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[REDACTED]@", t)
    t = re.sub(r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", "[REDACTED-PEM]", t, flags=re.S)
    t = re.sub(r"(?i)\b(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b", "[REDACTED-KEY]", t)
    t = re.sub(r"(?i)\b(pwd|x-api-key)\s*[:=]\s*\S+", r"\1=[REDACTED]", t)
    return t[:review_budget()["reason_max_chars"]]


def churn_attested(item: dict, latest_sha: str, budget: dict) -> bool:
    attesters = [str(x) for x in (budget.get("attesters") or [])]
    for d in reversed(item.get("decisions") or []):
        if str(d.get("decision") or "").upper() != "REVIEW_CHURN":
            continue
        if d.get("hil_confirmed") is not True:
            continue
        by = str(d.get("by") or "")
        note = str(d.get("note") or "")
        if not any(fnmatch.fnmatch(by, pat) for pat in attesters):
            continue
        if len(note.strip()) < 40:
            continue
        if latest_sha and latest_sha not in note:
            continue
        return True
    return False


def _item_committed(item_id: str) -> dict:
    rel = f"data/backlog/items/{item_id}.json"
    raw = _git_text(["show", f"HEAD:{rel}"])
    if not raw:
        raise RuntimeError(f"item {item_id} is not present in HEAD")
    return json.loads(raw)


def churn_verdict(item_id: str, item: dict | None = None, committed: bool = False) -> dict:
    """Single-source churn verdict consumed by the run guard and review_churn_check."""
    if item is None:
        item = _item_committed(item_id) if committed else _get_item(item_id)
    budget = review_budget()
    reviews = diff_reviews(item_id, committed=committed)
    epoch = review_epoch(item) if budget.get("scope") == "after_gate1" else ""
    counted = [r for r in reviews if _after_epoch(r["at"], epoch)]
    count = len(counted)
    latest = max(counted, key=lambda r: (r["at"], r["path"], r["sha"]))["sha"] if counted else ""
    over = count > budget["fail_after"]
    attested = churn_attested(item, latest, budget)
    return {"item": item_id, "count": count, "warn": count > budget["warn_after"],
            "fail": over and not attested, "allowed": not (over and not attested),
            "attested": attested, "warn_after": budget["warn_after"],
            "fail_after": budget["fail_after"], "epoch": epoch, "latest_sha": latest,
            "reviews": [{"path": r["path"], "sha": r["sha"], "at": r["at"]} for r in counted]}


def reason_flag_error(rereview: bool, reason: str) -> str:
    if str(reason or "").strip() and not rereview:
        return "--reason requires --rereview"
    return ""


def review_guard(item_id: str, item: dict, rereview: bool, reason: str) -> tuple[bool, str]:
    """Refuse an undispositioned re-review; a reasoned override must cite the prior sha."""
    verdict = churn_verdict(item_id, item)
    if not verdict["reviews"]:
        return True, ""
    disp = ((item.get("review_dispositions") or {}).get("diff") or {})
    if not disp and not rereview:
        return False, ("review-churn: a prior diff review has no dispositions; disposition it before "
                       "re-review (or pass --rereview --reason citing the prior sha)")
    if rereview:
        r = str(reason or "").strip()
        if not r:
            return False, "--rereview requires a non-empty --reason"
        latest = verdict["latest_sha"]
        if latest and latest not in r:
            return False, f"--reason must cite the prior review sha {latest}"
        return True, redact_reason(r)
    return True, ""


def _ingest(item_id: str, text: str, model: str, apply: bool, mode: str = "diff",
            rereview_reason: str = "") -> int:
    findings = parse_review(text)
    # BI-PF-1465: fail closed - evidence that did not parse must never look like a clean review.
    parsed_ok = bool(re.search(r"^\s*#{2,4}\s*(BLOCKER|MAJOR|MINOR|NIT|SUMMARY)\s*$", text, re.I | re.M))
    sha = design_sha(_get_item(item_id)) if mode == "design" else diff_sha()
    EVID.mkdir(parents=True, exist_ok=True)
    out = EVID / f"{item_id}-{sha}.json"
    if rereview_reason and out.is_file():
        prev = out.with_name(f"{out.stem}-prev-{int(time.time() * 1000)}.json")
        out.rename(prev)
    payload = {"item": item_id, "sha": sha, "model": model, "mode": mode,
               "parsed_ok": parsed_ok, "at": datetime.now(timezone.utc).isoformat(),
               "findings": findings}
    if rereview_reason:
        payload["rereview_reason"] = rereview_reason
        payload["rereview_reason_sha256"] = hashlib.sha256(rereview_reason.encode("utf-8")).hexdigest()
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
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
    try:
        from core import execution_trail as trail
        stage = "design_review" if mode == "design" else "diff_review"
        counts = {s: len(findings[s]) for s in SEVERITIES}
        trail.record(item_id, stage, "fail" if blockers else "pass",
                     summary=f"{stage}: {counts}",
                     refs={"review_sha": sha, "model": model, "evidence": out.name},
                     usage=dict(_LAST_USAGE))
    except Exception as e:
        try:
            from core import execution_trail as _t
            _t.write_failure("review", e, item_id)
        except Exception:
            pass
        print(json.dumps({"event": "execution_trail_write_failed", "stage": "review", "error": str(e)}), file=sys.stderr)
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
    rn.add_argument("--rereview", action="store_true", help="allow a second review for the same item+sha")
    rn.add_argument("--reason", default="", help="required with --rereview; cite the prior review sha")
    ing = sub.add_parser("ingest")
    ing.add_argument("--item", required=True)
    ing.add_argument("--file", required=True)
    ing.add_argument("--apply", action="store_true")
    ing.add_argument("--model", default=default_model, help="reviewer model label recorded in evidence")
    g = sub.add_parser("gate")
    g.add_argument("--item", required=True)
    g.add_argument("--gate", choices=["1", "2"], required=True)
    g.add_argument("--sha", default="", help="use a specific review evidence sha (trail/history)")
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
        view = gate_view_sha(a.item, mode, a.sha) if a.sha else gate_view(a.item, mode)
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
    if a.mode == "diff":
        rerr = reason_flag_error(a.rereview, a.reason)
        if rerr:
            print(rerr)
            return 1
        ok, why = review_guard(a.item, item, a.rereview, a.reason)
        if not ok:
            print(why)
            return 1
    reason = redact_reason(getattr(a, "reason", "")) if a.rereview else ""
    sha = design_sha(item) if a.mode == "design" else diff_sha()
    existing = EVID / f"{a.item}-{sha}.json"
    if existing.is_file() and not a.rereview:
        print(f"review already exists for {a.item} sha={sha}: {existing.name}")
        print("   convergence: re-review only after code changes (or pass --rereview)")
        return 1
    prompt = _build_prompt(item, a.item, a.mode)
    try:
        out = _llm_call(prompt, a.model)
    except Exception as e:
        print(f"review call failed: {e}")
        return 2
    if not out.strip():
        print("review call returned empty content")
        return 2
    return _ingest(a.item, out, a.model, a.apply, a.mode, rereview_reason=reason)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
