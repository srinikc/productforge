# API Design Standards (REST)

> **Scope:** All REST APIs in Product Forge
> **Source:** Google API Design Guide + Microsoft REST API Guidelines + Zalando RESTful API Guidelines
> **Version:** 1.0 | **Date:** 2026-08-24

---

## 1. URL Design

### 1.1 Resource Naming
- **Use plural nouns:** `/users`, `/todos`, `/orders`
- **No verbs in URLs:** ❌ `/getUsers`, ✅ `/users`
- **Use kebab-case:** `/user-profiles`, `/todo-items`
- **Nested resources:** `/users/{id}/todos`, `/teams/{id}/members`

### 1.2 URL Structure
```
https://api.example.com/api/v1/{resource}/{id}/{sub-resource}
```

### 1.3 Versioning (ADR-012)
- **Always use `/api/v1/` prefix**
- Major version in URL (breaking changes)
- Minor/patch in headers

### 1.4 Examples
```
GET    /api/v1/users              # List users
GET    /api/v1/users/{id}         # Get one user
POST   /api/v1/users              # Create user
PUT    /api/v1/users/{id}         # Full update
PATCH  /api/v1/users/{id}         # Partial update
DELETE /api/v1/users/{id}         # Delete user
GET    /api/v1/users/{id}/todos   # List user's todos
POST   /api/v1/users/{id}/todos   # Create todo for user
```

---

## 2. HTTP Methods

| Method | Purpose | Idempotent | Safe | Request Body |
|---|---|---|---|---|
| **GET** | Read resource(s) | Yes | Yes | No |
| **POST** | Create resource | No | No | Yes |
| **PUT** | Full update | Yes | No | Yes |
| **PATCH** | Partial update | No | No | Yes |
| **DELETE** | Delete resource | Yes | No | No |
| **HEAD** | Headers only | Yes | Yes | No |
| **OPTIONS** | Available methods | Yes | Yes | No |

---

## 3. HTTP Status Codes

### 3.1 Success (2xx)
| Code | Meaning | Use When |
|---|---|---|
| 200 | OK | Successful GET, PUT, PATCH |
| 201 | Created | Successful POST creating resource |
| 202 | Accepted | Async operation started |
| 204 | No Content | Successful DELETE, no body to return |

### 3.2 Client Error (4xx)
| Code | Meaning | Use When |
|---|---|---|
| 400 | Bad Request | Malformed request, validation error |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Authenticated but not authorized |
| 404 | Not Found | Resource doesn't exist |
| 405 | Method Not Allowed | HTTP method not supported |
| 409 | Conflict | Resource state conflict (e.g., duplicate) |
| 422 | Unprocessable Entity | Validation error (semantic) |
| 429 | Too Many Requests | Rate limit exceeded |

### 3.3 Server Error (5xx)
| Code | Meaning | Use When |
|---|---|---|
| 500 | Internal Server Error | Generic server error |
| 502 | Bad Gateway | Upstream service error |
| 503 | Service Unavailable | Temporary outage |
| 504 | Gateway Timeout | Upstream timeout |

---

## 4. Request Format

### 4.1 Headers
```http
POST /api/v1/users HTTP/1.1
Host: api.example.com
Authorization: Bearer {token}
Content-Type: application/json
Accept: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

**Required headers:**
- `Content-Type: application/json` (for POST/PUT/PATCH)
- `Accept: application/json`
- `Authorization: Bearer {token}` (for protected endpoints)
- `X-Request-ID` (for tracing)

### 4.2 Request Body (JSON)
```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "age": 30
}
```

**Conventions:**
- `camelCase` for JSON keys
- ISO 8601 for dates (`2026-08-24T10:30:00Z`)
- UTC for all timestamps
- Boolean as `true`/`false` (not `1`/`0`)

---

## 5. Response Format

### 5.1 Success Response
```json
{
  "data": {
    "id": 123,
    "email": "user@example.com",
    "name": "John Doe",
    "createdAt": "2026-08-24T10:30:00Z"
  }
}
```

### 5.2 List Response (with pagination metadata)
```json
{
  "data": [
    { "id": 1, "title": "Todo 1" },
    { "id": 2, "title": "Todo 2" }
  ],
  "pagination": {
    "total": 100,
    "limit": 10,
    "offset": 0,
    "hasMore": true
  }
}
```

### 5.3 Error Response (Standard Format)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format",
        "code": "INVALID_FORMAT"
      },
      {
        "field": "password",
        "message": "Password must be at least 8 characters",
        "code": "TOO_SHORT"
      }
    ],
    "requestId": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-08-24T10:30:00Z",
    "documentation": "https://docs.example.com/errors/VALIDATION_ERROR"
  }
}
```

**Required error fields:**
- `code` — Machine-readable error code
- `message` — Human-readable message
- `requestId` — For support/debugging
- `timestamp` — When error occurred

**Optional error fields:**
- `details` — Field-level errors (for validation)
- `documentation` — Link to docs
- `stackTrace` — Only in development

---

## 6. Pagination

### 6.1 Offset-Based (Simple)
```http
GET /api/v1/todos?limit=20&offset=40
```
- `limit` — Items per page (default: 20, max: 100)
- `offset` — Items to skip

**Use when:** Stable list, admin views, simple pagination

### 6.2 Cursor-Based (Scalable)
```http
GET /api/v1/todos?limit=20&cursor=eyJpZCI6MTAwfQ==
```
- `cursor` — Opaque cursor string
- Response includes `nextCursor` and `prevCursor`

