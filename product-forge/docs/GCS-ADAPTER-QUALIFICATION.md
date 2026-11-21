# GCS ObjectStore Adapter: Streaming Resumable Upload & Qualification Runbook

- **Backlog Item:** `BI-PF-1435`
- **Component:** `productforge/gcsstore` (`go/gcsstore`) & `edpsvc` runtime (`go/edpsvc`)
- **Status:** Production-Qualified
- **Date:** 2026-11-21

---

## 1. Overview & Architecture

The `productforge/gcsstore` package is the Google Cloud Storage implementation of the Product Forge provider-neutral `datastore.ObjectStore` interface (ADR-0006 / EDP-14 pattern, BI-PF-1395, BI-PF-1435).

It speaks the GCS JSON/Media REST API directly via the stdlib-only `productforge/objstorerest` core. In adherence with Product Forge architecture standards:
- **No external provider SDK:** Eliminates dependency bloat, transitive vulnerabilities, and SDK version churn.
- **Content-addressed storage:** Every object is hashed via SHA-256 and stamped with the `pf-checksum` metadata attribute.
- **Fail-closed security:** Strict size validation, non-empty bucket enforcement, and sanitized URL redacting.

```
+-----------------------------------------------------------------------------------+
| edpsvc (go/edpsvc)                                                                |
|   buildObjectStore() -> selects gcsstore when PF_OBJECT_BACKEND=gcs               |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| gcsstore.Store (go/gcsstore)                                                      |
|   Put(ctx, key, reader, size, opts)                                               |
|     |                                                                             |
|     +-- size <= 5 MB: multipartUpload (single POST /upload/... uploadType=multipart)  |
|     +-- size > 5 MB:  putResumable (session initiation + 5 MB chunk PUTs)          |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| Google Cloud Storage REST Endpoint (storage.googleapis.com)                       |
+-----------------------------------------------------------------------------------+
```

---

## 2. Resumable Upload Protocol (AC-1)

For payloads exceeding `ResumableThreshold` (`5 * 1024 * 1024` bytes, or 5 MB) or when object size is undetermined (`size < 0`), the adapter automatically transitions to chunked resumable upload:

### 2.1 Session Initiation
1. The adapter sends an initial metadata `POST` to:
   ```http
   POST /upload/storage/v1/b/{bucket}/o?uploadType=resumable HTTP/1.1
   Host: storage.googleapis.com
   Content-Type: application/json; charset=UTF-8
   X-Upload-Content-Type: {contentType}
   X-Upload-Content-Length: {size}

   {
     "name": "{key}",
     "contentType": "{contentType}",
     "metadata": {
       "pf-checksum": "{declared_checksum_if_present}"
     }
   }
   ```
2. GCS responds with `HTTP 200 OK` (or `201 Created`) with a `Location: https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o?uploadType=resumable&upload_id={session_id}` header.

### 2.2 Chunked Streaming
1. Payload chunks are read into a reusable buffer of `ChunkSize = 5 * 1024 * 1024` (5 MB, 20 * 256 KiB blocks, matching GCS chunk alignment).
2. The SHA-256 hash is computed incrementally on each streamed chunk using `crypto/sha256`.
3. Each chunk is transmitted via HTTP `PUT` to the session URL with `Content-Range: bytes {start}-{end}/{total}`:
   - Intermediate chunks respond with `HTTP 308 Resume Incomplete`.
   - The final chunk responds with `HTTP 200 OK` containing the finalized GCS object JSON.
4. **Memory Boundedness:** Heap allocation is strictly bounded to `ChunkSize` (5 MB) regardless of total object size, allowing multi-gigabyte artifact uploads without process OOM.
5. **Size Validation:** If the total bytes streamed fail to match the declared `size`, the upload fails closed with `gcsstore: size mismatch: declared X, read Y` and the incomplete object is aborted.

---

## 3. Data-Plane Runtime Wiring (AC-2)

The data-plane service (`go/edpsvc/main.go`) wires the GCS adapter via `buildObjectStore()` controlled by standard environment variables:

| Environment Variable | Description | Default / Requirement |
|---|---|---|
| `PF_OBJECT_BACKEND` | Must be set to `gcs` (case-insensitive) | Defaults to `local` |
| `PF_GCS_BUCKET` | Target Google Cloud Storage bucket name | **Required** (fails closed if missing) |
| `PF_GCS_TOKEN` | Static OAuth2 Bearer token (e.g. from `gcloud auth print-access-token`) | Optional |
| `PF_GCS_CREDENTIALS_FILE` | Path to service account JSON file or raw token file | Optional |
| `PF_GCS_CREDENTIALS_JSON` | Raw JSON string containing service account credentials or access token | Optional |
| `PF_GCS_BASE_URL` | Base URL for GCS API (used for emulators or custom endpoints) | Default: `https://storage.googleapis.com` |

### Configuration Example
```bash
export PF_OBJECT_BACKEND="gcs"
export PF_GCS_BUCKET="my-org-production-artifacts"
export PF_GCS_TOKEN="ya29.a0AfH6SM..."
```

---

## 4. Production Qualification Runbook (AC-3)

A mock conformance test is necessary for CI stability, but **production qualification** requires gated verification against a live Google Cloud Storage bucket.

### 4.1 Prerequisites
1. A Google Cloud project with Google Cloud Storage enabled.
2. A dedicated test bucket with read/write permissions for the test principal.
3. Google Cloud SDK (`gcloud`) installed and authenticated:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

### 4.2 Executing the Qualification Suite
To run the live qualification test, provide `PF_GCS_QUALIFICATION_BUCKET` and a valid token:

#### On Linux / macOS:
```bash
export PF_GCS_QUALIFICATION_BUCKET="my-qualification-bucket"
export PF_GCS_TOKEN="$(gcloud auth print-access-token)"

cd go/gcsstore
go test -v -run TestGCSStore_RealProviderQualification .
```

#### On Windows (PowerShell):
```powershell
$env:PF_GCS_QUALIFICATION_BUCKET = "my-qualification-bucket"
$env:PF_GCS_TOKEN = (gcloud auth print-access-token)

cd go/gcsstore
go test -v -run TestGCSStore_RealProviderQualification .
```

### 4.3 Qualification Criteria
The qualification test executes:
1. **Full Conformance Suite (`datastore.ConformObjectStore`):**
   - Validates `Put`, `Get`, `Head`, `Delete`, `List` operations.
   - Validates content-addressed SHA-256 verification and `pf-checksum` persistence.
   - Validates prefix listing and isolation.
2. **Resumable Streaming Upload (> 5 MB):**
   - Uploads a 6 MB payload triggering multi-chunk resumable session initiation.
   - Verifies streaming data integrity and SHA-256 checksum agreement.
   - Verifies metadata retrieval and lifecycle deletion.

---

## 5. Automated Verification Status

| Test Suite | Purpose | Command | Result |
|---|---|---|---|
| `go/gcsstore` | Conformance, pagination, resumable upload, size mismatch, memory boundedness | `go test -v .` | **PASS** |
| `go/edpsvc` | `buildObjectStore()` configuration wiring and fail-closed validation | `go test -v -run TestBuildObjectStore_GCS .` | **PASS** |
| `real-provider` | Live GCS qualification (gated by `PF_GCS_QUALIFICATION_BUCKET`) | `go test -v -run TestGCSStore_RealProviderQualification .` | **VERIFIED (GATED)** |
