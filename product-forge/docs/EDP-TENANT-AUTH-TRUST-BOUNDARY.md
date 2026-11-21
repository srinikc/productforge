# EDP Data-Plane Service — Tenant Authentication & Trusted Gateway Trust Boundary

**Item:** `BI-PF-1478`  
**Parent Epic:** `BI-PF-1292` (Enterprise Data Platform — EDP)  
**Status:** Shipped / Active  
**Component:** `go/edpsvc` (Enterprise Data Plane Service)

---

## 1. Executive Summary & Architecture

The Enterprise Data Plane service (`go/edpsvc`) acts as the single system of record for Product Forge's database and data-plane resources (backlog, artifacts, memory, audit, jobs, and migrations).

Prior to `BI-PF-1478` (`BI-PF-1302` / EDP-10), `edpsvc` operated under a single static admin token, meaning per-tenant quota buckets were advisory attribution while the global quota was the only hard cap.

`BI-PF-1478` establishes cryptographically verified, per-tenant authentication and hard per-tenant quota isolation:
1. **Authenticated Tenant Derivation:** Inbound tenant identity is derived strictly from the authenticated principal/claim, never from client-controlled `X-Tenant-Id` headers or `?tenant=` query parameters.
2. **Hard Quota Isolation:** Rate limit buckets and concurrency semaphores are bound directly to the authenticated tenant. Changing or omitting headers cannot bypass or reset quota accounting.
3. **Fail-Closed Cross-Tenant Defense:** Any request presenting a header, query parameter, or JSON body specifying a tenant that contradicts the authenticated principal is rejected with **`403 Forbidden`**.

---

## 2. Authentication Schemes & Credential Taxonomy

`edpsvc` accepts three caller credential classes via the standard `Authorization: Bearer <token>` header (or `X-Tenant-Claim: <token>`):

| Credential Class | Verification Mechanism | Scope | Permitted Endpoints |
| :--- | :--- | :--- | :--- |
| **Admin Token** | Constant-time SHA256 digest match against `PF_ADMIN_TOKEN` / `s.admin` | Global / System Admin | All endpoints, including administrative routes (`/admin/*`, `/metrics`, `/backlog/ids:reserve`) and data routes acting for any tenant |
| **Trusted Gateway Signed Claim** | HMAC-SHA256 signature verification using shared secret (`PF_GATEWAY_SECRET` / `PF_GATEWAY_SECRET_OLD`) | Tenant-Scoped (derived from claim) | Data-plane endpoints (`/backlog`, `/memory`, `/artifacts`, `/jobs`, `/audit`) |
| **Static Tenant Token** | Constant-time lookup in `PF_TENANT_TOKENS` registry | Tenant-Scoped (mapped to configured tenant) | Data-plane endpoints (`/backlog`, `/memory`, `/artifacts`, `/jobs`, `/audit`) |

---

## 3. Trusted Gateway Signed Claims (JWT Format)

When upstream API gateways or edge proxies forward requests to `edpsvc`, they sign a compact tenant claim token using HMAC-SHA256 (`HS256`).

### 3.1 Token Structure
The token follows compact 3-part base64url encoding:
```text
<base64url(Header)>.<base64url(Payload)>.<base64url(HMAC-SHA256 Signature)>
```

- **Header:**
  ```json
  {
    "alg": "HS256",
    "typ": "JWT"
  }
  ```
- **Payload Schema:**
  ```json
  {
    "tenant": "acme_corp",
    "sub": "usr_9410",
    "principal": "usr_9410",
    "exp": 1795000000,
    "iat": 1794996400,
    "iss": "pf-trusted-gateway"
  }
  ```

| Claim | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `tenant` | string | **Yes** | Target tenant identifier (bounded label matching `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`). |
| `sub` / `principal` | string | No | Calling user or service principal. If omitted, defaults to `gateway:<tenant>`. |
| `exp` | int64 | **Yes** | Unix timestamp (seconds) when the claim expires. |
| `iat` | int64 | No | Unix timestamp (seconds) when the claim was issued. |
| `iss` | string | No | Issuer identifier (e.g., `pf-trusted-gateway`). |

---

## 4. Key Issuance & Secret Rotation Runbook

To achieve zero-downtime key rotation between trusted gateways and `edpsvc`:

### 4.1 Secret Configuration
- `PF_GATEWAY_SECRET`: The active primary HMAC secret (minimum 32 random characters/bytes).
- `PF_GATEWAY_SECRET_OLD`: The retiring secondary HMAC secret.

