# Event Transports Design

- Item: BI-PF-1270
- Epic: BI-PF-1265
- Scope: in-process, webhook, notify/email transports behind the BI-PF-1269 dispatcher

## RECONCILIATION

### PRIOR DECISIONS
- ADR-0011: PostgreSQL is the event authority; transports never become a second event store.
- BI-PF-1269 owns cursor, dedupe, retry and DLQ.
- ADR-0012: event-delivery DLQ is Go/PostgreSQL, distinct from the pipeline task DLQ.
- BI-PF-1267 defines webhook HMAC and idempotency contract.
- BI-PF-1268/1269 delivery state and dispatcher are live.

### EXISTING PATH
- `go/edpdata.Transport` is the dispatcher transport interface.
- `core.notification_system.NotificationSystem` owns in-app notifications.
- Python API already owns HTTP surface; new notification endpoint edits existing API.
- Secrets are environment/secret-store references; never event payloads.

### ASSUMPTIONS
- All transports are best-effort senders; retry/DLQ remains dispatcher-owned.
- In-app notification remains available even when email is disabled.
- SMTP is the first email provider; other providers can implement the same Go interface.

### DIVERGENCES
- BI-PF-1269 retries every error. This item must add permanent-webhook classification so 400/404/410/422 go directly to DLQ.
- `core.notification_system` stores notifications but has no email provider. Email is new Go logic; in-app storage is reused through the API.

### OPEN QUESTIONS
- SMTP deployment defaults (host/port/TLS auth) must be supplied by environment.
- Webhook private-network access is disabled by default; deployments may allow it explicitly.

## Functional Behaviour

### In-process transport
- Thread-safe callback registry keyed by event type.
- `Deliver` invokes all matching callbacks and returns the first error.
- Used for tests and same-process consumers.

### Webhook transport
- `POST` JSON envelope to subscription target.
- Headers:
  - `X-PF-Timestamp`: RFC3339/Unix seconds
  - `X-PF-Signature`: `sha256=<hex HMAC>`
  - `X-PF-Idempotency-Key`: exact `event_id`
- Signature input: `timestamp + "." + rawBody`.
- Reject timestamps older/newer than 5 minutes on the receiver side.
- Constant-time HMAC comparison.
- URL policy:
  - HTTPS required by default.
  - HTTP only when `PF_WEBHOOK_ALLOW_HTTP=true`.
  - Private/loopback addresses rejected unless `PF_WEBHOOK_ALLOW_PRIVATE=true`.
  - No redirects followed by default.
- Response policy:
  - 2xx: success.
  - 409: duplicate success (idempotency key already processed).
  - 408/425/429: retryable; honor `Retry-After` when present.
  - 401/403: retryable bounded (credential rotation), then DLQ.
  - 400/404/410/422: permanent; dispatcher sends straight to DLQ.
  - 5xx/timeout/network: retryable.

### Notify/email transport
- Always writes in-app notification through `POST /api/v1/notifications`.
- Email eligibility:
  - low: in-app only
  - medium/high/critical: in-app + email when SMTP configured
  - threshold configurable via `PF_NOTIFY_EMAIL_MIN_PRIORITY`
- If SMTP is unconfigured, in-app succeeds and email is recorded as skipped, not failed.
- Email subject/body derive from event type and redacted payload summary.

### Dispatcher integration
- Add `edpdata.PermanentDeliveryError` (wrapped error marks no retry).
- Dispatcher checks permanent errors before retry count and DLQs immediately.
- All transports are selected by `subscription.transport` in a new `eventtransport.Registry`.

## API First

| Route | Method | Auth | Purpose |
|---|---|---|---|
| `/api/v1/notifications` | POST | operator/service | Store in-app notification |

