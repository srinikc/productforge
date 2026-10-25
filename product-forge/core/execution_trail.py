"""Backlog execution trail (BI-PF-1481, flow view BI-PF-1483).

One append-only, registered store per item: engineering/trails/<ID>.json. The gate tools write the stages
automatically; `show` renders one ordered flow: plain-language brief, Gate 0 reconciliation + impact,
a stage checklist with the current stage, the Gate 1.5/2.5 tables + recommendations, the Gate 1/2 decisions,
implementation/code review, tests, usage, the final table and the disposition key.

Stages (in order): planning, gate0, design_review, gate1, implementation, code_review, diff_review, gate2,
tests, precheck, pr, merge, delivery, completion.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAILS = ROOT / "engineering" / "trails"
SCHEMA = "pf.execution-trail/1"
PRICING = ROOT / "config" / "model-pricing.json"
STAGES = ("planning", "gate0", "design_review", "gate1", "implementation", "code_review",
          "diff_review", "gate2", "tests", "precheck", "pr", "merge", "delivery", "completion")
REQUIRED_AT_COMPLETION = ("planning", "gate0", "design_review", "gate1", "implementation",
                          "code_review", "diff_review", "gate2", "tests", "precheck", "completion")
MAX_EVENTS = 5000
MAX_SUMMARY = 2000
FAILURES = TRAILS / "_failures.jsonl"
_SECRET = re.compile(r"(?i)\b(api[_-]?key|token|secret|password|authorization)\b\s*[:=]\s*\S+")
_BEARER = re.compile(r"(?i)\b(bearer)\s+\S+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(s) -> str:
    t = str(s or "")
    t = _SECRET.sub(r"\1=[REDACTED]", t)
    t = _BEARER.sub(r"\1 [REDACTED]", t)
    return t[:MAX_SUMMARY]


def _path(item: str) -> Path:
    if not re.match(r"^BI-[A-Za-z0-9]+-\d+$", item or ""):
        raise ValueError(f"invalid item id {item!r}")
    return TRAILS / f"{item}.json"


def _lock(path: Path, timeout: float = 10.0):
    lock = path.with_suffix(".lock")
    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return lock
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 60:
                    lock.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.time() > deadline:
                raise TimeoutError(f"execution trail lock timeout: {lock}")
            time.sleep(0.05)


def _load(item: str) -> dict:
    p = _path(item)
    if not p.is_file():
        return {"schema": SCHEMA, "item": item, "updated_at": _now(), "events": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"unsupported trail schema {data.get('schema')!r}")
    return data


def _write(item: str, data: dict) -> None:
    p = _path(item)
    p.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def write_failure(stage: str, error: Exception, item: str = "") -> None:
    """Durable alert sink for a trail write failure (the failing trail cannot record its own failure)."""
    try:
        TRAILS.mkdir(parents=True, exist_ok=True)
        lock = _lock(FAILURES)
        try:
            with open(FAILURES, "a", encoding="utf-8") as f:
                f.write(json.dumps({"at": _now(), "item": item, "stage": stage,
                                    "error": _redact(str(error))}) + "\n")
        finally:
            try:
                lock.unlink()
            except FileNotFoundError:
                pass
    except Exception:
        pass


def record(item: str, stage: str, status: str = "pass", summary: str = "", refs: dict | None = None,
           tests: list | None = None, usage: dict | None = None, actor: str = "tool",
           duration_ms: int = 0) -> dict:
    """Append one event (append-only, monotonically sequenced). Raises on an invalid item/stage."""
    if stage not in STAGES:
        raise ValueError(f"unknown trail stage {stage!r}")
    p = _path(item)
    TRAILS.mkdir(parents=True, exist_ok=True)
    lock = _lock(p)
    try:
        data = _load(item)
        events = data.setdefault("events", [])
        if len(events) >= MAX_EVENTS:
            raise RuntimeError(f"execution trail exceeds {MAX_EVENTS} events")
        ev = {"seq": (events[-1]["seq"] + 1 if events else 1), "at": _now(), "stage": stage,
              "actor": _redact(actor), "status": str(status or "pass"),
              "summary": _redact(summary), "refs": refs or {}, "tests": tests or [],
              "usage": price_usage(usage or {}), "duration_ms": int(duration_ms or 0)}
        events.append(ev)
        _write(item, data)
        return ev
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def events(item: str) -> list[dict]:
    return list(_load(item).get("events") or [])


def _stage_events(item: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for ev in events(item):
        out[ev["stage"]] = ev
    return out


def missing_stages(item: str, required=REQUIRED_AT_COMPLETION) -> list[str]:
    have = _stage_events(item)
    return [s for s in required if s not in have]


def order_problems(item: str) -> list[str]:
    """Critical review/decision ordering: design before Gate 1, diff before Gate 2."""
    have = _stage_events(item)
    bad = []
    for first, second in (("design_review", "gate1"), ("diff_review", "gate2")):
        if first in have and second in have and have[first]["seq"] > have[second]["seq"]:
            bad.append(f"{first} must be recorded before {second}")
    return bad


def _item(item: str) -> dict:
    from core import backlog
    it = backlog.get_epic("product_forge", None, item)
    if not it:
        raise KeyError(f"backlog item {item} not found")
    return it


def next_item(item: str) -> tuple[str, str]:
    it = _item(item)
    epic = str(it.get("epic") or "")
    from core import backlog
    open_items = [x for x in backlog.list_items("product_forge", None) if x.get("id") != item
                  and str(x.get("status") or "").lower() not in ("completed", "closed", "done")]
    rows = [x for x in open_items if not epic or x.get("epic") == epic]
    rows.sort(key=lambda x: (x.get("priority_rank") or 999, -(x.get("score") or 0), x.get("id", "")))
    if not rows:
        return "", ""
    return str(rows[0].get("id") or ""), str(rows[0].get("title") or "")



_PRICING_CACHE: dict | None = None


def _pricing() -> dict:
    global _PRICING_CACHE
    if _PRICING_CACHE is None:
        try:
            _PRICING_CACHE = json.loads(PRICING.read_text(encoding="utf-8"))
        except Exception:
            _PRICING_CACHE = {"models": {}, "aliases": {}}
    return _PRICING_CACHE


def normalize_model(model: str) -> str:
    s = str(model or "").strip().lower().split(":")[0]
    s = s.rsplit("/", 1)[-1]
    aliases = _pricing().get("aliases") or {}
    return str(aliases.get(str(model or "").strip().lower()) or aliases.get(s) or s)


def price_usage(usage: dict) -> dict:
    """Add cost_usd/cost_source. Provider cost wins; unknown/invalid usage is explicitly unavailable."""
    u = dict(usage or {})
    if not u or u.get("not_captured"):
        return u
    model = normalize_model(u.get("model") or "")
    inp = int(u.get("input_tokens") or 0)
    out = int(u.get("output_tokens") or 0)
    cached = int(u.get("cached_tokens") or 0)
    prov = u.get("provider_cost_usd")
    if prov is not None:
        u["cost_usd"] = round(float(prov), 6)
        u["cost_source"] = "provider"
        return u
    p = (_pricing().get("models") or {}).get(model)
    if not p:
        u["cost_source"] = "unavailable"
        return u
    if inp < 0 or out < 0 or cached < 0 or cached > inp:
        u["cost_source"] = "invalid_usage"
        return u
    computed = ((inp - cached) * float(p.get("input") or 0)
                + cached * float(p.get("cached_input") or 0)
                + out * float(p.get("output") or 0)) / 1_000_000.0
    u["cost_usd"] = round(computed, 6)
    u["cost_source"] = "opencode-data"
    u["model"] = model
    return u


def _box(headers: list, rows: list, widths: list | None = None) -> str:
    """Cursor-style Unicode box table with wrapped cells."""
    n = len(headers)
    cells = [[str(c) if c is not None else "" for c in r] for r in rows]
    if widths is None:
        widths = []
        for i in range(n):
            w = max([len(str(headers[i]))] + [len(c[i]) for c in cells if i < len(c)])
            widths.append(min(max(w, 4), 44))

    def wrap(c, w):
        return textwrap.wrap(str(c), width=w, break_long_words=True, replace_whitespace=False) or [""]

    top = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    bot = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    def line(vals):
        return "|" + "|".join(" " + str(vals[i]).ljust(widths[i]) + " " for i in range(n)) + "|"

    out = [top, line(headers), sep]
    for r in cells:
        wr = [wrap(r[i] if i < len(r) else "", widths[i]) for i in range(n)]
        h = max(len(x) for x in wr)
        for j in range(h):
            out.append(line([wr[i][j] if j < len(wr[i]) else "" for i in range(n)]))
    out.append(bot)
    return "\n".join(out)


def usage_totals(evs: list[dict]) -> dict:
    total = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "cost_usd": 0.0,
             "captured": 0, "not_captured": 0, "unpriced": 0}
    for ev in evs:
        u = ev.get("usage") or {}
        if not u:
            continue
        if u.get("not_captured"):
            total["not_captured"] += 1
            continue
        u = price_usage(u)
        total["captured"] += 1
        total["input_tokens"] += int(u.get("input_tokens") or 0)
        total["output_tokens"] += int(u.get("output_tokens") or 0)
        total["cached_tokens"] += int(u.get("cached_tokens") or 0)
        total["cost_usd"] += float(u.get("cost_usd") or 0)
        if u.get("cost_usd") is None:
            total["unpriced"] += 1
    return total


def _review_evidence(item: str, mode: str) -> tuple[str, str]:
    """Return (rendered Gate 1.5/2.5 table, current architect recommendation)."""
    stage = "design_review" if mode == "design" else "diff_review"
    ev = _stage_events(item).get(stage)
    if not ev:
        return f"({stage}: no evidence)", ""
    sha = str((ev.get("refs") or {}).get("review_sha") or "")
    try:
        import subprocess
        gate = "1" if mode == "design" else "2"
        cmd = [sys.executable, str(ROOT / "scripts" / "dev" / "architect_review.py"),
               "gate", "--item", item, "--gate", gate]
        if sha:
            cmd += ["--sha", sha]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        out = (r.stdout or "").strip()
        if not out:
            return f"({stage}: evidence missing)", ""
        m = re.search(r"Overall architect recommendation:\s*\**\s*([A-Z ]+?)\s*\**\s*$", out, re.M)
        return out, (m.group(1).strip() if m else "")
    except Exception as e:
        return f"({stage}: cannot render: {e})", ""


def _review_table(item: str, mode: str) -> str:
    return _review_evidence(item, mode)[0]


def current_stage(item: str) -> str:
    """The first required stage with no committed event, or 'complete'."""
    have = _stage_events(item)
    for stage in STAGES:
        if stage not in have:
            return stage
    return "complete"


def _as_rows(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return ["; ".join(f"{k}: {value[k]}" for k in value)]
    if isinstance(value, (list, tuple)):
        out = []
        for row in value:
            if isinstance(row, dict):
                out.append("; ".join(f"{k}: {row[k]}" for k in row))
            else:
                out.append(str(row))
        return out
    return [str(value)]


def _decision(item: dict, gate: int) -> dict:
    for d in item.get("decisions") or []:
        if str((d or {}).get("gate") or "") == str(gate):
            return d
    return {}


def show(item: str) -> str:
    it = _item(item)
    evs = events(item)
    have = _stage_events(item)
    current = current_stage(item)
    design_table, design_rec = _review_evidence(item, "design")
    diff_table, diff_rec = _review_evidence(item, "diff")
    brief = it.get("brief") or {}
    lines = [f"# Execution trail - {item}", f"**Title:** {it.get('title')}",
             f"**Status:** {it.get('status')}  **Epic:** {it.get('epic')}",
             f"**Current stage:** {current}", ""]

    runs: dict[str, int] = {}
    for ev in evs:
        runs[ev["stage"]] = runs.get(ev["stage"], 0) + 1
    stage_rows = []
    for stage in STAGES:
        ev = have.get(stage)
        if not ev:
            continue
        status = ev["status"]
        if stage == "design_review" and design_rec:
            status = design_rec
        elif stage == "diff_review" and diff_rec:
            status = diff_rec
        stage_rows.append([ev["seq"], stage, status, ev["at"], f"{ev.get('duration_ms', 0)} ms",
                           f"{runs.get(stage, 1)}", str(ev.get("summary") or "")])
    if not stage_rows:
        stage_rows = [["-", "(no events yet)", "-", "-", "-", "-", "-"]]
    lines.append(_box(["#", "Stage", "Status", "At", "Duration", "Runs", "Summary"], stage_rows,
                      widths=[4, 15, 14, 28, 10, 5, 44]))

    lines += ["", "## 1. Plain language"]
    for label, key in (("What it is", "problem"), ("What it adds", "what_adds"),
                       ("Why now", "why_now"), ("Who", "who"), ("Success", "success")):
        if brief.get(key):
            lines.append(f"**{label}:** {brief.get(key)}")
    if not any(brief.get(k) for k in ("problem", "what_adds", "why_now", "who", "success")):
        lines.append(f"**What it is:** {it.get('objective') or it.get('title') or ''}")

    rev = it.get("review") or {}
    recon = rev.get("reconciliation") or {}
    lines += ["", "## 2. Gate 0 - reconciliation and impact"]
    for label, key in (("PRIOR DECISIONS", "prior_decisions"), ("EXISTING PATH", "existing_path"),
                       ("ASSUMPTIONS", "assumptions"), ("DIVERGENCES", "divergences"),
                       ("OPEN QUESTIONS", "open_questions")):
        rows = _as_rows(recon.get(key))
        lines.append(f"**{label}:**" + (" none" if not rows else ""))
        lines += [f"- {r}" for r in rows]
    impact = rev.get("impact_review") or []
    if impact:
        irows = []
        for row in impact:
            if isinstance(row, dict):
                irows.append([row.get("claim", ""), row.get("verdict", ""),
                              row.get("evidence", ""), row.get("recommendation", "")])
            else:
                irows.append([str(row), "", "", ""])
        lines += ["", _box(["Claim", "Verdict", "Evidence", "Recommendation"], irows,
                           widths=[34, 12, 34, 30])]

    lines += ["", "## 3. Flow - where we are", f"**Current stage:** {current}", ""]
    for stage in STAGES:
        ev = have.get(stage)
        if not ev:
            mark = "[CURRENT]" if stage == current else "[PENDING]"
            lines.append(f"- {mark} {stage}")
            continue
        status = ev.get("status") or "pass"
        if stage == "design_review" and design_rec:
            status = design_rec
        elif stage == "diff_review" and diff_rec:
            status = diff_rec
        lines.append(f"- [DONE] {stage} ({status}) - {ev.get('at', '')}")

    lines += ["", "## 4. Gate 1.5 - design review",
              f"**Architect recommendation:** {design_rec or 'not recorded'}", "", design_table]
    g1 = _decision(it, 1)
    lines += ["", "## 5. Gate 1 - design decision"]
    if g1:
        lines += [f"**Decision:** {g1.get('decision')} | **By:** {g1.get('by')} | **At:** {g1.get('at')}"]
        if g1.get("note"):
            lines.append(f"**Note:** {g1.get('note')}")
    else:
        lines.append("Not recorded.")

    lines += ["", "## 6. Implementation and code review"]
    for stage in ("implementation", "code_review"):
        ev = have.get(stage)
        lines.append(f"- **{stage}:** " + (f"{ev.get('status')} - {ev.get('summary')}"
                                           if ev else "not recorded"))

    lines += ["", "## 7. Gate 2.5 - delivery review",
              f"**Architect recommendation:** {diff_rec or 'not recorded'}", "", diff_table]
    g2 = _decision(it, 2)
    lines += ["", "## 8. Gate 2 - delivery decision"]
    if g2:
        lines += [f"**Decision:** {g2.get('decision')} | **By:** {g2.get('by')} | **At:** {g2.get('at')}"]
        if g2.get("note"):
            lines.append(f"**Note:** {g2.get('note')}")
    else:
        lines.append("Not recorded.")

    tests = [t for ev in evs for t in (ev.get("tests") or [])]
    test_rows = [[t.get('command', ''), t.get('result', ''), f"{t.get('duration_ms', 0)} ms",
                  t.get('passed', ''), t.get('failed', ''), t.get('skipped', '')] for t in tests]
    if not test_rows:
        test_rows = [["(none recorded)", "-", "-", "-", "-", "-"]]
    lines += ["", "## 9. Tests", _box(["Command", "Result", "Duration", "Passed", "Failed", "Skipped"],
                                       test_rows, widths=[36, 8, 10, 7, 7, 8])]

    u = usage_totals(evs)
    lines += ["", "## 10. Usage", f"input={u['input_tokens']} output={u['output_tokens']} "
              f"cached={u['cached_tokens']} cost_usd={u['cost_usd']:.6f} "
              f"captured={u['captured']} not_captured={u['not_captured']} unpriced={u['unpriced']}"]
    delivery = (it.get("links") or {}).get("delivery") or {}
    total_ms = 0
    if evs:
        try:
            start = datetime.fromisoformat(evs[0]["at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(evs[-1]["at"].replace("Z", "+00:00"))
            total_ms = int((end - start).total_seconds() * 1000)
        except Exception:
            total_ms = sum(int(e.get("duration_ms") or 0) for e in evs)
    nid, ntitle = next_item(item)
    final_rows = [
        ["Item", item],
        ["What it was", it.get("title") or ""],
        ["What shipped", it.get("summary") or it.get("objective") or ""],
        ["Current stage", current],
        ["PR / Merge", f"{delivery.get('pr') or '-'} / {delivery.get('merge_sha') or '-'}"],
        ["Tests", f"{len(tests)} test row(s)"],
        ["Total time", f"{total_ms} ms ({total_ms / 1000.0:.1f}s)"],
        ["Tokens in/out/cached", f"{u['input_tokens']} / {u['output_tokens']} / {u['cached_tokens']}"],
        ["Cost (USD)", f"{u['cost_usd']:.6f} (captured={u['captured']} unpriced={u['unpriced']})"],
        ["Next", f"{nid or '-'} {ntitle}"],
    ]
    lines += ["", "## 11. Final completion", _box(["Field", "Value"], final_rows, widths=[20, 72])]
    lines += ["", "## Disposition key",
              "- **ACTIONED** - fixed or committed in this item (Gate 1.5: design/plan updated; Gate 2.5: code/docs changed).",
              "- **ACCEPTED** - not fixed; the risk is explicitly accepted with a rationale (no follow-up unless a backlog id is named).",
              "- **DEFERRED** - not fixed; must cite a follow-up backlog id (BI-PF-...); completion fails without one.",
              "- **REJECTED** - finding is invalid or not applicable; no change.",
              "- **SCOPE** - outside this item; the note must name the owning item/scope."]
    missing = missing_stages(item)
    lines += ["", f"**Required-at-completion missing:** {', '.join(missing) if missing else 'none'}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backlog execution trail")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sh = sub.add_parser("show")
    sh.add_argument("--item", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--item", required=True)
    rec.add_argument("--stage", required=True, choices=STAGES)
    rec.add_argument("--status", default="pass")
    rec.add_argument("--summary", default="")
    rec.add_argument("--actor", default="tool")
    rec.add_argument("--refs", default="{}", help="JSON object")
    rec.add_argument("--tests", default="[]", help="JSON array")
    rec.add_argument("--usage", default="{}", help="JSON object")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if a.cmd == "show":
        print(show(a.item))
        return 0
    try:
        refs, tests, usage = json.loads(a.refs), json.loads(a.tests), json.loads(a.usage)
    except Exception as e:
        print(f"execution-trail: invalid JSON: {e}", file=sys.stderr)
        return 2
    record(a.item, a.stage, a.status, a.summary, refs, tests, usage, a.actor)
    print(f"execution-trail: recorded {a.stage} for {a.item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
