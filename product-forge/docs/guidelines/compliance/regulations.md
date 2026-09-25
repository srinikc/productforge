# Compliance Engineering Standards

> Regulatory compliance, audit, and governance for MyWorld Central Portal.

## Table of Contents

1. [Compliance Overview](#compliance-overview)
2. [GDPR (General Data Protection Regulation)](#gdpr-general-data-protection-regulation)
3. [SOC 2 (System and Organization Controls)](#soc-2-system-and-organization-controls)
4. [HIPAA (Health Insurance Portability and Accountability Act)](#hipaa)
5. [PCI DSS (Payment Card Industry Data Security Standard)](#pci-dss)
6. [CCPA (California Consumer Privacy Act)](#ccpa-california-consumer-privacy-act)
7. [Data Classification](#data-classification)
8. [Audit Logging](#audit-logging)
9. [Privacy by Design](#privacy-by-design)
10. [Data Retention](#data-retention)

---

## Compliance Overview

### Applicable Regulations

| Regulation | Applies To | Key Requirements |
|------------|-----------|------------------|
| **GDPR** | EU users | Data protection, right to be forgotten, consent |
| **SOC 2** | SaaS customers | Security, availability, confidentiality |
| **CCPA** | California users | Data disclosure, opt-out |
| **HIPAA** | Healthcare data | PHI protection, BAAs |
| **PCI DSS** | Payment data | Card data security, encryption |

### Compliance Roles

- **Data Controller** — Determines purpose and means of processing (MyWorld)
- **Data Processor** — Processes data on behalf of controller (us for customers)
- **Data Protection Officer (DPO)** — Oversees GDPR compliance
- **Security Officer** — Manages security controls
- **Auditor** — External/internal compliance auditor

---

## GDPR (General Data Protection Regulation)

### Key Principles

1. **Lawfulness, fairness, transparency**
2. **Purpose limitation** — Use data only for stated purpose
3. **Data minimization** — Collect only what's needed
4. **Accuracy** — Keep data accurate and up to date
5. **Storage limitation** — Don't keep data longer than needed
6. **Integrity and confidentiality** — Secure the data
7. **Accountability** — Demonstrate compliance

### User Rights Implementation

#### Right to Access (Article 15)

```python
# User can request all their data
@router.get("/users/me/data-export")
async def export_my_data(current_user: User = Depends(get_current_user)):
    """Export all user data (GDPR Article 15 - Right to Access)."""
    return {
        "personal_data": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "created_at": current_user.created_at,
        },
        "activity": {
            "posts": await get_user_posts(current_user.id),
            "comments": await get_user_comments(current_user.id),
            "sessions": await get_user_sessions(current_user.id),
        },
        "preferences": await get_user_preferences(current_user.id),
        "data_sources": [
            "Direct registration",
            "Authentication logs",
            "User-generated content",
        ],
    }
```

#### Right to Erasure / Right to be Forgotten (Article 17)

```python
# User can request account deletion
@router.delete("/users/me")
async def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete user account and all associated data (GDPR Article 17)."""
    # Soft delete first (30-day grace period)
    user = await db.get(User, current_user.id)
    user.deleted_at = datetime.utcnow()
    user.deletion_requested_at = datetime.utcnow()
    user.email = f"deleted-{user.id}@deleted.myworld.com"  # Anonymize
    user.full_name = "[DELETED]"
    user.hashed_password = ""  # Can't log in
    user.is_active = False
    
    await db.commit()
    
    # Schedule hard delete after grace period
    await schedule_hard_delete(user_id=user.id, days=30)
    
    return {"message": "Account scheduled for deletion", "grace_period_days": 30}


async def hard_delete_user(user_id: int, db: AsyncSession):
    """Permanently delete user and all data."""
    # Delete personal data
    await db.execute(delete(UserPost).where(UserPost.user_id == user_id))
    await db.execute(delete(UserComment).where(UserComment.user_id == user_id))
    
    # Anonymize activity logs
    await db.execute(
        update(ActivityLog)
        .where(ActivityLog.user_id == user_id)
        .values(user_id=None, anonymized=True)
    )
    
    # Delete account
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
    
    # Log deletion (anonymized)
    await audit_log(
        event="user.hard_deleted",
        user_id=user_id,
        timestamp=datetime.utcnow(),
    )
```

#### Right to Data Portability (Article 20)

```python
# Export data in machine-readable format
@router.get("/users/me/data-export.json")
async def export_my_data_json(current_user: User = Depends(get_current_user)):
    """Export user data in JSON format (GDPR Article 20)."""
    data = await export_my_data(current_user)
    
    return Response(
        content=json.dumps(data, indent=2, default=str),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=myworld-data-export-{datetime.utcnow().date()}.json"
        }
    )
```

#### Right to Rectification (Article 16)

```python
# Allow users to correct their data
@router.patch("/users/me")
async def update_my_profile(
    updates: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user profile (GDPR Article 16 - Right to Rectification)."""
    update_data = updates.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    await db.commit()
    return current_user
```

### Consent Management

```python
# Track user consent
class UserConsent(Base):
    __tablename__ = "user_consents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    consent_type: Mapped[str] = mapped_column(String(50))  # marketing, analytics, etc.
    granted: Mapped[bool] = mapped_column(Boolean)
    granted_at: Mapped[datetime] = mapped_column(DateTime)
    ip_address: Mapped[str] = mapped_column(String(45))
    user_agent: Mapped[str] = mapped_column(String(500))
    version: Mapped[str] = mapped_column(String(20))  # Privacy policy version
    
    # GDPR requires proof of consent


# Cookie consent
@router.post("/consent/cookies")
async def set_cookie_consent(
    consent: CookieConsent,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Record cookie consent."""
    await record_consent(
        user_id=current_user.id,
        consent_type="cookies",
        granted=consent.analytics_cookies,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
    )
    
    # Set consent cookie
    response.set_cookie(
        key="cookie_consent",
        value=json.dumps(consent.model_dump()),
        max_age=365 * 24 * 60 * 60,  # 1 year
        httponly=True,
        secure=True,
        samesite="strict",
    )
```

### Privacy Policy and Cookie Notice

```python
# Privacy policy versioning
PRIVACY_POLICY_VERSION = "2.1"  # Bump when policy changes


@router.get("/privacy-policy")
async def get_privacy_policy():
    return {
        "version": PRIVACY_POLICY_VERSION,
        "effective_date": "2026-08-15",
        "url": "https://myworld.com/privacy",
        "changes": [
            "Added data retention period clarifications",
            "Updated contact information for DPO",
        ],
    }


# Notify users when policy changes
@router.post("/privacy-policy/accept")
async def accept_privacy_policy(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.privacy_policy_version != PRIVACY_POLICY_VERSION:
        current_user.privacy_policy_version = PRIVACY_POLICY_VERSION
        current_user.privacy_policy_accepted_at = datetime.utcnow()
        await db.commit()
    
    return {"status": "accepted"}
```

### Data Breach Notification

```python
# GDPR requires breach notification within 72 hours
@router.post("/admin/security/breach-report")
async def report_data_breach(
    breach: DataBreachReport,
    current_user: User = Depends(require_admin),
):
    """Report a data breach to authorities within 72 hours."""
    # Log breach
    await audit_log(
        event="security.breach_reported",
        severity=breach.severity,
        affected_users=breach.affected_user_count,
        data_types=breach.data_types_affected,
    )
    
    # Notify DPO and security team
    await send_immediate_alert(
        channel="security-incidents",
        message=f"Data breach reported: {breach.description}",
        severity="critical",
    )
    
    # Schedule user notifications (within reasonable time)
    if breach.affected_user_count > 0:
        await schedule_user_breach_notifications(breach)
    
    return {"status": "reported", "timestamp": datetime.utcnow()}
```

---

## SOC 2 (System and Organization Controls)

### Trust Service Criteria

| Criteria | Description | MyWorld Implementation |
|----------|-------------|----------------------|
| **Security** | Protect against unauthorized access | MFA, RBAC, encryption |
| **Availability** | System is available | 99.9% SLA, monitoring |
| **Processing Integrity** | Process is complete, accurate | Validation, audit logs |
| **Confidentiality** | Protect sensitive information | Encryption, access controls |
| **Privacy** | Personal information is protected | GDPR, CCPA compliance |

### Security Controls Implementation

```python
# 1. Access Control (CC6.1)
- Multi-factor authentication (MFA) required for admin accounts
- Role-based access control (RBAC)
- Principle of least privilege
- Regular access reviews (quarterly)
- Automated user provisioning/deprovisioning


# 2. Authentication (CC6.2)
@router.post("/auth/login")
async def login(credentials: LoginInput):
    # Rate limiting (5 failed attempts per 15 minutes)
    if await is_rate_limited(credentials.email):
        raise HTTPException(429, "Too many failed attempts")
    
    user = await authenticate(credentials.email, credentials.password)
    if not user:
        await increment_failed_attempts(credentials.email)
        raise HTTPException(401, "Invalid credentials")
    
    # Require MFA for admin/sensitive accounts
    if user.requires_mfa:
        return {"requires_mfa": True, "mfa_token": generate_mfa_token(user.id)}
    
    return await issue_tokens(user)


# 3. Audit Logging (CC7.2)
async def audit_log(
    event: str,
    user_id: int | None = None,
    resource: str | None = None,
    action: str | None = None,
    **details
):
    """Create immutable audit log entry."""
    log_entry = AuditLog(
        event=event,
        user_id=user_id,
        resource=resource,
        action=action,
        timestamp=datetime.utcnow(),
        ip_address=details.get("ip_address"),
        user_agent=details.get("user_agent"),
        details=details,
    )
    db.add(log_entry)
    await db.commit()
    
    # Also send to immutable storage (S3 with object lock)
    await send_to_audit_storage(log_entry)
```

### Change Management (CC8.1)

```yaml
# All changes require:
1. Pull request with description
2. Code review approval (2+ reviewers for production)
3. Passing CI/CD pipeline (tests, lint, security scan)
4. Architecture review (for significant changes)
5. Approval from tech lead
6. Rollback plan documented
7. Deployment to staging first
8. Smoke tests before production deployment
```

### Incident Response (CC7.3)

```markdown
## Incident Response Plan

### Severity Levels

**SEV-1 (Critical):** Production down, data breach, security incident
- Response time: 15 minutes
- Notification: CEO, CTO, Security team
- Public status page update

**SEV-2 (High):** Degraded service, non-critical feature broken
- Response time: 1 hour
- Notification: Engineering team
- Status page update

**SEV-3 (Medium):** Minor issue, workaround available
- Response time: 4 hours
- Notification: Assigned engineer

**SEV-4 (Low):** Cosmetic, documentation
- Response time: Next business day

### Response Process

1. **Detect** — Monitoring alert or user report
2. **Triage** — Assess severity, assign incident commander
3. **Mitigate** — Stop the bleeding (rollback, disable feature, etc.)
4. **Resolve** — Fix the root cause
5. **Post-mortem** — Document what happened, how to prevent recurrence
```

### Vendor Management (CC9.2)

```markdown
## Third-Party Vendors

All vendors must:
- Sign Data Processing Agreement (DPA)
- Provide SOC 2 Type II report
- Document security controls
- Allow security audits
- Notify us of breaches within 24 hours
- Comply with GDPR/CCPA
```

---

## HIPAA (Health Insurance Portability and Accountability Act)

### When HIPAA Applies

If MyWorld stores, processes, or transmits Protected Health Information (PHI):
- Healthcare providers
- Health plans
- Healthcare clearinghouses
- Business Associates

### HIPAA Safeguards

```python
# 1. Access Control (164.312(a)(1))
- Unique user identification
- Emergency access procedure
- Automatic logoff
- Encryption/decryption

# 2. Audit Controls (164.312(b))
- Hardware, software, procedural mechanisms to record/examine activity
- All PHI access must be logged

# 3. Integrity Controls (164.312(c)(1))
- Protect PHI from improper alteration or destruction
- Implement mechanisms to verify PHI hasn't been altered

# 4. Person/Entity Authentication (164.312(d))
- Verify person/entity seeking access is who they claim to be

# 5. Transmission Security (164.312(e)(1))
- Integrity controls
- Encryption for PHI transmitted over network


# Implementation
@router.get("/health-records/{patient_id}")
async def get_patient_record(
    patient_id: str,
    current_user: User = Depends(require_healthcare_provider),
    db: AsyncSession = Depends(get_db),
):
    """Access PHI - requires audit logging and authentication."""
    # Verify relationship between provider and patient
    if not await verify_care_relationship(current_user.id, patient_id):
        raise HTTPException(403, "No care relationship with patient")
    
    # Log PHI access (required by HIPAA)
    await audit_log(
        event="phi.accessed",
        user_id=current_user.id,
        patient_id=patient_id,
        purpose=current_user.access_purpose,  # Treatment, payment, operations
        timestamp=datetime.utcnow(),
    )
    
    return await db.get(HealthRecord, patient_id)
```

---

## PCI DSS (Payment Card Industry Data Security Standard)

### When PCI DSS Applies

Any system that stores, processes, or transmits cardholder data.

### Best Practice: Don't Store Card Data

```python
# GOOD: Use Stripe/tokenization (PCI compliant out-of-box)
import stripe


@router.post("/payments/create-intent")
async def create_payment_intent(amount: int, currency: str = "usd"):
    """Create Stripe payment intent (no card data touches our servers)."""
    intent = stripe.PaymentIntent.create(
        amount=amount,
        currency=currency,
        automatic_payment_methods={"enabled": True},
    )
    return {"client_secret": intent.client_secret}


# Frontend uses Stripe Elements (PCI SAQ-A compliant)
# <Elements stripe={stripePromise}>
#   <CheckoutForm />
# </Elements>
```

### If You Must Handle Card Data (SAQ-D)

```python
# 1. Never store CVV/CVC
# 2. Encrypt card data at rest (AES-256)
# 3. Use TLS 1.2+ for transmission
# 4. Maintain secure network
# 5. Implement strong access controls
# 6. Regularly test security systems
# 7. Maintain information security policy


# Tokenization service
class TokenizationService:
    def tokenize_card(self, card_data: dict) -> str:
        """Replace sensitive card data with non-sensitive token."""
        # Use vault (e.g., Stripe, AWS Payment Cryptography)
        token = vault.encrypt(card_data)
        
        # Store mapping: token -> encrypted_pan (CVV NEVER stored)
        db.execute(
            "INSERT INTO card_tokens (token, encrypted_pan, last4, exp_month, exp_year) "
            "VALUES (?, ?, ?, ?, ?)",
            (token, encrypted_pan, card_data["number"][-4:], ...)
        )
        
        return token
```

---

## CCPA (California Consumer Privacy Act)

### Consumer Rights

1. **Right to Know** — What data is collected and how it's used
2. **Right to Delete** — Request deletion of personal information
3. **Right to Opt-Out** — Opt-out of sale of personal information
4. **Right to Non-Discrimination** — Equal service regardless of privacy choices

### Implementation

```python
# Right to Opt-Out of Sale
@router.post("/users/me/opt-out-sale")
async def opt_out_of_sale(current_user: User = Depends(get_current_user)):
    """CCPA: Opt out of sale of personal information."""
    current_user.ccpa_opt_out_sale = True
    current_user.ccpa_opt_out_at = datetime.utcnow()
    await db.commit()
    
    return {"status": "opted_out", "effective_date": datetime.utcnow()}


# "Do Not Sell My Personal Information" link
@router.get("/users/me/sale-status")
async def get_sale_status(current_user: User = Depends(get_current_user)):
    return {
        "data_sold": False,  # MyWorld doesn't sell data
        "opt_out_available": True,
        "opted_out": current_user.ccpa_opt_out_sale,
    }
```

---

## Data Classification

### Classification Levels

| Level | Description | Examples | Controls |
|-------|-------------|----------|----------|
| **Public** | Publicly available | Marketing materials | None |
| **Internal** | Internal use | Org structure, policies | Authentication |
| **Confidential** | Sensitive business | Financial data, source code | Encryption, access logs |
| **Restricted** | Highly sensitive | PII, PHI, payment data | Strong encryption, audit logs, MFA |

### Data Handling

```python
# GOOD: Tag data with classification
class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


# Apply controls based on classification
@router.get("/users/{user_id}/ssn")  # RESTRICTED data
async def get_ssn(
    user_id: int,
    current_user: User = Depends(require_mfa_and_admin),
):
    # Multiple controls: MFA + admin + audit log
    await audit_log(
        event="restricted_data.accessed",
        data_type="SSN",
        user_id=user_id,
        accessed_by=current_user.id,
    )
    
    return {"ssn": await get_user_ssn(user_id)}


# BAD: No controls on restricted data
@router.get("/users/{user_id}/ssn")
async def get_ssn(user_id: int, db: AsyncSession = Depends(get_db)):
    return {"ssn": await get_user_ssn(user_id)}  # ❌ No controls
```

---

## Audit Logging

### What to Audit

✅ **Audit:**
- Authentication events (login, logout, failed attempts)
- Authorization events (permission changes, role grants)
- Data access (especially sensitive data)
- Data modifications (create, update, delete)
- Administrative actions
- Configuration changes
- Security events (breaches, suspicious activity)

### Audit Log Structure

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    
    # Who
    user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    user_email: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    session_id: Mapped[str | None] = mapped_column(String(100))
    
    # What
    resource_type: Mapped[str | None] = mapped_column(String(50), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(50))  # CREATE, READ, UPDATE, DELETE
    outcome: Mapped[str] = mapped_column(String(20))  # SUCCESS, FAILURE
    
    # Context
    request_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Integrity
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))  # Tamper detection


# Create tamper-evident audit log
async def audit_log(event: str, **kwargs):
    log_entry = AuditLog(
        event_type=event,
        timestamp=datetime.utcnow(),
        **kwargs,
    )
    
    # Hash chain for tamper detection
    last_log = await get_last_audit_log()
    log_entry.previous_hash = last_log.hash if last_log else None
    log_entry.hash = compute_hash(log_entry)
    
    db.add(log_entry)
    await db.commit()
```

### Audit Log Retention

| Data Type | Retention | Justification |
|-----------|-----------|---------------|
| **Authentication logs** | 1 year | Security investigation |
| **Access logs** | 90 days | Operational, security |
| **Financial transactions** | 7 years | Tax/audit requirements |
| **PHI access** | 6 years | HIPAA requirement |
| **GDPR-related actions** | 3 years after account closure | Demonstrate compliance |
| **SOC 2 audit logs** | 1 year | Audit trail |

---

## Privacy by Design

### Seven Foundational Principles

1. **Proactive not Reactive** — Prevent, don't remediate
2. **Privacy as Default** — Maximum privacy without user action
3. **Privacy Embedded in Design** — Integral to system design
4. **Full Functionality** — Both privacy AND functionality
5. **End-to-End Security** — Throughout data lifecycle
6. **Visibility and Transparency** — Document practices
7. **Respect for User Privacy** — User-centric

### Implementation Checklist

```markdown
## Privacy by Design Checklist

### Data Collection
- [ ] Collect only necessary data
- [ ] Document purpose of collection
- [ ] Obtain informed consent
- [ ] Provide opt-out mechanisms

### Data Storage
- [ ] Encrypt at rest
- [ ] Encrypt in transit
- [ ] Minimize access (least privilege)
- [ ] Set retention periods
- [ ] Plan for secure deletion

### Data Processing
- [ ] Pseudonymize where possible
- [ ] Log all access to personal data
- [ ] Limit processing to stated purpose
- [ ] Implement data minimization

### Data Sharing
- [ ] DPAs with all processors
- [ ] User consent for sharing
- [ ] Data sharing agreements
- [ ] Track data flows

### User Rights
- [ ] Right to access (data export)
- [ ] Right to rectification
- [ ] Right to erasure
- [ ] Right to portability
- [ ] Right to object

### Transparency
- [ ] Privacy policy (clear, accessible)
- [ ] Cookie notice
- [ ] Data breach notification process
- [ ] DPO contact information
```

---

## Data Retention

### Retention Policy

```python
# GOOD: Automated data retention
import asyncio
from datetime import datetime, timedelta


async def delete_old_data():
    """Run daily to enforce retention policies."""
    # Delete audit logs older than 1 year
    cutoff = datetime.utcnow() - timedelta(days=365)
    await db.execute(
        delete(AuditLog).where(AuditLog.timestamp < cutoff)
    )
    
    # Delete inactive sessions older than 30 days
    session_cutoff = datetime.utcnow() - timedelta(days=30)
    await db.execute(
        delete(Session).where(Session.last_active < session_cutoff)
    )
    
    # Anonymize deleted accounts after grace period
    hard_delete_cutoff = datetime.utcnow() - timedelta(days=30)
    expired_deletions = await db.execute(
        select(User)
        .where(
            User.deletion_requested_at < hard_delete_cutoff,
            User.deleted_at.is_not(None),
        )
    )
    
    for user in expired_deletions.scalars():
        await hard_delete_user(user.id, db)
    
    await db.commit()
```

### Documented Retention Schedule

| Data Type | Retention Period | Deletion Method |
|-----------|-----------------|-----------------|
| Active user accounts | While account active + 30 days grace | Soft delete → Hard delete |
| User data (inactive) | 30 days after last activity | Anonymize |
| Audit logs | 1 year | Permanent delete |
| Authentication logs | 1 year | Permanent delete |
| Financial records | 7 years | Permanent delete |
| PHI | 6 years after last access | Permanent delete |
| Marketing consent | Until withdrawn | Permanent delete |
| Session data | 30 days | Permanent delete |
| Backups | 90 days | Encrypted permanent delete |

---

## Best Practices Summary

| ✅ DO | ❌ DON'T |
|---|---|
| Implement privacy by design | Add privacy as an afterthought |
| Document all data processing | Process data without documentation |
| Obtain explicit consent | Assume consent |
| Implement data minimization | Collect everything "just in case" |
| Use encryption for sensitive data | Store sensitive data in plain text |
| Implement audit logging for all sensitive access | Skip logging for performance |
| Honor user rights (access, deletion, portability) | Ignore or delay user requests |
| Have incident response plan | Wait until breach happens |
| Sign DPAs with all vendors | Share data without agreements |
| Conduct regular compliance audits | Only check during official audits |
| Train employees on compliance | Assume everyone knows the rules |
| Implement data retention policies | Keep data forever |
| Use tokenization for payment data | Store credit card numbers |
| Conduct DPIA (Data Protection Impact Assessment) | Skip impact assessment for new features |

---

## References

- [GDPR Official Text](https://gdpr-info.eu/)
- [SOC 2 Compliance](https://www.aicpa.org/topic/soc-2)
- [HIPAA](https://www.hhs.gov/hipaa/index.html)
- [PCI DSS](https://www.pcisecuritystandards.org/)
- [CCPA](https://oag.ca.gov/privacy/ccpa)
- [Privacy by Design](https://www.ipc.on.ca/health-individuals/privacy-by-design/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [ISO 27001](https://www.iso.org/standard/27001)
