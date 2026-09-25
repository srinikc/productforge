# Product Forge — Generic Intake Adapter

Works for **any** caller (another app, a script, cron, a webhook). One endpoint, one schema.

## Endpoint
```
POST {BASE}/api/intake
Content-Type: application/json

{ "source": "generic",        # optional; defaults to generic
  "title": "...",             # REQUIRED
  "body": "...",              # details / context / requirements
  "scope": "project" | "pipeline",   # pipeline = Product Forge itself
  "project": "<existing project name>",  # required when scope=project
  "kind": "feature" | "bug" | "enhancement" | "change" | "idea" | "context" | "tech-debt",
  "value": 1-5, "effort": 1-5, "risk": 1-5,
  "moscow": "Must" | "Should" | "Could",
  "deps": ["BI-0001"], "links": {"conversation_id": "..."} }
```
`POST {BASE}/api/v1/intake` accepts the same body (adapter-compatible).
For large content use `/api/v1/intake/upload-chunk` + `/upload-complete` (see the chatgpt adapter).

## What happens
1. Raw payload archived to `products/inbox/<source>/`.
2. Normalized, stored as a Conversation, routed by intent.
3. Promoted to exactly one backlog item (`origin=intake`) in the right scope:
   - `scope=pipeline` → **Product Forge backlog** (`product-forge/backlog/`)
   - `scope=project`  → that **project's backlog** (`products/<project>/backlog/`)
4. `idea`/`explore` items are parked with a weekly follow-up; changes become `new` items; new projects become `accepted`.

## Response
```json
{ "id": "BI-0007", "label": "PF Backlog 7", "status": "new", "scope": "product_forge",
  "conversation_id": "...", "raw": "products/inbox/generic/....json" }
```

## Rules
- Send **one intent per call** (don't mix a new project with bug fixes).
- Never send secrets; raw payloads are archived.
- Idempotency: reuse `links.conversation_id` or the same title+project to avoid duplicates
  (the analyzer can also detect duplicates across a backlog).