Request: project, notification_type, title, message, priority, agent, stage.
Response: notification_id, stored=true, email_eligible.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PF_WEBHOOK_HMAC_KEY` | unset | webhook signing secret; unset disables webhook transport |
| `PF_WEBHOOK_ALLOW_HTTP` | `false` | allow non-TLS webhook targets |
| `PF_WEBHOOK_ALLOW_PRIVATE` | `false` | allow private/loopback targets |
| `PF_WEBHOOK_TIMEOUT_SECONDS` | `10` | HTTP timeout |
| `PF_NOTIFY_API_URL` | local API | notification endpoint base |
| `PF_NOTIFY_EMAIL_MIN_PRIORITY` | `medium` | email threshold |
| `PF_SMTP_HOST/PORT/USER/PASSWORD/FROM` | unset | SMTP provider |
| `PF_SMTP_TLS` | `true` | TLS mode |

## Security

- HMAC in constant time; never log secret or signature.
- No caller-controlled DSN/path/tenant.
- URL validation blocks SSRF by default.
- Email credentials from environment/secret store only.
- Notification endpoint operator/service auth; no anonymous access.

## Failure Matrix

| Case | Behaviour |
|---|---|
| invalid webhook URL | permanent error → DLQ |
| missing HMAC key | transport disabled/fail closed |
| stale/future timestamp (receiver) | reject |
| 409 idempotency conflict | success |
| 400/404/410/422 | permanent → DLQ |
| 429 with Retry-After | retry using backoff |
| SMTP unavailable | in-app stored; email retryable |
| notification API down | retryable |

## Tests

- Inproc callback receives event; no callback means no-op success.
- Webhook HMAC matches timestamp+body; idempotency header equals event_id.
- Webhook 4xx permanent classification; 409 duplicate success; 429/5xx retry.
- URL policy rejects HTTP/private by default; allows only with explicit flags.
- Notify stores in-app; priority gate selects email for medium/high/critical.
- SMTP disabled: in-app success, email skipped.
- Dispatcher integration: permanent error → DLQ without retry; retryable → retry.

## Rollout / Rollback

- Additive packages and endpoint.
- No schema migration.
- Rollback removes transports and endpoint; in-app notifications remain.
- Webhook is disabled when secret is absent; notify/email remains in-app-only.

## Risks

| Risk | Mitigation |
|---|---|
| SSRF via webhook target | HTTPS + private-IP block + explicit allow flags |
| Secret leakage | env/secret store, no logs, constant-time compare |
| Duplicate email | event_id idempotency + delivery dedupe |
| Email provider outage | in-app first; email retried/DLQ |
| Hardcoded priority policy | configurable `PF_NOTIFY_EMAIL_MIN_PRIORITY` |
| Transport complexity | one registry, small interfaces, no new store |


## Gate 1 corrections

### API contract (complete)

- Route: `POST /api/v1/notifications` added by editing existing `api/routers/events.py`; no new Python module.
- Auth: operator or service role.
- Authz: scope/project resolved by existing API context; no caller-controlled tenant.
- Validation: notification_type enum, non-empty title/message, priority in low/medium/high/critical, bounded lengths.
- Tenant scoping: request tenant comes from authenticated context; notification store remains project-scoped.
- Response: notification_id, stored=true, email_eligible.
- Language rule: Python is only a thin wrapper over `core.notification_system`; all transport/email/HMAC logic is Go.

### Config contract (one table)

| Variable | Required | Default |
|---|---|---|
| `PF_WEBHOOK_HMAC_KEY` | for webhook | unset disables webhook |
| `PF_WEBHOOK_ALLOW_HTTP` | no | false |
| `PF_WEBHOOK_ALLOW_PRIVATE` | no | false |
| `PF_WEBHOOK_TIMEOUT_SECONDS` | no | 10 |
| `PF_NOTIFY_API_URL` | no | local API |
| `PF_NOTIFY_EMAIL_MIN_PRIORITY` | no | medium |
| `PF_SMTP_HOST` | for email | unset |
| `PF_SMTP_PORT` | for email | 587 |
| `PF_SMTP_USER` | for email | unset |
| `PF_SMTP_PASSWORD` | for email | unset |
| `PF_SMTP_FROM` | for email | unset |
| `PF_SMTP_TLS` | no | true |

### Tenant/RLS and runtime roles

- Transport registry is scoped by tenant subscription; cross-tenant subscription lookup is rejected.
- Webhook/inproc/notify transports never receive caller-supplied tenant IDs; tenant comes from the subscription.
- Where DB-backed, runtime role remains NOSUPERUSER/NOBYPASSRLS; RLS posture is unchanged from 1268/1269.
- Tests must cover cross-tenant subscription collision and tenant-scoped delivery.

### Webhook security

- HMAC key is resolved per subscription through `auth_ref` from the secret store/environment; no shared global secret is required.
- Comparison uses `hmac.Equal` (constant time).
- Signature input is `timestamp + "." + rawBody`.
- Timestamp skew is bounded to 5 minutes.
- Secret/key values are never logged.

### Failure matrix completion

| Case | Behaviour |
|---|---|
| 429 with `Retry-After` | retry using max(backoff, Retry-After) |
| 400/404/410/422 | permanent ? DLQ |
| 401/403 | bounded retry for credential rotation, then DLQ |
| 409 | duplicate success |
| 5xx/timeout/network | retry, then DLQ |
| missing HMAC key | webhook disabled/fail closed |

### Availability and startup

- Startup validates webhook/SMTP config shape; missing webhook key disables webhook explicitly.
- Dispatcher/DB unavailable: no partial sends; retry by dispatcher.
- DLQ depth alert threshold: >0 entries or >5 minutes retry age; owner is eventing on-call runbook.

### Observability names

- `event_delivery_attempts_total{transport,outcome}`
- `event_delivery_retry_age_seconds{transport}`
- `event_delivery_dlq_depth{transport}`
- `event_delivery_latency_seconds{transport}`
- Logs redact target credentials, HMAC keys and signatures.

### Rollback

- Remove transports and notification endpoint.
- Disable subscriptions using removed transports; do not delete delivery/DLQ history.
- Stranded DLQ entries remain exportable and require verified backup before any destructive cleanup.
- No migration in this item.

### AC evidence

- Candidate design SHA: `0c578b06c682c22429fca8570227430aafd4ce8a`.
- Implementation evidence will be pinned at the implementation SHA; design rows use this candidate SHA.


## Final Gate 1 corrections

- DB-backed subscription/delivery paths run as NOSUPERUSER/NOBYPASSRLS; RLS tests cover cross-tenant rejection.
- Delivery queries use statement_timeout and bounded limits.
- Delivery semantics are at-least-once; duplicates are possible and deduped by event_id idempotency plus per-subscription cursor ordering.
- Availability: dispatcher/DB failure never partially sends; alert on >5m 5xx or DLQ growth.
- Notify endpoint bounds title/message length; no bulk send is allowed.
