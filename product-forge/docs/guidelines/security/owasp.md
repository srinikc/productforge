# Security Standards (OWASP-Based)

> **Scope:** All Product Forge applications
> **Source:** OWASP Top 10 (2023) + OWASP API Security Top 10 (2023) + NIST Cybersecurity Framework
> **Version:** 1.0 | **Date:** 2026-08-24

---

## 1. OWASP Top 10 (2023) - Web Applications

### A01: Broken Access Control
**Risk:** Users can act outside their intended permissions.

**Prevention:**
- Implement RBAC (Role-Based Access Control) or ABAC (Attribute-Based)
- Deny by default (allowlist, not blocklist)
- Use RLS (Row-Level Security) at database level
- Validate authorization on every request
- Log access control failures

**Example:**
```python
# Bad: Only check authentication, not authorization
@router.delete("/users/{user_id}")
async def delete_user(user_id: int, current_user: User = Depends(get_current_user)):
    await db.delete(User, user_id)  # Any authenticated user can delete any user!

# Good: Check authorization
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.delete(User, user_id)
```

---

### A02: Cryptographic Failures
**Risk:** Sensitive data exposed due to weak/missing encryption.

**Prevention:**
- Use HTTPS only (TLS 1.3)
- Hash passwords with bcrypt/argon2 (never MD5, SHA1)
- Encrypt sensitive data at rest
- Use strong random tokens (32+ bytes)
- Never log sensitive data

**Example:**
```python
from passlib.hash import bcrypt

# Bad: Plain text or weak hash
user.password = "password123"
user.password_hash = hashlib.md5(password.encode()).hexdigest()

# Good: bcrypt with salt
user.password_hash = bcrypt.hash(password)
# Verify
is_valid = bcrypt.verify(password, user.password_hash)
```

---

### A03: Injection (SQL, NoSQL, Command, LDAP)
**Risk:** User input interpreted as code.

**Prevention:**
- Use parameterized queries (SQLAlchemy ORM)
- Use ORMs instead of raw SQL
- Validate and sanitize all input
- Use allowlists for commands
- Escape output (for XSS)

**Example:**
```python
# Bad: SQL injection
query = f"SELECT * FROM users WHERE email = '{email}'"

# Good: Parameterized
query = select(User).where(User.email == email)

# Bad: Command injection
os.system(f"convert {filename} output.png")

# Good: Use library, validate input
if not filename.endswith(('.jpg', '.png')):
    raise ValueError("Invalid file")
subprocess.run(['convert', filename, 'output.png'], check=True)
```

---

### A04: Insecure Design
**Risk:** Flaws in design that can't be fixed by implementation alone.

**Prevention:**
- Threat modeling during design (use STRIDE)
- Security requirements as user stories
- Reference architecture patterns
- Security review before implementation
- Defense in depth

**Example (Threat Model):**
```
Asset: User's personal data
Threat: SQL injection → Data breach
Mitigation: ORM + input validation + RLS
Threat: XSS → Account takeover
Mitigation: CSP headers + output encoding
Threat: CSRF → Unauthorized actions
Mitigation: SameSite cookies + CSRF tokens
```

---

### A05: Security Misconfiguration
**Risk:** Default configs, open services, verbose errors.

**Prevention:**
- Hardened baseline configs
- No default passwords
- Disable directory listings
- Error messages don't leak stack traces
- Security headers enabled

**Example:**
```python
# Bad: Debug mode in production
app = FastAPI(debug=True)

# Good: Environment-specific config
app = FastAPI(
    debug=settings.environment == "development",
    docs_url="/docs" if settings.environment != "production" else None,
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

---

### A06: Vulnerable & Outdated Components
**Risk:** Using libraries with known vulnerabilities.

**Prevention:**
- Keep dependencies updated
- Automated vulnerability scanning (Snyk, Dependabot)
- Pin versions in production
- Regular security audits

**Tools:**
```bash
# Python
pip-audit
safety check