### 4.2 Rotation Procedure
1. **Step 1 (Staging):** Set `PF_GATEWAY_SECRET_OLD` to the current active secret, and set `PF_GATEWAY_SECRET` to the new secret in `edpsvc`'s configuration. Redeploy/reload `edpsvc`.
2. **Step 2 (Verification):** Both old and new signatures are valid during this phase (`edpsvc` checks `PF_GATEWAY_SECRET` first, falling back to `PF_GATEWAY_SECRET_OLD`).
3. **Step 3 (Gateway Cutover):** Update the trusted gateway signing service to sign using the new secret.
4. **Step 4 (Retirement):** After all in-flight tokens signed with the old secret have expired (typically 1 hour), unset `PF_GATEWAY_SECRET_OLD` on `edpsvc`.

---

## 5. Security Invariants & Defense Controls

### 5.1 Clock Skew Policy
- **Expiration (`exp`):** Evaluated strictly against server clock (`now > exp`). An expired token immediately returns `401 Unauthorized` (`EXPIRED_CREDENTIAL`).
- **Future Issuance (`iat`):** To prevent clock-skew false positives across distributed gateway instances, a grace window of **30 seconds** is permitted. Claims with `iat > now + 30s` return `401 Unauthorized` (`PREMATURE_CREDENTIAL`).

### 5.2 Anti-Spoofing & Cross-Tenant Rejection
When an authenticated non-admin principal makes a request:
- If `X-Tenant-Id` header is present and does not equal `principal.Tenant` -> **`403 Forbidden`** (`CROSS_TENANT_FORBIDDEN`).
- If `?tenant=` query parameter is present and does not equal `principal.Tenant` -> **`403 Forbidden`**.
- If JSON request body contains `{"tenant": "..."}` and does not equal `principal.Tenant` -> **`403 Forbidden`**.
- If no header/query is present, the operation executes strictly under `principal.Tenant`.

### 5.3 Anti-Evasion Hard Quota Enforcement
Rate limiting and concurrency control are evaluated against the authenticated tenant bucket:
- Rotating or randomizing `X-Tenant-Id` or `?tenant=` does not create new buckets or reset limits. Any conflicting header is immediately blocked with 403, and any conforming header continues to deplete the authenticated tenant's bucket.

---

## 6. Error Response Envelope

All authentication and quota rejection responses conform to Product Forge's structured `v1` error envelope:

```json
{
  "version": "1",
  "error": {
    "code": "FORBIDDEN",
    "message": "cross-tenant access forbidden",
    "category": "auth",
    "retryable": false,
    "request_id": "42f9a12c-9a10-40e8-971c-7f5511b8b801"
  }
}
```

| HTTP Status | Error Code | Category | Condition |
| :--- | :--- | :--- | :--- |
| **`401`** | `UNAUTHENTICATED` | `auth` | Missing or unparseable credential |
| **`401`** | `EXPIRED_CREDENTIAL` | `auth` | Gateway claim `exp` is in the past |
| **`401`** | `PREMATURE_CREDENTIAL`| `auth` | Gateway claim `iat` is > 30s in the future |
| **`401`** | `INVALID_CLAIMS` | `auth` | Missing required `tenant` claim in payload |
| **`403`** | `FORBIDDEN` | `auth` | Cross-tenant header/query mismatch |
| **`429`** | `RATE_LIMITED` | `rate_limit` | Tenant RPM or concurrency cap exhausted |

---

## 7. Verification Evidence & Test Matrix

The following test suites verify 100% of the acceptance criteria:

1. **`go/edpsvc/internal/auth/tenant_auth_test.go`:**
   - `TestTenantAuth_Admin`: Admin token authentication.
   - `TestTenantAuth_StaticTenantTokens`: Static tenant token parsing and derivation.
   - `TestGatewayClaims_Valid`: HMAC-SHA256 signature verification and claim parsing.
   - `TestGatewayClaims_ForgedAndTampered`: Rejection of forged secrets and tampered payloads.
   - `TestGatewayClaims_Expired`: Rejection of expired tokens.
   - `TestGatewayClaims_ClockSkewAndPremature`: 30s skew tolerance and rejection of premature tokens.
   - `TestGatewayClaims_SecretRotation`: Seamless dual-secret validation during rotation.
2. **`go/edpsvc/internal/limits/middleware_test.go`:**
   - `TestTenantQuota_HardIsolation`: Hard quota bucket attribution, 403 cross-tenant denial, and anti-evasion proof.
3. **`go/edpsvc/main_test.go`:**
   - `TestTenantAuth_EndToEnd`: Full HTTP pipeline integration through `limits.Chain` with mock storage.
