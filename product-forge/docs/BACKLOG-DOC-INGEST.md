# Backlog document ingest (`BI-PF-1396`)

Ingest a plan/design document and project its sections onto backlog items — so context is taken from the
**original decision document** instead of being re-invented at re-grooming time.

- **Tool:** `scripts/dev/backlog_ingest_doc.py` (tooling Python; **no** new API endpoint, **no** Go required).
- **Writes:** only through the **backlog API** (single writer `core.backlog`); default is a **dry-run preview**.
- **Text extraction:** reuses the existing owner `core.intake_files.extract` — supports
  `.md`, `.txt`, `.doc`, `.docx`, `.pdf`, `.rtf`.

## Usage

```bash
python scripts/dev/backlog_ingest_doc.py --doc plan.md --epic BI-PF-1292            # preview
python scripts/dev/backlog_ingest_doc.py --doc plan.md --epic BI-PF-1292 --apply    # fill missing fields
python scripts/dev/backlog_ingest_doc.py --doc plan.md --epic BI-PF-1292 --apply --overwrite
cat plan.md | python scripts/dev/backlog_ingest_doc.py --stdin --epic BI-PF-1292
```

## Document format

A heading that contains an item id starts a section; inside it, `field: value` lines set a field and bullet
lines following a bare `field:` collect a list.

```markdown
## BI-PF-1309 - EDP-17 canonical schema
objective: canonical PostgreSQL schema
affected_files:
- migrations/0002_core_schema.up.sql
- go/store/pg.go
risks: migration drift, data loss
type: feature
```

## Fields routed to the API

| Group | Fields | Endpoint |
|---|---|---|
| context | `objective, acceptance_criteria, in_scope, out_of_scope, affected_components, affected_files, approach, verification, risks, rollback, evidence, owner, summary, brief` | `POST /backlog/items/{id}/context` |
| editable | `title, body, type, label, tag, origin, value, effort, risk, moscow` | `PATCH /backlog/items/{id}` |
| dependencies | `dependencies, blocked_by` | `POST /backlog/items/{id}/dependencies` |

## Upsert semantics

- **Default:** fill only **missing/empty** fields on existing items (never clobbers authored content).
- `--overwrite`: replace values the document supplies.
- `--create`: create missing items as children of `--epic` (idempotent via `external_id`); without it,
  unknown ids are reported as `not_found`.
- Re-applying the **same document** is a no-op (fields already present) — safe/idempotent.

## Out of scope

- An HTTP endpoint in `api/` (would be new shipped logic → **Go**, plus a Python→Go bridge). If a
  non-operator caller ever needs this network capability, that is a separate Gate 1.
- OCR for images/audio/video; robust legacy `.doc` (best-effort only — prefer `.docx`).

## Related

- `BI-PF-1396` (this feature), `BI-PF-1398` (undeclared `pypdf`/`python-docx` gap),
  `BI-PF-0360` (API-only backlog writes), `BI-PF-0387/0388` (language rule: new shipped logic → Go).