# JavaScript
npm audit
snyk test
```

---

### A07: Identification & Authentication Failures
**Risk:** Weak authentication allows account takeover.

**Prevention:**
- Multi-factor authentication (MFA)
- Strong password requirements
- Rate limit login attempts
- Secure session management
- JWT with short expiration + refresh tokens
- Account lockout after failed attempts

**Example:**
```python
# Password requirements
def validate_password(password: str) -> bool:
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'[0-9]', password):
        return False
    return True

# Rate limit login
@limiter.limit("5 per 15 minutes")
async def login(credentials: LoginRequest):
    # authenticate
    pass
```

---

### A08: Software & Data Integrity Failures
**Risk:** Untrusted code, data, or updates.

**Prevention:**
- Verify signatures on updates
- Use SRI (Subresource Integrity) for CDN
- CI/CD pipeline security
- Code review requirements
- Audit log for data changes

**Example:**
```html
<!-- SRI for CDN scripts -->
<script src="https://cdn.example.com/lib.js"
        integrity="sha384-..."
        crossorigin="anonymous"></script>
```

---

### A09: Security Logging & Monitoring Failures
**Risk:** Attacks not detected or investigated.

**Prevention:**
- Log all authentication events
- Log all access control failures
- Log all input validation failures
- Centralized logging (ELK, Datadog)
- Alerting on suspicious patterns
- Incident response plan

**Example:**
```python
import logging
logger = logging.getLogger("security")

# Log security events
async def login(credentials: LoginRequest, request: Request):
    user = await authenticate(credentials)
    if not user:
        logger.warning("Failed login attempt", extra={
            "email": credentials.email,
            "ip": request.client.host,
            "user_agent": request.headers.get("user-agent"),
            "timestamp": datetime.utcnow().isoformat(),
        })
        raise HTTPException(401, "Invalid credentials")
    
    logger.info("Successful login", extra={
        "user_id": user.id,
        "ip": request.client.host,
    })
    return create_token(user)
```

---

### A10: Server-Side Request Forgery (SSRF)
**Risk:** Server makes requests to unintended locations.

**Prevention:**
- Validate URLs against allowlist
- Block internal IP ranges (127.0.0.1, 10.x, 192.168.x, etc.)
- Use DNS resolution check
- Disable HTTP redirects

**Example:**
```python
import ipaddress
from urllib.parse import urlparse

BLOCKED_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
]

def is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False
    
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
        return not any(ip in network for network in BLOCKED_NETWORKS)
    except:
        return False
```

---

## 2. OWASP API Security Top 10 (2023)

### API1: Broken Object Level Authorization (BOLA)
**Risk:** User can access other users' resources by changing ID.

**Prevention:**
- Verify ownership on every request
- Use RLS at database level
- Use UUIDs instead of sequential IDs

### API2: Broken Authentication
**Risk:** Weak API authentication.

**Prevention:**
- Use OAuth2/OIDC for third-party
- JWT with proper validation
- Rate limit authentication endpoints
- Token rotation

### API3: Broken Object Property Level Authorization
**Risk:** User can access/modify properties they shouldn't.

**Prevention:**
- Separate read/write schemas
- Field-level access control
- Don't return sensitive fields

### API4: Unrestricted Resource Consumption
**Risk:** DoS via resource exhaustion.

**Prevention:**
- Rate limiting per user/IP
- Request size limits
- Query complexity limits (GraphQL)
- Timeout on all external calls

### API5: Broken Function Level Authorization
**Risk:** User can access admin functions.

**Prevention:**
- Role-based access control
- Separate admin API
- Function-level permissions

### API6: Unrestricted Access to Sensitive Business Flows
**Risk:** Abuse of business logic (e.g., ticket scalping).

**Prevention:**
- CAPTCHA for sensitive flows
- Device fingerprinting
- Anomaly detection

### API7: Server Side Request Forgery
**Risk:** See A10 above.

### API8: Security Misconfiguration
**Risk:** See A05 above.

### API9: Improper Inventory Management
**Risk:** Old API versions, undocumented endpoints.

**Prevention:**
- API versioning
- API documentation (OpenAPI)
- Deprecation policy
- Environment separation (dev/staging/prod)

### API10: Unsafe Consumption of APIs
**Risk:** Trusting third-party API responses.

**Prevention:**
- Validate all third-party responses
- Use allowlists for expected fields
- Handle errors gracefully
- Monitor third-party API changes

---

## 3. Authentication Best Practices

### 3.1 Password Storage
```python
from passlib.hash import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.verify(password, password_hash)
```

**Rules:**
- Never store plain text
- Use bcrypt (cost 12+), argon2, or scrypt
- Never log passwords
- Force password change on first login
- Check against breached password lists (Have I Been Pwned API)

### 3.2 JWT Tokens
```python
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = settings.jwt_secret  # From env, never hardcoded
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(minutes=15)
REFRESH_TOKEN_EXPIRE = timedelta(days=7)

