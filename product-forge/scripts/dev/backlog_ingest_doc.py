"""Ingest a plan/design document and project its sections onto backlog items via the API (BI-PF-1396).

Text is extracted with the existing owner ``core.intake_files.extract`` (supports .md/.txt/.doc/.docx/.pdf/.rtf).
The document is split into per-item sections by a heading that contains an id (``## BI-PF-1309 ...``); inside a
section, ``field: value`` lines set a field and bullet lines following a bare ``field:`` collect a list.

Writes go ONLY through the backlog API (single writer). Default is a dry-run preview; ``--apply`` writes.
Upsert semantics: fill MISSING fields by default, ``--overwrite`` replaces, ``--create`` creates missing
items as children of ``--epic`` (idempotent via ``external_id``).

Usage:
  python scripts/dev/backlog_ingest_doc.py --doc plan.md --epic BI-PF-1292
  python scripts/dev/backlog_ingest_doc.py --doc plan.md --epic BI-PF-1292 --apply --overwrite
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTEXT_FIELDS = frozenset({
    "objective", "acceptance_criteria", "in_scope", "out_of_scope", "affected_components",
    "affected_files", "approach", "verification", "risks", "rollback", "evidence", "owner",
    "summary", "brief",
})
EDITABLE_FIELDS = frozenset({"title", "body", "type", "label", "tag", "origin",
                             "value", "effort", "risk", "moscow"})
DEP_FIELDS = frozenset({"dependencies", "blocked_by"})
LIST_FIELDS = frozenset({
    "acceptance_criteria", "in_scope", "out_of_scope", "affected_components", "affected_files",
    "verification", "risks", "evidence", "dependencies", "blocked_by",
})
ALL_FIELDS = CONTEXT_FIELDS | EDITABLE_FIELDS | DEP_FIELDS

_ITEM_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\b(BI-PF-\d+)\b(.*)$", re.IGNORECASE)
_FIELD_LINE_RE = re.compile(r"^\s*(?:[-*]\s+)?([a-z_]+)\s*[:=]\s*(.*)$", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*)$")


def extract_text(path: Path) -> str:
    from core import intake_files

    res = intake_files.extract(str(path))
    return str(res.get("text") or "")


def _coerce(field: str, raw: str) -> Any:
    value = raw.strip()
    if field == "brief":
        return {"what_adds": value}
    if field in LIST_FIELDS:
        return [p.strip() for p in value.split(",") if p.strip()]
    return value


def _heading_title(before: str, after: str) -> str:
    mid = f"{before} {after}".strip()
    return re.sub(r"^[\s\-–—:.]*", "", mid).strip()


def parse_sections(text: str) -> dict[str, dict[str, Any]]:
    sections: dict[str, dict[str, Any]] = {}
    cur: str | None = None
    cur_field: str | None = None
    for raw in text.splitlines():
        m = _ITEM_HEADING_RE.match(raw)
        if m:
            cur = m.group(2).upper()
            sec = sections.setdefault(cur, {})
            title = _heading_title(m.group(1), m.group(3))
            if title and not sec.get("title"):
                sec["title"] = title
            cur_field = None
            continue
        if cur is None:
            continue
        if not raw.strip():
            cur_field = None
            continue
        f = _FIELD_LINE_RE.match(raw)
        if f and f.group(1).lower() in ALL_FIELDS:
            key, val = f.group(1).lower(), f.group(2).strip()
            if val:
                sections[cur][key] = _coerce(key, val)
                cur_field = None
            else:
                sections[cur].setdefault(key, [])
                cur_field = key
            continue
        b = _BULLET_RE.match(raw)
        if b and cur_field:
            existing = sections[cur].get(cur_field)
            if not isinstance(existing, list):
                existing = []
                sections[cur][cur_field] = existing
            existing.append(b.group(1).strip())
    return {k: v for k, v in sections.items() if v}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (str, list, dict)):
        return len(value) == 0 or (isinstance(value, str) and not value.strip())
    return False


def compute_changes(current: dict[str, Any], desired: dict[str, Any],
                    overwrite: bool) -> dict[str, Any]:
    return {k: v for k, v in desired.items() if overwrite or _is_missing(current.get(k))}


def _route(fields: dict[str, Any]) -> tuple[dict, dict, dict]:
    ctx = {k: v for k, v in fields.items() if k in CONTEXT_FIELDS}
    edit = {k: v for k, v in fields.items() if k in EDITABLE_FIELDS}
    deps = {k: v for k, v in fields.items() if k in DEP_FIELDS}
    return ctx, edit, deps


class Client:
    def __init__(self, base: str, token: str):
        self.base = base.rstrip("/")
        self.token = token

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("X-Roles", "operator")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from None

    def get_item(self, item_id: str, scope: str, project: str) -> dict | None:
        q = f"?scope={scope}&project={project}"
        try:
            env = self.call("GET", f"/backlog/items/{item_id}{q}")
        except RuntimeError:
            return None
        return env.get("data") if isinstance(env, dict) else None

    def create_item(self, item_id: str, title: str, epic: str, scope: str, project: str) -> dict:
        env = self.call("POST", "/backlog/items", {
            "title": title or item_id, "type": "feature", "epic": epic,
            "external_id": item_id, "scope": scope, "project": project,
        })
        return env.get("data") or {}


def run(sections: dict[str, dict[str, Any]], client: Client, epic: str, scope: str, project: str,
        apply_: bool, overwrite: bool, create: bool) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for item_id, desired in sections.items():
        current = client.get_item(item_id, scope, project)
        if current is None and not create:
            report.append({"id": item_id, "state": "not_found", "fields": sorted(desired)})
            continue
        if current is None:
            if not apply_:
                report.append({"id": item_id, "state": "would_create", "fields": sorted(desired)})
                continue
            current = client.create_item(item_id, str(desired.get("title") or ""), epic, scope, project)
        changed = compute_changes(current, desired, overwrite)
        entry = {"id": item_id, "state": "preview" if not apply_ else "unchanged",
                 "changed": sorted(changed)}
        if apply_ and changed:
            ctx, edit, deps = _route(changed)
            if ctx:
                client.call("POST", f"/backlog/items/{item_id}/context", ctx)
            if edit:
                client.call("PATCH", f"/backlog/items/{item_id}", edit)
            if deps:
                client.call("POST", f"/backlog/items/{item_id}/dependencies", deps)
            entry["state"] = "applied"
        report.append(entry)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest a document into backlog item fields via the API.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--doc", help="path to .md/.txt/.doc/.docx/.pdf/.rtf")
    src.add_argument("--stdin", action="store_true", help="read the document text from stdin")
    ap.add_argument("--epic", required=True, help="target epic id for --create")
    ap.add_argument("--scope", default="product_forge")
    ap.add_argument("--project", default="")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run preview)")
    ap.add_argument("--overwrite", action="store_true", help="replace supplied fields (default: fill missing only)")
    ap.add_argument("--create", action="store_true", help="create missing items as children of --epic")
    ap.add_argument("--api-url", default=os.environ.get("PF_API_URL", "http://127.0.0.1:8010/api/v1"))
    ap.add_argument("--token", default="")
    a = ap.parse_args(argv)

    text = sys.stdin.read() if a.stdin else extract_text(Path(a.doc))
    if not text.strip():
        print("no text extracted", file=sys.stderr)
        return 2
    sections = parse_sections(text)
    if not sections:
        print("no item sections found (use '## <BI-PF-id> ...' headings)", file=sys.stderr)
        return 2
    token = a.token or os.environ.get("PF_API_TOKEN", "")
    if not token:
        tf = ROOT / "data" / "local" / "dev-api-token"
        token = tf.read_text(encoding="utf-8").strip() if tf.is_file() else ""
    if not token:
        print("no API token (set --token/PF_API_TOKEN or data/local/dev-api-token)", file=sys.stderr)
        return 2
    client = Client(a.api_url, token)
    report = run(sections, client, a.epic, a.scope, a.project, a.apply, a.overwrite, a.create)
    print(json.dumps({"epic": a.epic, "apply": a.apply, "overwrite": a.overwrite,
                      "create": a.create, "items": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
