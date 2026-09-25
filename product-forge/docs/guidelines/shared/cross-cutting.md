# Cross-Cutting Concerns

> Shared patterns and practices that apply across all layers of MyWorld Central Portal.

## Table of Contents

1. [Error Handling Philosophy](#error-handling-philosophy)
2. [Logging Conventions](#logging-conventions)
3. [Configuration Management](#configuration-management)
4. [Feature Flags](#feature-flags)
5. [Internationalization (i18n)](#internationalization-i18n)
6. [Time and Timezone Handling](#time-and-timezone-handling)
7. [Money and Currency](#money-and-currency)
8. [Email Communications](#email-communications)
9. [File Handling](#file-handling)
10. [Rate Limiting](#rate-limiting)
11. [Idempotency](#idempotency)
12. [Background Jobs](#background-jobs)

---

## Error Handling Philosophy

### Error Categories

| Category | HTTP Status | User-Facing? | Logged? |
|----------|-------------|--------------|---------|
| **Validation Error** | 400/422 | Yes (specific) | Yes |
| **Authentication Error** | 401 | Generic | Yes |
| **Authorization Error** | 403 | Generic | Yes (with context) |
| **Not Found** | 404 | Generic | Sometimes |
| **Conflict** | 409 | Yes (specific) | Yes |
| **Rate Limit** | 429 | Generic | Yes |
| **Server Error** | 500 | Generic | Yes (with stack) |

### Standard Error Response Format

```python
# GOOD: Consistent error response structure
{
  "error": {
    "code": "validation_error",
    "message": "Invalid input data",
    "details": {
      "field": "email",
      "reason": "Invalid email format"
    },
    "request_id": "abc123",
    "timestamp": "2026-08-30T12:00:00Z",
    "documentation_url": "https://docs.myworld.com/errors/validation"
  }
}


# Python implementation
class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | None = None
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())
    documentation_url: str | None = None


@router.exception_handler(MyWorldException)
async def myworld_exception_handler(request: Request, exc: MyWorldException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": ErrorResponse(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=request.headers.get("X-Request-ID"),
                documentation_url=f"https://docs.myworld.com/errors/{exc.code}",
            ).model_dump()
        }
    )
```

### Error Handling Patterns

```python
# Pattern 1: Fail fast
def process_payment(amount: Decimal, card_token: str):
    if amount <= 0:
        raise ValidationError("Amount must be positive")
    
    result = stripe.charge(card_token, amount)
    return result


# Pattern 2: Graceful degradation
async def get_recommendations(user_id: int) -> list[Product]:
    try:
        return await ml_service.get_recommendations(user_id)
    except Exception as e:
        # Service down, return popular products instead
        logger.warning(f"ML service unavailable: {e}")
        return await get_popular_products()


# Pattern 3: Circuit breaker
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
async def call_external_api(url: str):
    """Call external API with circuit breaker."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=5.0)
        response.raise_for_status()
        return response.json()
```

---

## Logging Conventions

### Log Levels

| Level | When to Use | Example |
|-------|-------------|---------|
| **DEBUG** | Detailed diagnostic info | Variable values, flow control |
| **INFO** | Normal events | User created, order placed |
| **WARNING** | Potential issues | Rate limit approaching, retry |
| **ERROR** | Errors that need attention | Failed payment, DB error |
| **CRITICAL** | System-level failures | Database unreachable, OOM |

### What to Log

```python
# GOOD: Log with context
logger.info(
    "Order created",
    extra={
        "order_id": order.id,
        "user_id": order.user_id,
        "total": str(order.total),
        "item_count": len(order.items),
        "request_id": request_id,
    }
)


# GOOD: Log business events
logger.info("user.signup", extra={"user_id": user.id, "source": "organic"})
logger.info("order.created", extra={"order_id": order.id, "amount": order.total})
logger.info("payment.completed", extra={"payment_id": payment.id})


# GOOD: Log errors with full context
try:
    result = process_payment(order)
except PaymentError as e:
    logger.error(
        "Payment processing failed",
        extra={
            "order_id": order.id,
            "user_id": order.user_id,
            "amount": str(order.total),
            "error_code": e.code,
            "error_message": str(e),
        },
        exc_info=True,
    )
    raise
```

### What NOT to Log

```python
# ❌ NEVER log sensitive data
logger.info(f"Login attempt: {email} / {password}")  # ❌ PASSWORD
logger.info(f"API call with key: {api_key}")  # ❌ SECRET
logger.info(f"Card: {card_number}")  # ❌ PCI
logger.info(f"SSN: {ssn}")  # ❌ PII

# ✅ Mask or omit sensitive data
logger.info(f"Login attempt: {email} / ****")
logger.info(f"API call authenticated: {bool(api_key)}")
logger.info(f"Card: ****-****-****-{last4}")
logger.info(f"User authenticated: {user_id}")
```

### Correlation IDs

```python
import contextvars
import uuid

request_id_var = contextvars.ContextVar("request_id", default=None)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    # Get or generate request ID
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request_id_var.set(request_id)
    
    # Process request
    response = await call_next(request)
    
    # Add to response
    response.headers["X-Request-ID"] = request_id
    return response


def get_logger(name: str):
    """Get logger with automatic request context."""
    return logging.LoggerAdapter(
        logging.getLogger(name),
        {"request_id": request_id_var.get()}
    )
```

---

## Configuration Management

### 12-Factor App Principles

```python
# GOOD: Configuration from environment
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "MyWorld API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Security
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    
    # External services
    STRIPE_API_KEY: str
    SENDGRID_API_KEY: str
    
    # Feature flags
    ENABLE_NEW_CHECKOUT: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Singleton settings
settings = Settings()
```

### Environment-Specific Configs

```bash
# .env.development
ENVIRONMENT=development
DEBUG=true
DATABASE_URL=postgresql://localhost/myworld_dev
LOG_LEVEL=DEBUG

# .env.production
ENVIRONMENT=production
DEBUG=false
DATABASE_URL=${SECRET_DATABASE_URL}
LOG_LEVEL=INFO
SENTRY_DSN=${SECRET_SENTRY_DSN}
```

### Secrets Management

```python
# GOOD: Use secrets manager in production
import boto3
import json


def get_secret(secret_name: str) -> str:
    """Fetch secret from AWS Secrets Manager."""
    if settings.is_production:
        client = boto3.client("secretsmanager", region_name="us-east-1")
        response = client.get_secret_value(SecretId=secret_name)
        return response["SecretString"]
    else:
        # Use env var in dev
        return os.environ[secret_name]


# Use secrets
STRIPE_API_KEY = get_secret("myworld/production/stripe")
```

---

## Feature Flags

### Implementation

```python
# feature_flags.py
from enum import Enum


class FeatureFlag(str, Enum):
    NEW_CHECKOUT = "new_checkout"
    DARK_MODE = "dark_mode"
    AI_RECOMMENDATIONS = "ai_recommendations"
    BETA_FEATURES = "beta_features"


# Simple in-memory feature flags
_feature_flags: dict[str, bool] = {
    FeatureFlag.NEW_CHECKOUT: False,
    FeatureFlag.DARK_MODE: True,
    FeatureFlag.AI_RECOMMENDATIONS: True,
}


def is_feature_enabled(flag: FeatureFlag, user_id: int | None = None) -> bool:
    """Check if feature is enabled."""
    # Simple boolean flag
    if not _feature_flags.get(flag, False):
        return False
    
    # Beta features only for specific users
    if flag == FeatureFlag.BETA_FEATURES:
        return user_id in settings.BETA_TESTER_IDS
    
    return True


# Usage
@router.get("/checkout")
async def get_checkout(current_user: User = Depends(get_current_user)):
    if is_feature_enabled(FeatureFlag.NEW_CHECKOUT, current_user.id):
        return NewCheckoutView()
    return OldCheckoutView()
```

### Advanced: LaunchDarkly or Unleash

```python
# GOOD: Use feature flag service for production
import ldclient
from ldclient import Context


ldclient.set_sdk_key(settings.LAUNCHDARKLY_SDK_KEY)
ld_client = ldclient.get()


def is_feature_enabled(flag_key: str, user: User) -> bool:
    """Check feature flag with LaunchDarkly."""
    context = Context.create(user.id, {
        "email": user.email,
        "plan": user.plan,
    })
    
    return ld_client.variation(flag_key, context, default=False)


# Usage
if is_feature_enabled("new-checkout", current_user):
    return NewCheckoutView()
```

---

## Internationalization (i18n)

### Message Catalogs

```python
# messages/en.json
{
    "user.created": "User {name} created successfully",
    "user.not_found": "User with ID {id} not found",
    "order.total": "Order total: ${amount}",
    "validation.required": "Field {field} is required"
}

# messages/es.json
{
    "user.created": "Usuario {name} creado exitosamente",
    "user.not_found": "Usuario con ID {id} no encontrado",
    "order.total": "Total del pedido: ${amount}",
    "validation.required": "El campo {field} es obligatorio"
}
```

### i18n Implementation

```python
import json
from pathlib import Path


class Translator:
    def __init__(self):
        self.translations = {}
        self.default_locale = "en"
        self._load_translations()
    
    def _load_translations(self):
        messages_dir = Path("messages")
        for file in messages_dir.glob("*.json"):
            locale = file.stem
            with open(file) as f:
                self.translations[locale] = json.load(f)
    
    def translate(self, key: str, locale: str = "en", **kwargs) -> str:
        """Translate message with variable substitution."""
        message = (
            self.translations
            .get(locale, {})
            .get(key, self.translations[self.default_locale].get(key, key))
        )
        return message.format(**kwargs)


translator = Translator()


# Usage
message = translator.translate(
    "user.created",
    locale="es",
    name="Juan"
)
# "Usuario Juan creado exitosamente"
```

### API Localization

```python
# GOOD: Accept language in request
from fastapi import Header


@router.get("/messages/welcome")
async def get_welcome_message(
    accept_language: str = Header(default="en"),
):
    locale = accept_language.split(",")[0].split("-")[0]  # "en-US" -> "en"
    return {
        "message": translator.translate("welcome", locale=locale)
    }
```

---

## Time and Timezone Handling

### Always Store UTC

```python
from datetime import datetime, timezone


# GOOD: Always use UTC in database
@router.post("/events")
async def create_event(event_in: EventCreate):
    event = Event(
        name=event_in.name,
        scheduled_at=event_in.scheduled_at.astimezone(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()


# BAD: Store local time (ambiguous)
event.scheduled_at = datetime.now()  # ❌ Which timezone?
```

### Display in User's Timezone

```python
# Frontend: Convert UTC to local time
const eventDate = new Date(event.scheduled_at_utc);  // UTC from server
const localTime = eventDate.toLocaleString();  // User's local time
```

### Date Models

```python
from pydantic import BaseModel, field_validator
from datetime import datetime, timezone


class EventCreate(BaseModel):
    name: str
    scheduled_at: datetime
    
    @field_validator("scheduled_at")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Convert to UTC if not already."""
        if v.tzinfo is None:
            # Naive datetime, assume UTC
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)
```

---

## Money and Currency

### Use Decimal, Never Float

```python
from decimal import Decimal


# GOOD: Use Decimal for money
price: Decimal = Decimal("99.99")
total: Decimal = price * quantity  # Exact calculation

# BAD: Use float (precision errors)
price: float = 99.99  # ❌ 0.1 + 0.2 != 0.3
```

### Store as Cents (Integer)

```python
# GOOD: Store as integer cents
class Product(Base):
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    price_cents: Mapped[int] = mapped_column(Integer)  # 9999 = $99.99
    currency: Mapped[str] = mapped_column(String(3), default="USD")


# Convert to/from dollars
def dollars_to_cents(dollars: Decimal) -> int:
    return int(dollars * 100)


def cents_to_dollars(cents: int) -> Decimal:
    return Decimal(cents) / 100


# Pydantic schema
class ProductResponse(BaseModel):
    name: str
    price: Decimal  # $99.99
    currency: str
    
    @classmethod
    def from_orm(cls, product: Product):
        return cls(
            name=product.name,
            price=cents_to_dollars(product.price_cents),
            currency=product.currency,
        )
```

### Currency Conversion

```python
# GOOD: Use external API for conversion, cache results
import httpx


@cache(ttl=3600, key_prefix="fx_rate")
async def get_exchange_rate(from_currency: str, to_currency: str) -> Decimal:
    """Get current exchange rate."""
    if from_currency == to_currency:
        return Decimal("1.0")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
        )
        data = response.json()
        rate = data["rates"][to_currency]
        return Decimal(str(rate))


# Convert amounts
def convert(amount: Decimal, from_curr: str, to_curr: str) -> Decimal:
    rate = get_exchange_rate(from_curr, to_curr)
    return (amount * rate).quantize(Decimal("0.01"))
```

---

## Email Communications

### Email Service Interface

```python
from abc import ABC, abstractmethod


class EmailService(ABC):
    @abstractmethod
    async def send(self, to: str, subject: str, html: str, text: str | None = None):
        pass


class SendGridEmailService(EmailService):
    def __init__(self):
        from sendgrid import SendGridAPIClient
        self.client = SendGridAPIClient(settings.SENDGRID_API_KEY)
    
    async def send(self, to: str, subject: str, html: str, text: str | None = None):
        from sendgrid.helpers.mail import Mail
        
        message = Mail(
            from_email="noreply@myworld.com",
            to_emails=to,
            subject=subject,
            html_content=html,
            plain_text_content=text,
        )
        
        response = self.client.send(message)
        return response.status_code


# Usage (async via queue)
async def send_welcome_email(user: User):
    html = render_template("welcome.html", user=user)
    text = render_template("welcome.txt", user=user)
    
    await celery_app.send_task(
        "send_email",
        args=[user.email, "Welcome to MyWorld", html, text],
    )
```

### Email Templates

```python
# templates/welcome.html
<!DOCTYPE html>
<html>
<head>
    <title>Welcome to MyWorld</title>
</head>
<body>
    <h1>Welcome {{ user.full_name }}!</h1>
    <p>Thanks for signing up for MyWorld.</p>
    <a href="https://myworld.com/dashboard">Go to dashboard</a>
</body>
</html>
```

---

## File Handling

### File Upload

```python
from fastapi import UploadFile, File
import magic  # python-magic for file type detection


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = ["image/jpeg", "image/png", "application/pdf"]


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload file with validation."""
    # Check size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large (max 10MB)")
    
    # Check type (don't trust Content-Type header)
    actual_type = magic.from_buffer(contents, mime=True)
    if actual_type not in ALLOWED_TYPES:
        raise HTTPException(415, f"File type not allowed: {actual_type}")
    
    # Generate safe filename
    import secrets
    safe_filename = f"{secrets.token_urlsafe(16)}.{get_extension(actual_type)}"
    
    # Upload to S3
    s3_client.put_object(
        Bucket="myworld-uploads",
        Key=f"uploads/{current_user.id}/{safe_filename}",
        Body=contents,
        ContentType=actual_type,
    )
    
    return {"filename": safe_filename, "size": len(contents)}
```

### File Download (Presigned URLs)

```python
# GOOD: Use S3 presigned URLs instead of proxying through API
@router.get("/files/{file_id}/download-url")
async def get_download_url(
    file_id: str,
    current_user: User = Depends(get_current_user),
):
    """Generate presigned download URL."""
    # Check user has access to this file
    file = await get_file(file_id)
    if not user_has_access(current_user, file):
        raise HTTPException(403, "Access denied")
    
    # Generate presigned URL (expires in 1 hour)
    url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": file.bucket, "Key": file.key},
        ExpiresIn=3600,
    )
    
    return {"download_url": url, "expires_in": 3600}
```

---

## Rate Limiting

### Implementation

```python
import redis.asyncio as redis
from fastapi import Request
import time


class RateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def check(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """
        Check if request is allowed.
        Returns (allowed, remaining_requests).
        """
        now = time.time()
        window_start = now - window_seconds
        
        # Use sliding window with sorted set
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
        
        request_count = results[2]
        
        if request_count > max_requests:
            return False, 0
        
        return True, max_requests - request_count


rate_limiter = RateLimiter(redis_client)


# Usage as dependency
async def rate_limit_dependency(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    key = f"rate_limit:user:{current_user.id}:{request.url.path}"
    allowed, remaining = await rate_limiter.check(
        key, max_requests=100, window_seconds=60
    )
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"}
        )
    
    return current_user


# Apply to endpoints
@router.get("/api/v1/expensive-operation")
async def expensive_operation(user: User = Depends(rate_limit_dependency)):
    return {"result": "..."}
```

---

## Idempotency

### Idempotency Keys

```python
import hashlib


class IdempotencyMiddleware:
    """Ensure endpoints are idempotent using idempotency keys."""
    
    async def __call__(self, request: Request, call_next):
        # Only apply to mutating requests
        if request.method not in ["POST", "PUT", "PATCH"]:
            return await call_next(request)
        
        # Get idempotency key from header
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)
        
        # Check if request was already processed
        cache_key = f"idempotency:{idempotency_key}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            # Return cached response
            return JSONResponse(
                content=json.loads(cached),
                status_code=200,
            )
        
        # Process request
        response = await call_next(request)
        
        # Cache successful response (24 hours)
        if 200 <= response.status_code < 300:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            await redis_client.setex(
                cache_key,
                86400,  # 24 hours
                body.decode(),
            )
            
            return Response(
                content=body,
                status_code=response.status_code,
                headers=response.headers,
            )
        
        return response
```

### Idempotent Operations

```python
# GOOD: Idempotent payment processing
@router.post("/payments", headers={"Idempotency-Key": "..."})
async def create_payment(
    payment_in: PaymentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    # Check if payment already exists
    existing = await db.execute(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    if existing.scalar_one_or_none():
        return existing  # Return existing payment, don't create duplicate
    
    # Create payment
    payment = Payment(
        amount=payment_in.amount,
        idempotency_key=idempotency_key,
    )
    db.add(payment)
    await db.commit()
    
    return payment
```

---

## Background Jobs

### Celery for Heavy Tasks

```python
# tasks/celery_app.py
from celery import Celery


celery_app = Celery(
    "myworld",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes hard limit
    task_soft_time_limit=540,  # 9 minutes soft limit
    worker_max_tasks_per_child=1000,
    worker_prefetch_multiplier=1,
)


# tasks/email.py
@celery_app.task(bind=True, max_retries=3)
def send_email_task(self, to: str, subject: str, html: str):
    """Send email with retry logic."""
    try:
        email_service.send(to, subject, html)
        return {"status": "sent", "to": to}
    except (ConnectionError, TimeoutError) as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


# Usage in endpoint
@router.post("/orders")
async def create_order(order_in: OrderCreate):
    order = await OrderService.create(order_in)
    
    # Queue async tasks
    send_email_task.delay(order.customer_email, "Order Confirmation", "...")
    update_inventory_task.delay(order.product_id, order.quantity)
    notify_warehouse_task.delay(order.id)
    
    return order
```

### Job Status Tracking

```python
# GOOD: Track job status for long-running operations
@celery_app.task(bind=True)
def long_running_task(self, job_id: str, data: dict):
    """Long-running task with progress tracking."""
    total_steps = 10
    
    for step in range(total_steps):
        # Do work
        process_step(data, step)
        
        # Update progress
        self.update_state(
            state="PROGRESS",
            meta={
                "current": step + 1,
                "total": total_steps,
                "percent": (step + 1) / total_steps * 100,
            },
        )
    
    return {"status": "completed", "result": "..."}


# Check job status
@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    result = AsyncResult(job_id, app=celery_app)
    
    if result.state == "PROGRESS":
        return {
            "status": "running",
            "progress": result.info,
        }
    elif result.state == "SUCCESS":
        return {
            "status": "completed",
            "result": result.result,
        }
    elif result.state == "FAILURE":
        return {
            "status": "failed",
            "error": str(result.info),
        }
```

---

## Best Practices Summary

| ✅ DO | ❌ DON'T |
|---|---|
| Use consistent error response format | Return ad-hoc error structures |
| Log with context (request_id, user_id) | Log bare messages |
| Store all times in UTC | Mix UTC and local times |
| Use Decimal for money | Use float for currency |
| Validate file types (not just extensions) | Trust Content-Type headers |
| Use presigned URLs for file downloads | Proxy files through API |
| Implement rate limiting | Allow unlimited requests |
| Make operations idempotent | Process duplicate requests |
| Use background jobs for heavy work | Block API responses |
| Use environment variables for config | Hardcode configuration |
| Use feature flags for gradual rollouts | Deploy features to everyone at once |
| Mask sensitive data in logs | Log passwords, secrets, PII |
| Use correlation IDs for request tracing | Lose context between services |
| Handle timezones correctly | Assume server timezone is user's |

---

## References

- [12-Factor App](https://12factor.net/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [REST API Best Practices](https://restfulapi.net/)
- [Feature Flag Best Practices](https://martinfowler.com/articles/feature-toggles.html)
- [Idempotency Keys (Stripe)](https://stripe.com/docs/api/idempotent_requests)
- [Celery Documentation](https://docs.celeryproject.org/)
- [Money in Python](https://github.com/carlospalol/money)