def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + ACCESS_TOKEN_EXPIRE,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + REFRESH_TOKEN_EXPIRE,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
```

**Rules:**
- Short-lived access tokens (15-30 min)
- Long-lived refresh tokens (7-30 days)
- Refresh token rotation
- Store refresh tokens securely (httpOnly cookies)
- Include user ID, expiration, type
- Validate signature and expiration

### 3.3 OAuth2 / OIDC
- Use Authorization Code Flow with PKCE
- Validate state parameter
- Store tokens securely
- Implement refresh token rotation
- Use HTTPS for all redirects

---

## 4. Authorization Patterns

### 4.1 Role-Based Access Control (RBAC)
```python
from enum import Enum

class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

def require_role(required_role: Role):
    def dependency(current_user: User = Depends(get_current_user)):
        if not has_role(current_user, required_role):
            raise HTTPException(403, "Insufficient permissions")
        return current_user
    return dependency

@router.get("/admin/users", dependencies=[Depends(require_role(Role.ADMIN))])
async def list_all_users():
    ...
```

### 4.2 Attribute-Based Access Control (ABAC)
```python
def can_access_todo(user: User, todo: Todo) -> bool:
    return (
        todo.user_id == user.id
        or user.is_admin
        or (todo.is_public and user.is_verified)
    )
```

### 4.3 Database-Level (RLS)
```sql
-- See database standards for full RLS setup
ALTER TABLE todo_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY todos_user_isolation ON todo_items
    USING (user_id = current_setting('app.current_user_id')::BIGINT);
```

---

## 5. Input Validation

### 5.1 Pydantic (Python)
```python
from pydantic import BaseModel, Field, EmailStr, HttpUrl, validator

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=150)
    website: HttpUrl | None = None
    
    @validator('name')
    def name_no_special_chars(cls, v):
        if not re.match(r'^[a-zA-Z\s-]+$', v):
            raise ValueError('Name can only contain letters, spaces, and hyphens')
        return v
```

### 5.2 Zod (TypeScript)
```typescript
import { z } from 'zod';

const userSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8).max(128),
  name: z.string().min(1).max(100).regex(/^[a-zA-Z\s-]+$/),
  age: z.number().int().min(0).max(150),
  website: z.string().url().optional(),
});
```

---

## 6. Secrets Management

### 6.1 Never Commit Secrets
- Use `.env` files (gitignored)
- Use environment variables
- Use secret manager (AWS Secrets Manager, HashiCorp Vault)
- Pre-commit hooks to detect secrets

### 6.2 Environment Variables
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    jwt_secret: str  # From env
    api_key: str     # From env
    
    class Config:
        env_file = ".env"
```

### 6.3 Secret Rotation
- Rotate secrets regularly (90 days)
- Have multiple active secrets during rotation
- Automate rotation where possible
- Audit secret access

---

## 7. Security Headers

### 7.1 Required Headers
```python
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}
```

---

## 8. Rate Limiting

### 8.1 Implementation
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Per IP
@limiter.limit("100 per hour")
async def public_endpoint():
    ...

# Per user
@limiter.limit("1000 per hour", key_func=lambda: get_current_user_id())
async def user_endpoint():
    ...

# Strict limits on auth
@limiter.limit("5 per 15 minutes")
async def login():
    ...