**Use when:** Large datasets, real-time data, infinite scroll

### 6.3 Page-Based
```http
GET /api/v1/todos?page=3&perPage=20
```
- `page` — 1-indexed page number
- `perPage` — Items per page

**Use when:** User-facing pagination with page numbers

---

## 7. Filtering, Sorting, Searching

### 7.1 Filtering
```http
GET /api/v1/todos?status=active&priority=high
GET /api/v1/todos?createdAt[gte]=2026-01-01&createdAt[lte]=2026-12-31
```

### 7.2 Sorting
```http
GET /api/v1/todos?sort=createdAt:desc,priority:asc
```

### 7.3 Searching
```http
GET /api/v1/todos?q=groceries
GET /api/v1/todos?search=title:groceries,description:milk
```

### 7.4 Field Selection (Sparse Fieldsets)
```http
GET /api/v1/todos?fields=id,title,completed
```

---

## 8. Authentication

### 8.1 JWT Bearer Token
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 8.2 API Key (for service-to-service)
```http
X-API-Key: your-api-key-here
```

### 8.3 OAuth2 (for third-party)
- Use Authorization Code Flow with PKCE
- Store tokens securely
- Implement refresh token rotation

---

## 9. Rate Limiting

### 9.1 Response Headers
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1692873600
X-RateLimit-Policy: 100;w=3600
```

### 9.2 429 Response
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "retryAfter": 60
  }
}
```

---

## 10. Caching

### 10.1 Cache Headers
```http
Cache-Control: public, max-age=3600
ETag: "33a64df551425fcc55e4d42a148795d9f25f89d4"
Last-Modified: Wed, 24 Aug 2026 10:30:00 GMT
```

### 10.2 Conditional Requests
```http
If-None-Match: "33a64df551425fcc55e4d42a148795d9f25f89d4"
If-Modified-Since: Wed, 24 Aug 2026 10:30:00 GMT
```

### 10.3 Cache Strategies
- **Public:** CDN can cache (GET /products, /categories)
- **Private:** User-specific (GET /user/profile)
- **No cache:** Sensitive data (GET /auth/me)

---

## 11. Versioning & Deprecation

### 11.1 Versioning
- URL-based for major versions (`/api/v1/`, `/api/v2/`)
- Header-based for minor versions (`Accept: application/vnd.api.v1.1+json`)

### 11.2 Deprecation
```http
Deprecation: true
Sunset: Wed, 01 Jan 2027 00:00:00 GMT
Link: </api/v2/users>; rel="successor-version"
```

---

## 12. HATEOAS (Optional)

Include links to related resources:
```json
{
  "data": {
    "id": 123,
    "title": "Buy groceries",
    "links": {
      "self": "/api/v1/todos/123",
      "user": "/api/v1/users/456",
      "comments": "/api/v1/todos/123/comments"
    }
  }
}
```

---

## 13. Documentation (OpenAPI)

Every API MUST have OpenAPI 3.1+ spec.

### 13.1 Generate from Code (FastAPI)
```python
from fastapi import FastAPI

app = FastAPI(
    title="MyWorld API",
    version="1.0.0",
    description="Central portal API",
    openapi_tags=[...],
)

# OpenAPI spec auto-generated at /openapi.json
# Swagger UI at /docs
# ReDoc at /redoc
```

### 13.2 Include
- All endpoints
- Request/response schemas
- Authentication methods
- Error responses
- Examples
- Status codes

---

## 14. Security

### 14.1 HTTPS Only
- All APIs MUST use HTTPS in production
- HSTS header recommended
- Reject HTTP requests

### 14.2 CORS
```http
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 86400
```

### 14.3 Input Validation
- Validate all inputs (Pydantic, Zod)
- Sanitize strings
- Use parameterized queries
- Reject unexpected fields

### 14.4 Security Headers
```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
```

---

## 15. Anti-Patterns to Avoid

| Anti-Pattern | Why | Instead |
|---|---|---|
| Verbs in URLs | Not RESTful | Use HTTP methods |
| Singular resources | Inconsistent | Use plural |
| Deep nesting (>3 levels) | Hard to maintain | Flatten or use filtering |
| Exposing internal IDs | Security risk | Use UUIDs or slugs |
| Returning 200 for errors | Misleading | Use 4xx/5xx codes |
| Different error formats | Hard to parse | Use standard format |
| Missing pagination | Performance issues | Always paginate lists |
| No versioning | Breaking changes | Use `/api/v1/` |
| Mixed camelCase/snake_case | Inconsistent | Choose one (camelCase for JSON) |
| Ignoring HTTP methods | Lost REST benefits | Use GET/POST/PUT/DELETE correctly |
| Storing sensitive data in URLs | Logged everywhere | Use POST with body or headers |
| No rate limiting | DoS vulnerability | Implement rate limits |

---

## 16. References

- [Google API Design Guide](https://cloud.google.com/apis/design)
- [Microsoft REST API Guidelines](https://github.com/microsoft/api-guidelines)
- [Zalando RESTful API Guidelines](https://opensource.zalando.com/restful-api-guidelines/)
- [OpenAPI 3.1 Specification](https://spec.openapis.org/oas/v3.1.0)
- [HTTP Semantics (RFC 9110)](https://www.rfc-editor.org/rfc/rfc9110.html)
- [OWASP API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)
