# Google Drive ObjectStore Adapter Specification & Runbook

- **Backlog Item:** `BI-PF-1434`
- **Component:** `productforge/gdrivestore` (`go/gdrivestore`) & `edpsvc` runtime (`go/edpsvc`)
- **Status:** Production-Qualified
- **Date:** 2026-11-21

---

## 1. Overview & Architecture

The `productforge/gdrivestore` package provides the Google Drive v3 REST implementation of Product Forge's provider-neutral `datastore.ObjectStore` interface (ADR-0006 / EDP-14 pattern, BI-PF-1434).

It communicates directly with the Google Drive v3 REST API over the standard-library-only `productforge/objstorerest` core. In strict adherence with Product Forge architecture rules:
- **Zero Provider SDK Dependencies:** Implements Google Drive REST protocol directly via Go stdlib (eliminating `google.golang.org/api/drive` dependency tree and transitive vulnerabilities).
- **Write-Then-Delete Collision Policy:** Standard object stores are flat, unique-name key-value stores, whereas Google Drive allows duplicate file names in folders. To prevent race conditions and guarantee zero data loss, the adapter uploads and verifies the new file first before retiring any superseded older file to Drive trash.
- **Native Soft-Delete to Trash:** Replaced hard deletion with Google Drive native soft-delete (`{"trashed": true}`), enabling a 30-day administrative recovery window from accidental overwrites.
- **Strict Custom Property Bounds:** Stored metadata (`pf_key`, `pf_checksum`) strictly respects Google Drive's 124-byte custom property limit (`pf_key` <= 100 bytes, `pf_checksum` = 64 hex characters).
- **True Streaming Delivery:** `Get` streams the HTTP response body directly (`resp.Body`) without buffering large objects into memory, eliminating OOM risk for high-throughput enterprise pipelines.
- **Content-Addressed Integrity:** Objects are verified via SHA-256 and stamped with `pf_checksum` user and app properties.
- **Fail-Closed Security:** Root folder ID is mandatory; size mismatches reject immediately; unsupported capabilities (immutability, retention, CMK) return explicit `UnsupportedError`.
- **Tenant Isolation:** Enforced at the `edpsvc` service boundary via `{tenant_id}/{key}` prefixing and fail-closed 403 checks.

```
+-----------------------------------------------------------------------------------+
| edpsvc (go/edpsvc)                                                                |
|   buildObjectStore() -> selects gdrivestore when PF_OBJECT_BACKEND=gdrive        |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| gdrivestore.Store (go/gdrivestore)                                                |
|   Put(ctx, key, reader, size, opts)                                               |
|     |-- Validates size and calculates SHA256 checksum                             |
|     |-- Uploads RFC 2387 multipart/related body (JSON metadata + media payload)   |
|     |-- Stamps pf_checksum and pf_key in properties & appProperties               |
|     \-- Write-Then-Delete: retires pre-existing file IDs with same key to trash   |
|   Get(ctx, key, version)                                                          |
|     |-- Scopes query to rootFolderID ('{rootFolderID}' in parents and trashed=false)|
|     \-- GET /drive/v3/files/{id}?alt=media, streams resp.Body directly            |
|   Head(ctx, key)                                                                  |
|     \-- Scopes query to rootFolderID, returns ObjectInfo without reading media    |
|   Delete(ctx, key, version)                                                       |
|     \-- PATCH /drive/v3/files/{id} with {"trashed": true}, idempotent on 404      |
|   List(ctx, prefix) / ListPage(...)                                               |
|     \-- GET /drive/v3/files with bounded JSON parsing (10MB) & pagination token   |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| Google Drive API v3 / Google Workspace Shared Drive Endpoint                      |
+-----------------------------------------------------------------------------------+
```

---

## 2. Key <-> FileID Model & Collision Policy

Google Drive is an ID-based document store rather than a key-value object store. Without a deterministic model, folder collisions and concurrent writes cause duplicate files or silent overwrites.

### 2.1 Storage Layout
- All objects for a given store instance are contained within a single designated parent folder (`RootFolderID`).
- The logical key is stored in `name` and in custom file properties (`properties["pf_key"]` and `appProperties["pf_key"]`).
- For keys up to 100 characters, the exact string is recorded. Keys are bounded to stay within Google Drive's 124-byte property limit.

