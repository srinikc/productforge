"""Functional spec contract: validate, render, and freeze engineering/specs/<ID>.md."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if p not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402

SPEC_DIR = ROOT / "engineering" / "specs"
CFG = ROOT / "config" / "functional-spec.json"


def _cfg() -> dict:
    return json.loads(CFG.read_text(encoding="utf-8-sig"))


def _date(v) -> date | None:
    s = str(v or "")
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return date.fromisoformat(s)


def should_enforce(item: dict, cfg: dict) -> bool:
    if str(item.get("id") or "") in (cfg.get("enforce_items") or []):
        return True
    created = _date(item.get("created_at"))
    start = _date(cfg.get("enforce_from"))
    return bool(created and start and created >= start)


def _sha(spec: dict) -> str:
    data = {k: v for k, v in spec.items() if k not in ("functional_sha", "generated_at")}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


def _has_placeholder(text: str, cfg: dict) -> bool:
    low = text.lower()
    return any(t in low for t in (cfg.get("placeholder_tokens") or []))


def _nonempty(v) -> bool:
    if isinstance(v, (list, dict)):
        return bool(v)
    return bool(str(v or "").strip())


def problems(item: dict, cfg: dict | None = None) -> list[str]:
    cfg = cfg or _cfg()
    if not should_enforce(item, cfg):
        return []
    spec = item.get("functional_spec")
    if not isinstance(spec, dict) or not spec:
        return ["functional_spec missing"]
    bad: list[str] = []
    for key in cfg.get("required_sections") or []:
        if not _nonempty(spec.get(key)):
            bad.append(f"functional_spec.{key} missing")
    for key in ("version", "status", "owner", "source", "outcome", "design_ref"):
        if _nonempty(spec.get(key)) and _has_placeholder(str(spec.get(key)), cfg):
            bad.append(f"functional_spec.{key} contains a placeholder")
    reqs = spec.get("requirements")
    if not isinstance(reqs, list) or not reqs:
        bad.append("functional_spec.requirements must be a non-empty list")
        return bad
    ids = []
    for i, fr in enumerate(reqs, 1):
        if not isinstance(fr, dict):
            bad.append(f"functional_spec.requirements[{i}] must be an object")
            continue
        for key in cfg.get("required_fr_fields") or []:
            if not _nonempty(fr.get(key)):
                bad.append(f"FR[{i}].{key} missing")
        fid = str(fr.get("id") or "")
        if not re.fullmatch(r"FR-\d+", fid):
            bad.append(f"FR[{i}].id must match FR-<n> (got {fid!r})")
        elif fid in ids:
            bad.append(f"duplicate functional requirement {fid}")
        ids.append(fid)
        acc = " ".join(str(x) for x in (fr.get("acceptance") or [])).lower()
        for token in ("given", "when", "then"):
            if token not in acc:
                bad.append(f"{fid}.acceptance missing {token}")
        for key in ("id", "title", "preconditions", "trigger", "inputs", "outputs",
                    "errors", "auth", "idempotency", "data_rules", "edge_cases",
                    "acceptance", "verification"):
            if _has_placeholder(str(fr.get(key) or ""), cfg):
                bad.append(f"{fid}.{key} contains a placeholder")
    trace = spec.get("traceability")
    if not isinstance(trace, list) or not trace:
        bad.append("functional_spec.traceability must be a non-empty list")
    else:
        traced = {str(r.get("fr") or "") for r in trace if isinstance(r, dict)}
        for fid in ids:
            if fid not in traced:
                bad.append(f"traceability missing {fid}")
        for r in trace:
            if isinstance(r, dict):
                for key in ("fr", "design", "test", "evidence"):
                    if not _nonempty(r.get(key)):
                        bad.append(f"traceability row {r.get('fr') or '?'} missing {key}")
    frozen = str(spec.get("functional_sha") or "")
    if not frozen:
        bad.append("functional_sha missing (freeze the functional spec)")
    elif frozen != _sha(spec):
        bad.append(f"functional_sha stale (expected {_sha(spec)})")
    return bad


def _join(v) -> str:
    if isinstance(v, list):
        return "\n".join(f"- {x}" for x in v) or "- none"
    if isinstance(v, dict):
        return "\n".join(f"- **{k}**: {v[k]}" for k in v) or "- none"
    return str(v or "- none")


def _fr_text(reqs) -> str:
    out = []
    for fr in reqs or []:
        if not isinstance(fr, dict):
            continue
        out.append(f"### {fr.get('id')} — {fr.get('title')}")
        for key in ("priority", "source", "preconditions", "trigger", "inputs", "outputs",
                    "errors", "auth", "idempotency", "data_rules", "edge_cases",
                    "acceptance", "verification"):
            val = fr.get(key)
            if isinstance(val, list):
                val = "; ".join(str(x) for x in val)
            out.append(f"- **{key}:** {val}")
        out.append("")
    return "\n".join(out) or "- none"


def _rows(rows, keys) -> str:
    out = []
    for r in rows or []:
        if isinstance(r, dict):
            out.append("| " + " | ".join(str(r.get(k) or "") for k in keys) + " |")
    return "\n".join(out) or "| - | - | - | - | - | - |"


def _trace_rows(rows) -> str:
    out = []
    for r in rows or []:
        if isinstance(r, dict):
            ev = r.get("evidence")
            if isinstance(ev, list):
                ev = ", ".join(str(x) for x in ev)
            out.append(f"| {r.get('fr','')} | {r.get('design','')} | {r.get('test','')} | {ev or ''} |")
    return "\n".join(out) or "| - | - | - | - |"


def render(item: dict) -> str:
    spec = item.get("functional_spec") or {}
    tpl = (ROOT / "templates" / "FUNCTIONAL-SPEC.md").read_text(encoding="utf-8-sig")
    return (tpl.replace("{{ITEM}}", str(item.get("id") or ""))
              .replace("{{TITLE}}", str(item.get("title") or ""))
              .replace("{{VERSION}}", str(spec.get("version") or 1))
              .replace("{{STATUS}}", str(spec.get("status") or ""))
              .replace("{{OWNER}}", str(spec.get("owner") or ""))
              .replace("{{SOURCE}}", str(spec.get("source") or ""))
              .replace("{{FUNCTIONAL_SHA}}", str(spec.get("functional_sha") or ""))
              .replace("{{DESIGN_REF}}", str(spec.get("design_ref") or ""))
              .replace("{{OUTCOME}}", _join(spec.get("outcome")))
              .replace("{{ACTORS}}", _join(spec.get("actors")))
              .replace("{{SCOPE}}", _join(spec.get("scope")))
              .replace("{{NON_GOALS}}", _join(spec.get("non_goals")))
              .replace("{{ASSUMPTIONS}}", _join(spec.get("assumptions")))
              .replace("{{DEPENDENCIES}}", _join(spec.get("dependencies")))
              .replace("{{DOMAIN}}", _join(spec.get("domain")))
              .replace("{{REQUIREMENTS}}", _fr_text(spec.get("requirements")))
              .replace("{{OPERATION_MATRIX}}", _rows(spec.get("operation_matrix"), ("mode", "operation", "scope", "actor", "expected", "error")))
              .replace("{{CONFIG_CONTRACT}}", _rows(spec.get("config_contract"), ("name", "default", "precedence", "valid_values", "empty_behavior", "invalid_behavior", "startup_validation")))
              .replace("{{NFR}}", _join(spec.get("nfr")))
              .replace("{{DATA_LIFECYCLE}}", _join(spec.get("data_lifecycle")))
              .replace("{{COMPATIBILITY}}", _join(spec.get("compatibility")))
              .replace("{{ROLLBACK}}", _join(spec.get("rollback")))
              .replace("{{OBSERVABILITY}}", _join(spec.get("observability")))
              .replace("{{TRACEABILITY}}", _trace_rows(spec.get("traceability")))
              .replace("{{OPEN_QUESTIONS}}", _join(spec.get("open_questions")))
              .replace("{{DOD}}", _join(spec.get("dod"))))


def fresh(item: dict) -> bool:
    path = SPEC_DIR / f"{item.get('id')}.md"
    if not path.is_file():
        return False
    return path.read_text(encoding="utf-8").split("\n", 2)[-1] == render(item).split("\n", 2)[-1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Functional spec check/render")
    ap.add_argument("--item", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args(argv)
    cfg = _cfg()
    if a.all:
        bad = []
        for item in backlog.list_items("product_forge", None):
            if should_enforce(item, cfg):
                bad += [f"{item.get('id')}: {p}" for p in problems(item, cfg)]
                if a.fresh and not fresh(item):
                    bad.append(f"{item.get('id')}: generated functional spec is stale")
        print("functional-spec: " + ("OK" if not bad else "FAIL"))
        for x in bad:
            print("  - " + x)
        return 1 if bad else 0
    if not a.item:
        print("functional-spec: --item or --all required", file=sys.stderr)
        return 2
    item = backlog.get_epic("product_forge", None, a.item) or {}
    bad = problems(item, cfg)
    if a.render:
        SPEC_DIR.mkdir(parents=True, exist_ok=True)
        (SPEC_DIR / f"{a.item}.md").write_text(render(item), encoding="utf-8")
        print(f"functional-spec: wrote {SPEC_DIR / (a.item + '.md')}")
    if a.fresh and not fresh(item):
        bad.append("generated functional spec is stale")
    if a.check:
        print("functional-spec: " + ("OK" if not bad else "FAIL"))
        for x in bad:
            print("  - " + x)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
