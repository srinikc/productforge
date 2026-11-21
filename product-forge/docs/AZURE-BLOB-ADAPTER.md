# Azure Blob Storage ObjectStore Adapter Specification & Runbook

- **Backlog Item:** `BI-PF-1433`
- **Component:** `productforge/azurestore` (`go/azurestore`) & `edpsvc` runtime (`go/edpsvc`)
- **Status:** Production-Qualified
- **Date:** 2026-11-21

---

## 1. Overview & Architecture

The `productforge/azurestore` package provides the Microsoft Azure Blob Storage implementation of Product Forge's provider-neutral `datastore.ObjectStore` interface (ADR-0006 / EDP-14 pattern, BI-PF-1433).

It communicates directly with the Azure Blob Storage REST API over the standard-library-only `productforge/objstorerest` core. In strict adherence with Product Forge architecture rules:
- **Zero Provider SDK Dependencies:** Implements Azure Blob REST protocol directly via Go stdlib (eliminating `azure-sdk-for-go` dependency tree and transitive vulnerabilities).
- **True Streaming Delivery:** `Get` streams the HTTP response body directly (`resp.Body`) without buffering large objects into memory, eliminating OOM risk for high-throughput enterprise pipelines.
- **Content-Addressed Integrity:** Objects are verified via SHA-256 and stamped with `x-ms-meta-pf_checksum` user metadata.
- **Fail-Closed Security:** Container presence is mandatory; size mismatches reject immediately; unsupported capabilities (immutability, retention, CMK) return explicit `UnsupportedError`.
- **Tenant Isolation:** Enforced at the `edpsvc` service boundary via `{tenant_id}/{key}` prefixing and fail-closed 403 checks.

```
+-----------------------------------------------------------------------------------+
| edpsvc (go/edpsvc)                                                                |
|   buildObjectStore() -> selects azurestore when PF_OBJECT_BACKEND=azure|azblob    |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| azurestore.Store (go/azurestore)                                                  |
|   Put(ctx, key, reader, size, opts)                                               |
|     |-- Validates size and calculates SHA256 checksum                             |
|     |-- Sends PUT /{container}/{blob} with x-ms-blob-type: BlockBlob              |
|     \-- Stamps x-ms-meta-pf_checksum                                              |
|   Get(ctx, key, version)                                                          |
|     \-- GET /{container}/{blob}, streams resp.Body directly without OOM risk     |
|   Head(ctx, key)                                                                  |
|     \-- HEAD /{container}/{blob}, reads x-ms-meta-pf_checksum & Content-Length    |
|   Delete(ctx, key, version)                                                       |
|     \-- DELETE /{container}/{blob}, idempotent on 404                             |
|   List(ctx, prefix) / ListPage(...)                                               |
|     \-- GET /{container}?restype=container&comp=list with XML parsing (10MB bound)|
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| Azure Blob Storage / Azurite Emulator Endpoint                                    |
+-----------------------------------------------------------------------------------+
```

---

## 2. Authentication Mechanisms & Precedence

The adapter provides three authentication mechanisms implementing `objstorerest.Auth`:

1. **SharedKeyAuth (`SharedKeyAuth`):**
   Computes canonicalized HMAC-SHA256 signatures according to Azure Storage specifications for Blob Service:
   - Sets `x-ms-date: <RFC1123-UTC>` and `x-ms-version: 2020-10-02` (configurable via `APIVersion`).
   - Constructs `StringToSign` from HTTP verb, canonicalized headers (`x-ms-*`), and canonicalized resource (`/<account>/<path>`).
   - Sets `Authorization: SharedKey <account>:<base64-signature>`.

2. **SASTokenAuth (`SASTokenAuth`):**
   Appends Shared Access Signature query string parameters to the request URL while setting `x-ms-version`.

3. **BearerAuth (`BearerAuth`):**
   Sets `Authorization: Bearer <token>` for OAuth2 / Azure Managed Identity tokens.

4. **Credential Precedence (`AuthFromCredentials`):**
   When multiple credentials are present, `AuthFromCredentials` resolves in deterministic order:
   - **Precedence 1: SharedKeyAuth** (when both account and account key are provided)
   - **Precedence 2: SASTokenAuth** (when SAS query string is provided)
   - **Precedence 3: BearerAuth** (when Bearer token is provided)
   - **Fallback: nil** (unauthenticated, used for local emulators or mock test servers)

---

## 3. Configuration & Runtime Wiring

When `PF_OBJECT_BACKEND=azure` or `PF_OBJECT_BACKEND=azblob`, `buildObjectStore()` in `go/edpsvc/main.go` initializes the adapter using the following environment variables:

| Environment Variable | Description | Requirement | Default |
|---|---|---|---|
| `PF_OBJECT_BACKEND` | Storage backend selector (`azure` or `azblob`) | Required | `local` |
| `PF_AZURE_CONTAINER` | Target Azure Blob container name | Required | Fail-closed |
| `PF_AZURE_ACCOUNT` | Storage account name | Required if BaseURL is unset | Empty |
| `PF_AZURE_KEY` | Base64-encoded storage account shared key | Optional (SharedKey auth) | Empty |
| `PF_AZURE_SAS_TOKEN` | Shared Access Signature query string | Optional (SAS auth) | Empty |
| `PF_AZURE_TOKEN` | Azure AD / Managed Identity Bearer token | Optional (Bearer auth) | Empty |
| `PF_AZURE_BASE_URL` | Base URL override (e.g. `http://127.0.0.1:10000/devstoreaccount1`) | Optional (Azurite/tests) | `https://<account>.blob.core.windows.net` |

---

## 4. Capability Honesty Matrix

In compliance with Product Forge ADR-0006, optional capabilities are declared honestly:

| Capability | Declared | Behavior on Invocation |
|---|---|---|
| `Transactions` | `false` | Not supported |
| `ObjectVersioning` | `false` | Base operations supported; versioning not claimed |
| `ObjectLock` | `false` | `Put` rejects `Retention` / `RetentionMode` with `UnsupportedError` |
| `ConditionalWrites` | `false` | Not supported |
| `SignedURLs` | `false` | `SignedURL()` returns `UnsupportedError` |
| `MultipartUpload` | `false` | Direct block blob upload supported |
| `CustomerManagedKeys` | `false` | `Put` rejects `ServerSideEncryption` with `UnsupportedError` |

---

## 5. Verification & Conformance

The adapter passes the hardened `datastore.ConformObjectStore` conformance suite:
```bash
cd go/azurestore
go test -v .
```
Result:
- `TestAzureStore_Conformance`: **PASS** (Put, Head, Get streaming, prefix-filtered List, Delete)
- `TestAzureStore_CapabilitiesHonesty`: **PASS** (honest all-false capabilities, fail-closed on unsupported PutOptions)
- `TestAzureStore_SizeAndChecksumValidation`: **PASS** (strict short/long read rejection, checksum mismatch error)
- `TestAzureStore_SharedKeySignatureCorrectness`: **PASS** (exact HMAC-SHA256 signature calculation validation)
- `TestAzureStore_AuthMechanisms`: **PASS** (SharedKey, Bearer, SAS token verification)
