# Backlog & Intake — Epics, storage, lifecycle, APIs, persona

## Scopes (two backlogs)
| Scope | Open | Closed | History |
|---|---|---|---|
| **Project** | `products/<project>/backlog/open.json` | `.../backlog/closed.json` | `.../backlog/history/<EPIC-ID>.jsonl` |
| **Portfolio / Product Forge** | `products/backlog/open.json` | `products/backlog/closed.json` | `products/backlog/history/<EPIC-ID>.jsonl` |
| Intake raw archive | `products/inbox/<source>/<ts>.json` | — | — |

Open = non-terminal (`new → triaged → accepted(now|later) → queued → scheduled → executing → implemented → verifying`).
Closed = terminal (`done | rejected | wontfix`). Rejected/wontfix are terminal but keep an audit trail.

## Item model — **Epics only**
`EPIC-####` with: `title, body, scope(project|portfolio), project, source, kind(feature|bug|enhancement|idea|context), status, moscow(Must/Should/Could/Wont), value, effort, risk, score, deps[], links[], decisions[], created_at, updated_at`.

## Prioritization (WSJF-lite + MoSCoW + aging + capacity)
- `score = (value × confidence) / effort`, `confidence = 1 − (risk−1)/4`.
- Sort: **Must → score desc → age → FIFO**; aging boosts long-open items.
- **Capacity gate**: only items within `capacity.json` slots/budget/`max_created` get scheduled.

## Lifecycle
`intake → normalize → inbox → triage(LLM/rules) → accept(now|later) → open backlog → prioritize/queue → schedule → run → implement/verify → done → closed`.
- **accept now** (project scope) → `portfolio.enqueue(project)` (queue/supervisor picks it up); **later** → `accepted` (unscheduled).
- Project items → project run (iteration or **enhance**); pipeline items → **Product Forge self-enhance**.

## Intake adapters
Per-source `{field map + instructions}`; **`generic`** works for any caller; plus chatgpt/gemini/dashboard/file.
`GET /api/intake/instructions?source=<s>` returns what to send.

Schema (generic):
```json
{ "source":"generic", "scope":"project|pipeline", "project":"<name>",
  "title":"...", "body":"...", "kind":"feature|bug|enhancement|idea|context",
  "value":1-5, "effort":1-5, "risk":1-5, "moscow":"Must|Should|Could|Wont",
  "deps":[], "links":[] }
```

## Persona (Human Proxy / auto mode)
`config/persona.json` (default) merged with `products/<project>/persona.json`.
Defines the owner's traits + knobs (risk_appetite, quality_bar, budget_sensitivity, deadline_pressure, ux_sensitivity, compliance_strictness, communication_style) + must/must-not → drives the `human` agent’s decisions and backlog triage priorities.

## APIs (Product Forge exposes all; dashboard consumes)
`POST /api/intake` · `GET/POST /api/backlog` · `GET /api/backlog/closed` · `GET /api/backlog/stale?days=` ·
`POST /api/backlog/<id>/triage` · `POST /api/backlog/<id>/accept {when:"now|later"}` · `POST /api/backlog/<id>/close` ·
`GET /api/persona` · `GET /api/intake/instructions`. Plus run/enhance/control/portfolio/capacity/quality APIs.

## Notes
- Classified as **Epics** now; stories/tasks + Scrum later.
- Single writer per backlog file with a lock; atomic writes.
- Stale items (`backlog.stale`) are the follow-up signal for the **event router** (planned).