### 2.2 Write-Then-Delete Protocol
1. **Upload First:** `Put` constructs an RFC 2387 `multipart/related` request and uploads the new file to `/upload/drive/v3/files?uploadType=multipart`.
2. **Verification:** The API response is parsed, confirming the file was created and assigned a new unique `id`.
3. **Retire Superseded:** A query searches for any existing active files in `RootFolderID` with the same `name` (excluding the new `id`).
4. **Soft-Delete:** Matching older files are patched with `{"trashed": true}`. If this retirement step encounters an error, the `Put` operation still succeeds because the new file is already intact and valid (zero data loss).

### 2.3 Deletion Policy
- Calling `Delete(ctx, key, "")` finds all active files matching `key` in `RootFolderID` and moves them to trash.
- Deleting an already non-existent file returns `nil` (idempotent).
- Calling `Delete(ctx, key, version)` trashes the specific Google Drive `version` (file ID).

---

## 3. Configuration & Runtime Wiring

When `PF_OBJECT_BACKEND=gdrive` or `PF_OBJECT_BACKEND=googledrive`, `buildObjectStore()` in `go/edpsvc/main.go` initializes the adapter using the following environment variables:

| Environment Variable | Description | Requirement | Default |
|---|---|---|---|
| `PF_OBJECT_BACKEND` | Storage backend selector (`gdrive` or `googledrive`) | Required | `local` |
| `PF_GDRIVE_ROOT_FOLDER_ID` | Designated Google Drive root folder ID | Required | Fail-closed |
| `PF_GDRIVE_TOKEN` | Google Service Account / OAuth2 access token | Optional (auth) | Empty |
| `PF_GDRIVE_BASE_URL` | Base URL override (e.g. `http://127.0.0.1:8090`) | Optional (mock/tests) | `https://www.googleapis.com` |
| `PF_GDRIVE_UPLOAD_BASE_URL` | Upload endpoint base URL override | Optional (mock/tests) | BaseURL |

---

## 4. Capability Honesty Matrix

In compliance with Product Forge ADR-0006, optional capabilities are declared honestly:

| Capability | Declared | Behavior on Invocation |
|---|---|---|
| `Transactions` | `false` | Not supported |
| `ObjectVersioning` | `false` | Base operations supported; versioning not claimed |
| `ObjectLock` | `false` | Returns `&UnsupportedError{Provider: "gdrive", Capability: "retention"}` |
| `ConditionalWrites`| `false` | Not supported |
| `SignedURLs` | `false` | Returns `&UnsupportedError{Provider: "gdrive", Capability: "signed-urls"}` |
| `MultipartUpload` | `false` | Internal multipart/related used; high-level chunked upload not claimed |
| `CustomerManagedKeys` | `false` | Returns `&UnsupportedError{Provider: "gdrive", Capability: "server-side-encryption"}` |

---

## 5. Verification & Conformance

The adapter passes all automated tests without external network dependencies:
- **`datastore.ConformObjectStore`:** Verifies standard `Put`, `Head`, `Get`, `List` prefix filtering, and `Delete` contracts.
- **Capability Honesty:** Verifies all-false capabilities and fail-closed error returns on unsupported options.
- **Write-Then-Delete Collision Safety:** Verifies that a failed upload leaves existing data intact, and a successful upload retires prior files to trash.
- **Size and Checksum Validation:** Verifies fail-closed detection of short reads, long reads, and checksum mismatches.
- **Authentication:** Verifies `Bearer` token header injection.
- **edpsvc Wiring:** Verifies runtime selection and environment variable parsing.

---

## 6. Operational Runbook & Troubleshooting

### 6.1 Authentication Failures (HTTP 401 / 403)
- Verify `PF_GDRIVE_TOKEN` is a valid, unexpired Google OAuth2 access token with `https://www.googleapis.com/auth/drive` or `https://www.googleapis.com/auth/drive.file` scope.
- Verify the service account has `Editor` permissions on the designated `PF_GDRIVE_ROOT_FOLDER_ID`.

### 6.2 Rate Limiting (HTTP 429)
- Google Drive applies a per-user rate limit (10 QPS default).
- The adapter delegates HTTP transport to `objstorerest.Client`, which automatically executes bounded exponential backoff with jitter and honors `Retry-After` response headers.
