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