```

### 8.2 Limits
- **Public endpoints:** 100/hour per IP
- **Authenticated endpoints:** 1000/hour per user
- **Login attempts:** 5/15min per IP
- **Password reset:** 3/hour per email
- **API key endpoints:** 10000/hour per key

---

## 9. CORS

### 9.1 Production Config
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.example.com",
        "https://www.example.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=86400,
)
```

**Rules:**
- Never use `allow_origins=["*"]` with credentials
- Whitelist specific origins
- Don't allow all methods
- Limit exposed headers

---

## 10. Audit Logging

### 10.1 What to Log
- Authentication events (login, logout, failed attempts)
- Authorization failures
- Data access (sensitive data)
- Data modifications (create, update, delete)
- Configuration changes
- Security events (rate limits, suspicious activity)

### 10.2 Log Format
```python
logger.info("Data access", extra={
    "event_type": "data_access",
    "user_id": user.id,
    "resource": "todo",
    "resource_id": todo.id,
    "action": "read",
    "ip": request.client.host,
    "timestamp": datetime.utcnow().isoformat(),
    "request_id": request.headers.get("X-Request-ID"),
})
```

---

## 11. Incident Response

### 11.1 Plan
1. **Detect** — Monitoring, alerting, user reports
2. **Contain** — Isolate affected systems, revoke compromised credentials
3. **Eradicate** — Remove threat, patch vulnerabilities
4. **Recover** — Restore from backups, verify integrity
5. **Learn** — Post-mortem, update procedures

### 11.2 Have Runbooks
- Data breach response
- DDoS attack response
- Compromised credentials
- Ransomware response

---

## 12. Compliance

### 12.1 GDPR
- Data minimization
- Right to be forgotten
- Data portability
- Consent management
- Privacy by design
- 72-hour breach notification

### 12.2 HIPAA (Healthcare)
- PHI encryption at rest and in transit
- Access controls and audit logs
- Business Associate Agreements
- Risk assessments

### 12.3 PCI DSS (Payments)
- Never store CVV
- Tokenize card data
- PCI-compliant infrastructure
- Regular scans

### 12.4 SOC 2
- Security policies
- Access controls
- Monitoring and logging
- Incident response
- Change management

---

## 13. Security Testing

### 13.1 SAST (Static Analysis)
- Bandit (Python)
- ESLint security plugin
- Semgrep
- SonarQube

### 13.2 DAST (Dynamic Analysis)
- OWASP ZAP
- Burp Suite
- Nikto

### 13.3 Dependency Scanning
- pip-audit (Python)
- npm audit (JavaScript)
- Snyk
- Dependabot

### 13.4 Penetration Testing
- Annual third-party pentest
- Bug bounty program
- Internal security reviews

---

## 14. Anti-Patterns to Avoid

| Anti-Pattern | Risk | Instead |
|---|---|---|
| Storing plain-text passwords | Account takeover | bcrypt/argon2 |
| Sequential user IDs in URLs | Enumeration attacks | UUIDs |
| No rate limiting on auth | Brute force | Rate limit + lockout |
| Logging sensitive data | Data leak | Redact/mask |
| No HTTPS | Man-in-the-middle | TLS 1.3 only |
| `eval()` / `exec()` | Code injection | Avoid, use safe alternatives |
| Trusting client-side validation | Bypass attacks | Validate server-side |
| Long-lived JWTs | Token theft impact | Short access + refresh rotation |
| No CSRF protection | Unauthorized actions | SameSite cookies + tokens |
| Open CORS (`*`) | Cross-origin attacks | Whitelist specific origins |
| Hardcoded secrets | Secret leak | Env vars + secret manager |
| No security headers | XSS, clickjacking | All required headers |
| Verbose error messages | Info disclosure | Generic user-facing errors |
| Using MD5/SHA1 for passwords | Easily cracked | bcrypt/argon2/scrypt |

---

## 15. References

- [OWASP Top 10 (2023)](https://owasp.org/Top10/)
- [OWASP API Security Top 10 (2023)](https://owasp.org/API-Security/editions/2023/en/0x00-introduction/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CIS Controls](https://www.cisecurity.org/controls/)
- [Mozilla Web Security Guidelines](https://infosec.mozilla.org/guidelines/web_security)
