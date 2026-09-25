# Monitoring and Observability Standards

> Logging, metrics, tracing, and alerting for MyWorld Central Portal.

## Table of Contents

1. [The Three Pillars](#the-three-pillars)
2. [Structured Logging](#structured-logging)
3. [Metrics](#metrics)
4. [Distributed Tracing](#distributed-tracing)
5. [Health Checks](#health-checks)
6. [Alerting](#alerting)
7. [Dashboards](#dashboards)
8. [Error Tracking](#error-tracking)
9. [SLIs, SLOs, and SLAs](#slis-slos-and-slas)

---

## The Three Pillars

| Pillar | Purpose | Tools |
|--------|---------|-------|
| **Logs** | Discrete events with context | CloudWatch, ELK, Loki |
| **Metrics** | Numerical data over time | Prometheus, CloudWatch, DataDog |
| **Traces** | Request flow across services | OpenTelemetry, Jaeger, X-Ray |

### When to Use Each

- **Logs:** Debugging specific issues, audit trail
- **Metrics:** Aggregate trends, alerting (CPU, latency, error rate)
- **Traces:** Performance bottlenecks, distributed request flow

---

## Structured Logging

### JSON Logging (Python)

```python
# core/logging.py
import logging
import sys
import json
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "myworld-api",
            "environment": settings.ENVIRONMENT,
        }
        
        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add custom fields from extra
        for key, value in record.__dict__.items():
            if key not in self._RESERVED_FIELDS:
                log_data[key] = value
        
        return json.dumps(log_data, default=str)
    
    _RESERVED_FIELDS = frozenset({
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "message",
    })


def setup_logging():
    """Configure application logging."""
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    
    if settings.is_production:
        handler.setFormatter(JSONFormatter())
    else:
        # Pretty logs for development
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
    
    root.addHandler(handler)
    
    # Reduce noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
```

### Logging Best Practices

```python
# GOOD: Include context with extra fields
logger.info(
    "User created successfully",
    extra={
        "user_id": user.id,
        "email": user.email,
        "organization_id": user.org_id,
        "request_id": request_id,
    }
)


# GOOD: Log at appropriate levels
logger.debug("Detailed diagnostic info")      # Dev debugging
logger.info("User logged in")                  # Normal events
logger.warning("Rate limit approaching")       # Potential issues
logger.error("Payment processing failed")      # Errors
logger.critical("Database unreachable")        # System-level failures


# GOOD: Include request context
import contextvars

request_id_var = contextvars.ContextVar("request_id", default=None)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request_id_var.set(request_id)
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def get_logger(name: str) -> logging.Logger:
    """Get logger with request context."""
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, {"request_id": request_id_var.get()})


# Usage
logger = get_logger(__name__)
logger.info("Processing request", extra={"user_id": 123})
```

### What NOT to Log

❌ **Never log:**
- Passwords or password hashes
- API keys, tokens, secrets
- Credit card numbers (PCI compliance)
- Social security numbers
- Full credit card numbers (mask: `****-****-****-1234`)

✅ **Safe to log:**
- User IDs (not emails if sensitive)
- Request IDs
- Error messages (sanitized)
- Performance metrics
- Business events

### Log Aggregation (CloudWatch)

```python
# Install awslogs agent or use ECS log driver
# Already configured in ECS task definition:

"logConfiguration": {
    "logDriver": "awslogs",
    "options": {
        "awslogs-group": "/ecs/myworld-api",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "ecs"
    }
}
```

---

## Metrics

### Prometheus Metrics (Python)

```python
from prometheus_client import (
    Counter, Histogram, Gauge, Summary,
    generate_latest, CONTENT_TYPE_LATEST
)
import time
from functools import wraps


# Counters (monotonically increasing)
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

http_errors_total = Counter(
    "http_errors_total",
    "Total HTTP errors",
    ["method", "endpoint", "status_class"]  # 4xx, 5xx
)

user_signups_total = Counter(
    "user_signups_total",
    "Total user signups",
    ["source"]  # organic, referral, etc.
)


# Histograms (distributions)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation", "table"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)


# Gauges (point-in-time values)
active_users = Gauge(
    "active_users",
    "Number of active users"
)

db_pool_connections = Gauge(
    "db_pool_connections",
    "Database connection pool stats",
    ["state"]  # active, idle, overflow
)


# Summaries (similar to histograms, with quantiles)
request_size_bytes = Summary(
    "request_size_bytes",
    "Request size in bytes",
    ["method", "endpoint"]
)


# Middleware to record metrics
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    
    # Record metrics
    http_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()
    
    http_request_duration_seconds.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(duration)
    
    if response.status_code >= 400:
        status_class = f"{response.status_code // 100}xx"
        http_errors_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status_class=status_class,
        ).inc()
    
    return response


# Metrics endpoint
@app.get("/metrics")
async def metrics():
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
```

### Custom Business Metrics

```python
# GOOD: Track business KPIs
orders_created_total = Counter(
    "orders_created_total",
    "Total orders created",
    ["product_category", "payment_method"]
)

revenue_total = Counter(
    "revenue_total_dollars",
    "Total revenue in dollars",
    ["product_category"]
)


@router.post("/orders")
async def create_order(order_in: OrderCreate):
    order = await OrderService.create(order_in)
    
    # Record business metrics
    orders_created_total.labels(
        product_category=order.product.category,
        payment_method=order.payment.method,
    ).inc()
    
    revenue_total.labels(
        product_category=order.product.category,
    ).inc(order.total)
    
    return order
```

---

## Distributed Tracing

### OpenTelemetry Setup

```python
# tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource


def setup_tracing():
    """Initialize OpenTelemetry tracing."""
    resource = Resource.create({
        "service.name": "myworld-api",
        "service.version": "1.0.0",
        "deployment.environment": settings.ENVIRONMENT,
    })
    
    provider = TracerProvider(resource=resource)
    
    # OTLP exporter (e.g., to Jaeger, Tempo, or X-Ray)
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://otel-collector:4317",
        insecure=True,
    )
    
    provider.add_span_processor(
        BatchSpanProcessor(otlp_exporter)
    )
    
    trace.set_tracer_provider(provider)
    
    # Auto-instrument frameworks
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()


# Custom spans
tracer = trace.get_tracer(__name__)


@router.get("/users/{user_id}")
async def get_user(user_id: int):
    with tracer.start_as_current_span("get_user") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("user.requested_at", datetime.now().isoformat())
        
        # Nested span for DB query
        with tracer.start_as_current_span("db.query") as db_span:
            db_span.set_attribute("db.system", "postgresql")
            db_span.set_attribute("db.operation", "SELECT")
            db_span.set_attribute("db.table", "users")
            
            user = await db.get(User, user_id)
        
        if not user:
            span.set_attribute("user.found", False)
            raise HTTPException(404, "User not found")
        
        span.set_attribute("user.found", True)
        span.set_attribute("user.email", user.email)
        
        return user
```

### Trace Context Propagation

```python
# GOOD: Propagate trace context across services
import httpx
from opentelemetry import trace
from opentelemetry.propagate import inject


async def call_external_service(url: str):
    """Call external service with trace context propagation."""
    headers = {}
    inject(headers)  # Inject trace context into headers
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return response.json()
```

---

## Health Checks

### Liveness vs Readiness

```python
# GOOD: Separate liveness and readiness
@router.get("/health/live")
async def liveness():
    """Liveness: Is the process alive?"""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db), redis=Depends(redis_dep)):
    """Readiness: Can the process handle requests?"""
    checks = {"status": "ready", "checks": {}}
    
    # Check database
    try:
        await db.execute("SELECT 1")
        checks["checks"]["database"] = "ok"
    except Exception as e:
        checks["status"] = "not_ready"
        checks["checks"]["database"] = f"failed: {e}"
    
    # Check Redis
    try:
        await redis.ping()
        checks["checks"]["redis"] = "ok"
    except Exception as e:
        checks["status"] = "not_ready"
        checks["checks"]["redis"] = f"failed: {e}"
    
    if checks["status"] != "ready":
        raise HTTPException(status_code=503, detail=checks)
    
    return checks
```

### Kubernetes Health Probes

```yaml
# k8s deployment
spec:
  containers:
    - name: api
      livenessProbe:
        httpGet:
          path: /health/live
          port: 8000
        initialDelaySeconds: 30
        periodSeconds: 10
        timeoutSeconds: 5
        failureThreshold: 3
      
      readinessProbe:
        httpGet:
          path: /health/ready
          port: 8000
        initialDelaySeconds: 5
        periodSeconds: 5
        timeoutSeconds: 3
        failureThreshold: 3
```

---

## Alerting

### Alert Philosophy

✅ **Alert on symptoms, not causes:**
- ❌ "CPU is 85%" (cause)
- ✅ "API p99 latency > 2s" (symptom affecting users)

✅ **Actionable alerts:**
- Include runbook link
- Clear severity (critical/warning)
- Auto-remediation where possible

### Alert Rules (Prometheus)

```yaml
# alerts.yml
groups:
  - name: api_alerts
    interval: 30s
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          (
            sum(rate(http_requests_total{status=~"5.."}[5m]))
            /
            sum(rate(http_requests_total[5m]))
          ) > 0.05
        for: 5m
        labels:
          severity: critical
          service: api
        annotations:
          summary: "API error rate above 5%"
          description: "{{ $value | humanizePercentage }} of requests are failing"
          runbook: "https://wiki.myworld.com/runbooks/high-error-rate"
      
      # High latency
      - alert: HighAPILatency
        expr: |
          histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))
          > 1
        for: 10m
        labels:
          severity: warning
          service: api
        annotations:
          summary: "API p95 latency above 1s for endpoint {{ $labels.endpoint }}"
      
      # Database connection pool exhausted
      - alert: DBPoolExhausted
        expr: db_pool_connections{state="overflow"} > 5
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool exhausted"
      
      # No traffic (potential outage)
      - alert: NoTraffic
        expr: sum(rate(http_requests_total[5m])) == 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "No traffic to API for 5 minutes"
```

### PagerDuty Integration

```python
# GOOD: Escalate critical alerts to PagerDuty
# Prometheus AlertManager configuration
receivers:
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: '<pagerduty-integration-key>'
        severity: 'critical'
        description: '{{ .GroupLabels.alertname }}: {{ .CommonAnnotations.summary }}'
  
  - name: 'slack-warnings'
    slack_configs:
      - api_url: '<slack-webhook-url>'
        channel: '#alerts'
        severity: 'warning'
```

---

## Dashboards

### CloudWatch Dashboard (Terraform)

```hcl
resource "aws_cloudwatch_dashboard" "api" {
  dashboard_name = "myworld-api-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          title = "API Request Count"
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", aws_lb.main.arn_suffix]
          ]
          period = 60
          stat   = "Sum"
          region = "us-east-1"
        }
      },
      {
        type = "metric"
        properties = {
          title = "API Latency (p50, p95, p99)"
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", aws_lb.main.arn_suffix, { stat = "p50" }],
            ["...", { stat = "p95" }],
            ["...", { stat = "p99" }]
          ]
          period = 60
          region = "us-east-1"
        }
      },
      {
        type = "metric"
        properties = {
          title = "Error Rate (4xx, 5xx)"
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_Target_4XX_Count", "LoadBalancer", aws_lb.main.arn_suffix],
            [".", "HTTPCode_Target_5XX_Count", ".", "."]
          ]
          period = 60
          stat   = "Sum"
          region = "us-east-1"
        }
      },
      {
        type = "metric"
        properties = {
          title = "ECS Resource Utilization"
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ServiceName", "api", "ClusterName", aws_ecs_cluster.main.name],
            [".", "MemoryUtilization", ".", ".", ".", "."]
          ]
          period = 60
          stat   = "Average"
          region = "us-east-1"
        }
      }
    ]
  })
}
```

### Key Dashboard Panels

| Panel | Metric | Threshold |
|-------|--------|-----------|
| **Request Rate** | Requests/sec | N/A |
| **Latency** | p50, p95, p99 | p95 < 500ms |
| **Error Rate** | 4xx, 5xx % | < 1% |
| **Saturation** | CPU, Memory | < 70% |
| **DB Connections** | Active/Idle | < 80% pool |
| **Cache Hit Rate** | Hits / (Hits+Misses) | > 80% |
| **Queue Depth** | SQS messages | < 1000 |

---

## Error Tracking

### Sentry Integration

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration


sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    environment=settings.ENVIRONMENT,
    release=f"myworld-api@{settings.VERSION}",
    traces_sample_rate=0.1,  # 10% of transactions
    profiles_sample_rate=0.1,  # 10% profiling
    integrations=[
        FastApiIntegration(),
        SqlalchemyIntegration(),
        RedisIntegration(),
    ],
    before_send=filter_sensitive_data,
)


def filter_sensitive_data(event, hint):
    """Remove sensitive data before sending to Sentry."""
    # Remove passwords
    if "request" in event and "data" in event["request"]:
        data = event["request"]["data"]
        if isinstance(data, dict):
            for key in ["password", "token", "secret", "api_key"]:
                if key in data:
                    data[key] = "[FILTERED]"
    
    return event
```

### Custom Error Context

```python
from sentry_sdk import capture_exception, set_context


async def create_user(user_in: UserCreate):
    try:
        user = await UserService.create(user_in)
        return user
    except Exception as e:
        # Add context to Sentry error
        with set_context("user_data", {
            "email": user_in.email,
            "full_name": user_in.full_name,
            "signup_source": user_in.source,
        }):
            capture_exception(e)
        raise
```

---

## SLIs, SLOs, and SLAs

### Definitions

- **SLI (Service Level Indicator):** Measurement of service quality (e.g., latency, error rate)
- **SLO (Service Level Objective):** Target value for SLI (e.g., 99.9% availability)
- **SLA (Service Level Agreement):** Contract with consequences for missing SLO

### MyWorld SLOs

| Service | SLI | SLO | Measurement Window |
|---------|-----|-----|-------------------|
| **API** | Successful requests | 99.9% | 30 days |
| **API** | Latency p95 | < 500ms | 30 days |
| **API** | Latency p99 | < 2s | 30 days |
| **Web** | Page load (LCP) p75 | < 2.5s | 7 days |
| **Database** | Query success | 99.99% | 30 days |
| **Worker** | Job completion | 99.5% within 5 min | 7 days |

### Error Budget

```python
# GOOD: Calculate error budget
# SLO: 99.9% availability over 30 days
# Total requests in 30 days: 30 * 24 * 60 * 60 * 1000 RPS = 259,200,000
# Allowed errors: 0.1% = 259,200 errors

slo_availability = 0.999
slo_window_days = 30
total_requests_per_second = 1000

total_requests = slo_window_days * 24 * 60 * 60 * total_requests_per_second
error_budget = total_requests * (1 - slo_availability)

print(f"Error budget: {error_budget:,.0f} errors over {slo_window_days} days")
# Output: Error budget: 259,200 errors over 30 days
```

### SLO Monitoring (Prometheus)

```yaml
# Multi-window multi-burn-rate alert
- alert: SLOErrorBudgetBurn
  expr: |
    (
      sum(rate(http_requests_total{status=~"5.."}[1h]))
      /
      sum(rate(http_requests_total[1h]))
    ) > (14.4 * 0.001)  # 14.4x burn rate for 1h window
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "SLO error budget burning too fast"
    description: "Error rate {{ $value | humanizePercentage }} will exhaust budget in {{ $labels.time_to_exhaustion }}"
```

---

## Best Practices Summary

| ✅ DO | ❌ DON'T |
|---|---|
| Use structured (JSON) logging | Log unstructured text |
| Include request_id in all logs | Log without context |
| Log at appropriate levels | Log everything as INFO |
| Use correlation IDs across services | Lose trace context between services |
| Alert on user-facing symptoms | Alert on internal metrics only |
| Set actionable alerts with runbooks | Send vague "something is wrong" alerts |
| Use RED metrics (Rate, Errors, Duration) | Track only infrastructure metrics |
| Use USE metrics (Utilization, Saturation, Errors) | Ignore resource limits |
| Implement health checks (liveness + readiness) | Use single /health endpoint |
| Sample traces (not 100%) | Trace every request in production |
| Define SLOs with stakeholders | Set SLOs arbitrarily |
| Track error budget burn rate | Wait for budget exhaustion |
| Mask sensitive data in error reports | Log PII or secrets |
| Test observability in staging | Assume it works in production |

---

## References

- [Google SRE Book - Monitoring](https://sre.google/sre-book/monitoring-distributed-systems/)
- [The Three Pillars of Observability](https://www.oreilly.com/library/view/distributed-systems-observability/9781492033431/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Sentry Documentation](https://docs.sentry.io/)
- [RED Method](https://www.weave.works/blog/the-red-method-key-metrics-for-microservices-architecture/)
- [USE Method](http://www.brendangregg.com/usemethod.html)
