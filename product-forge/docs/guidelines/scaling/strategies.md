# Scaling Engineering Standards

> Horizontal and vertical scaling strategies for MyWorld Central Portal.

## Table of Contents

1. [Scaling Principles](#scaling-principles)
2. [Horizontal Scaling](#horizontal-scaling)
3. [Vertical Scaling](#vertical-scaling)
4. [Database Scaling](#database-scaling)
5. [Caching for Scale](#caching-for-scale)
6. [Load Balancing](#load-balancing)
7. [Auto Scaling Strategies](#auto-scaling-strategies)
8. [Capacity Planning](#capacity-planning)
9. [Statelessness](#statelessness)

---

## Scaling Principles

### The Scale Cube (X, Y, Z)

```
X-axis: Horizontal duplication (run multiple instances)
Y-axis: Functional decomposition (split by service/function)
Z-axis: Data partitioning (shard by user/tenant)
```

**MyWorld Strategy:**
1. **Start with X-axis** (horizontal scaling) — easiest, most cost-effective
2. **Add Y-axis** (split services) when codebases grow
3. **Add Z-axis** (sharding) only when data volume demands it

### When to Scale

✅ **Scale up/out when:**
- CPU consistently > 70%
- Memory consistently > 80%
- Latency p95 > SLO
- Queue depth growing
- Request rate increasing

❌ **Don't scale when:**
- Spikes are short (< 5 minutes)
- Caused by inefficient code (optimize first)
- Cost outweighs benefit

---

## Horizontal Scaling

### Stateless Application Servers

```python
# GOOD: Stateless API server (no in-memory state)
# All state in external services (Redis, database)

@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),  # External
    cache: redis.Redis = Depends(redis_dep),  # External
):
    # No local state, can run on any instance
    return await get_user_cache_aside(user_id, db, cache)


# BAD: In-memory state (can't scale horizontally)
user_sessions = {}  # ❌ Each instance has different sessions

@router.post("/login")
async def login(credentials: LoginCreate):
    session_id = create_session()
    user_sessions[session_id] = user  # ❌ Only on this instance
    return {"session_id": session_id}
```

### Sticky Sessions (When Needed)

```python
# Use sticky sessions ONLY for WebSocket connections
# For regular HTTP, use stateless JWT

# GOOD: WebSocket with sticky session
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        msg = await websocket.receive_text()
        await websocket.send_text(f"Echo: {msg}")


# Alternative: Use Redis pub/sub for WebSocket
# Allows any instance to handle any WebSocket
```

### Horizontal Pod Autoscaler (HPA)

```yaml
# k8s/api-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  
  minReplicas: 3
  maxReplicas: 50
  
  metrics:
    # CPU-based scaling
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    
    # Memory-based scaling
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
    
    # Request rate-based scaling
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "1000"
  
  behavior:
    # Scale up quickly
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Percent
          value: 100
          periodSeconds: 30
        - type: Pods
          value: 4
          periodSeconds: 30
      selectPolicy: Max
    
    # Scale down slowly (avoid flapping)
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 50
          periodSeconds: 60
```

---

## Vertical Scaling

### When to Scale Vertically

✅ **Vertical scaling is good for:**
- Databases (before sharding)
- Stateful services
- Single-threaded workloads
- Short-term capacity boost

❌ **Vertical scaling limits:**
- Hardware limits (largest instance type)
- Cost grows non-linearly
- Requires downtime (usually)

### Vertical Pod Autoscaler (VPA)

```yaml
# k8s/api-vpa.yaml
apiVersion: autoscaling/v1
kind: VerticalPodAutoscaler
metadata:
  name: api
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  
  updatePolicy:
    updateMode: "Auto"  # or "Initial" or "Off"
  
  resourcePolicy:
    containerPolicies:
      - containerName: api
        minAllowed:
          cpu: "100m"
          memory: "256Mi"
        maxAllowed:
          cpu: "2000m"
          memory: "4Gi"
        controlledResources: ["cpu", "memory"]
```

---

## Database Scaling

### Read Replicas

```python
# GOOD: Route reads to replicas, writes to primary
from sqlalchemy.ext.asyncio import create_async_engine


# Primary (writes)
primary_engine = create_async_engine(
    settings.DATABASE_PRIMARY_URL,
    pool_size=20,
    max_overflow=10,
)

# Replica (reads)
replica_engine = create_async_engine(
    settings.DATABASE_REPLICA_URL,
    pool_size=30,
    max_overflow=20,
)


# Write operation
async def create_user(user_in: UserCreate) -> User:
    async with primary_engine.begin() as conn:
        user = User(**user_in.model_dump())
        conn.add(user)
        await conn.commit()
    return user


# Read operation
async def get_user(user_id: int) -> User | None:
    async with replica_engine.connect() as conn:
        return await conn.get(User, user_id)
```

### Connection Pooling (PgBouncer)

```ini
# pgbouncer.ini
[databases]
myworld = host=primary-db.internal port=5432 dbname=myworld
myworld_ro = host=replica-db.internal port=5432 dbname=myworld

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

# Pool mode
pool_mode = transaction
max_client_conn = 10000
default_pool_size = 25
min_pool_size = 5
reserve_pool_size = 5
reserve_pool_timeout = 3

# Timeouts
server_idle_timeout = 600
server_connect_timeout = 15
server_login_retry = 3
query_timeout = 300
query_wait_timeout = 120

# Logging
log_connections = 1
log_disconnections = 1
log_pooler_errors = 1
```

### Sharding Strategy (When Needed)

```python
# Shard by tenant_id (hash-based)
# Shard 0: tenant_id % 4 == 0
# Shard 1: tenant_id % 4 == 1
# Shard 2: tenant_id % 4 == 2
# Shard 3: tenant_id % 4 == 3


class ShardRouter:
    def __init__(self, num_shards: int):
        self.num_shards = num_shards
        self.engines = [
            create_async_engine(f"postgresql+asyncpg://shard{i}.internal/myworld")
            for i in range(num_shards)
        ]
    
    def get_shard_for_tenant(self, tenant_id: int) -> int:
        return tenant_id % self.num_shards
    
    def get_engine(self, tenant_id: int):
        shard_id = self.get_shard_for_tenant(tenant_id)
        return self.engines[shard_id]
    
    async def get_user(self, user_id: int, tenant_id: int):
        engine = self.get_engine(tenant_id)
        async with engine.connect() as conn:
            return await conn.get(User, user_id)


# Cross-shard queries (expensive, avoid)
async def get_all_users_across_shards(self):
    # Query all shards in parallel
    tasks = [
        engine.connect().__aenter__().get(User, user_id)
        for user_id in user_ids
    ]
    results = await asyncio.gather(*tasks)
    return results
```

### Partitioning (PostgreSQL)

```sql
-- Partition large tables by date or tenant
CREATE TABLE events (
    id BIGSERIAL,
    tenant_id BIGINT NOT NULL,
    event_type VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL,
    data JSONB
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE events_2026_08 PARTITION OF events
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

CREATE TABLE events_2026_09 PARTITION OF events
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');

-- Automatic partition creation
CREATE OR REPLACE FUNCTION create_monthly_partition()
RETURNS void AS $$
DECLARE
    start_date DATE := date_trunc('month', CURRENT_DATE);
    end_date DATE := start_date + INTERVAL '1 month';
    partition_name TEXT := 'events_' || to_char(start_date, 'YYYY_MM');
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF events FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );
END;
$$ LANGUAGE plpgsql;
```

---

## Caching for Scale

### Multi-Level Cache

```python
# Level 1: In-memory (per-instance, microseconds)
@lru_cache(maxsize=1000)
def get_static_config() -> dict:
    """Cache static config in memory."""
    return load_static_config()


# Level 2: Redis (distributed, milliseconds)
async def get_user_profile(user_id: int) -> UserProfile:
    """Cache user profiles in Redis."""
    cache_key = f"user:{user_id}:profile"
    
    # Try Redis
    cached = await redis_client.get(cache_key)
    if cached:
        return UserProfile(**json.loads(cached))
    
    # Cache miss: Load from DB
    profile = await load_from_db(user_id)
    
    # Store in Redis (1 hour TTL)
    await redis_client.setex(
        cache_key,
        3600,
        profile.model_dump_json(),
    )
    
    return profile


# Level 3: CDN (edge cache, seconds)
# Static assets cached at CloudFront edge locations
```

### Cache Warming

```python
# GOOD: Pre-populate cache on deployment
async def warm_cache():
    """Warm cache with popular data on startup."""
    popular_products = await get_popular_products(limit=100)
    
    for product in popular_products:
        await cache_set(
            f"product:{product.id}",
            product.model_dump(),
            ttl=3600,
        )
    
    logger.info(f"Warmed cache with {len(popular_products)} products")


# Run on application startup
@app.on_event("startup")
async def startup():
    await warm_cache()
```

---

## Load Balancing

### Application Load Balancer (ALB)

```hcl
# Already covered in cloud/aws.md
# Key: Use round-robin or least-outstanding-requests algorithm

resource "aws_lb_target_group" "api" {
  # ... config
  
  # Health check
  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }
  
  # Deregistration delay (allow in-flight requests to complete)
  deregistration_delay = 30
  
  # Slow start (gradually send traffic to new instances)
  slow_start = 60
}
```

### Sticky Sessions (WebSocket Only)

```hcl
# Only for WebSocket connections
resource "aws_lb_target_group" "websocket" {
  # ...
  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400
    enabled         = true
  }
}
```

### Rate Limiting at Load Balancer

```hcl
# AWS WAF rate limiting
resource "aws_wafv2_web_acl" "main" {
  name  = "myworld-waf"
  scope = "REGIONAL"
  
  default_action {
    allow {}
  }
  
  rule {
    name     = "RateLimitPerIP"
    priority = 1
    
    action {
      block {}
    }
    
    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimitPerIP"
      sampled_requests_enabled   = true
    }
  }
}
```

---

## Auto Scaling Strategies

### Predictive Scaling (ML-Based)

```hcl
# AWS Auto Scaling with predictive scaling
resource "aws_autoscaling_group" "api" {
  name                = "myworld-api"
  min_size            = 3
  max_size            = 50
  desired_capacity    = 3
  
  # Predictive scaling
  mixed_instances_policy {
    instances_distribution {
      on_demand_base_capacity = 2
      on_demand_percentage_above_base_capacity = 30
      spot_allocation_strategy = "diversified"
    }
    
    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.api.id
        version            = "$Latest"
      }
      
      override {
        instance_type = "m6i.xlarge"
      }
      override {
        instance_type = "m5.xlarge"
      }
    }
  }
}
```

### Scheduled Scaling (Predictable Patterns)

```python
# Scale up for known peak hours
# Monday-Friday 8 AM: scale to 10 instances
# Monday-Friday 8 PM: scale down to 3 instances
# Weekends: keep at 2 instances


# Using Celery beat for scheduled scaling
@celery_app.task
def scale_up_for_business_hours():
    """Scale up at 8 AM weekdays."""
    asg.set_desired_capacity(10)


@celery_app.task
def scale_down_for_night():
    """Scale down at 8 PM weekdays."""
    asg.set_desired_capacity(3)
```

### Reactive Scaling (Metrics-Based)

```python
# GOOD: Scale based on multiple signals
# CPU + Memory + Request rate + Queue depth

def calculate_desired_instances(
    current_instances: int,
    cpu_utilization: float,
    memory_utilization: float,
    request_rate: float,
    queue_depth: int,
) -> int:
    """Calculate desired instance count."""
    
    # Target metrics
    TARGET_CPU = 70
    TARGET_MEMORY = 80
    TARGET_RPS_PER_INSTANCE = 1000
    MAX_QUEUE_DEPTH = 100
    
    # Calculate based on each signal
    cpu_needed = math.ceil(current_instances * cpu_utilization / TARGET_CPU)
    mem_needed = math.ceil(current_instances * memory_utilization / TARGET_MEMORY)
    rps_needed = math.ceil(request_rate / TARGET_RPS_PER_INSTANCE)
    queue_needed = math.ceil(queue_depth / MAX_QUEUE_DEPTH) * current_instances
    
    # Take the maximum
    desired = max(cpu_needed, mem_needed, rps_needed, queue_needed)
    
    # Clamp to min/max
    desired = max(2, min(50, desired))
    
    return desired
```

---

## Capacity Planning

### Load Testing Methodology

```python
# 1. Baseline test (current capacity)
locust -f load_test.py --users 1000 --spawn-rate 10 --run-time 30m

# 2. Stress test (find breaking point)
locust -f load_test.py --users 10000 --spawn-rate 100 --run-time 1h

# 3. Soak test (sustained load)
locust -f load_test.py --users 2000 --spawn-rate 10 --run-time 24h

# 4. Spike test (sudden traffic spike)
locust -f load_test.py --users 100 --spawn-rate 5 --run-time 5m
# Then: --users 5000 --spawn-rate 1000 --run-time 5m
```

### Capacity Calculation

```python
# Calculate required capacity
def calculate_capacity(
    target_rps: int,
    avg_response_time_ms: int,
    max_response_time_ms: int = 1000,
) -> dict:
    """Calculate required instances and database connections."""
    
    # Each instance can handle ~1000 RPS at 100ms avg response time
    # Use Little's Law: concurrent_requests = rps * avg_response_time_seconds
    
    avg_response_time_s = avg_response_time_ms / 1000
    concurrent_requests_per_instance = 1000 * avg_response_time_s  # ~100 concurrent
    
    instances_needed = math.ceil(target_rps / 1000)
    
    # Database connections (20 per instance + 10 overflow = 30 per instance)
    db_pool_size = instances_needed * 30
    
    # Memory per instance (1 GB base + 100 MB per 100 concurrent requests)
    memory_per_instance_gb = 1 + (concurrent_requests_per_instance / 100) * 0.1
    
    # CPU cores (2 base + 1 per 500 RPS)
    cpu_cores_per_instance = 2 + (target_rps / instances_needed / 500)
    
    return {
        "instances": instances_needed,
        "db_connections": db_pool_size,
        "memory_gb_per_instance": memory_per_instance_gb,
        "cpu_cores_per_instance": math.ceil(cpu_cores_per_instance),
    }


# Example: 5000 RPS target
result = calculate_capacity(target_rps=5000, avg_response_time_ms=200)
# {
#   "instances": 5,
#   "db_connections": 150,
#   "memory_gb_per_instance": 2.0,
#   "cpu_cores_per_instance": 3
# }
```

---

## Statelessness

### Externalize All State

```python
# ✅ GOOD: Stateless
- Sessions: Redis
- File uploads: S3
- Cache: Redis
- Database: RDS
- Search: Elasticsearch
- Queue: SQS


# ❌ BAD: Stateful (can't scale horizontally)
- Sessions: In-memory dict
- File uploads: Local disk
- Cache: In-memory dict
- Temporary files: /tmp
```

### Health Checks for Load Balancer

```python
@router.get("/health/live")
async def liveness():
    """Is the process alive?"""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(redis_dep),
):
    """Can the process handle requests?"""
    # Check all dependencies
    try:
        await db.execute("SELECT 1")
        await redis.ping()
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(e)}
        )
    
    return {"status": "ready"}


@router.get("/health/startup")
async def startup_check():
    """Has the process finished initializing?"""
    if not app_state.is_initialized:
        return JSONResponse(
            status_code=503,
            content={"status": "starting"}
        )
    return {"status": "started"}
```

### Graceful Shutdown

```python
import signal
import asyncio


class GracefulShutdown:
    def __init__(self):
        self.shutdown_event = asyncio.Event()
    
    def handle_signal(self, signum, frame):
        logger.info(f"Received signal {signum}, starting graceful shutdown")
        self.shutdown_event.set()


shutdown_handler = GracefulShutdown()
signal.signal(signal.SIGTERM, shutdown_handler.handle_signal)
signal.signal(signal.SIGINT, shutdown_handler.handle_signal)


# In FastAPI app
@app.on_event("shutdown")
async def shutdown():
    """Gracefully shutdown the application."""
    logger.info("Stopping accepting new requests")
    
    # Stop accepting new work
    # (Load balancer should have already removed us from rotation)
    
    # Wait for in-flight requests to complete (max 30s)
    try:
        await asyncio.wait_for(
            shutdown_handler.shutdown_event.wait(),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        logger.warning("Shutdown timeout, forcing exit")
    
    # Close connections
    await close_db()
    await close_redis()
    
    logger.info("Shutdown complete")
```

---

## Best Practices Summary

| ✅ DO | ❌ DON'T |
|---|---|
| Build stateless services | Store state in memory |
| Use horizontal scaling | Scale vertically indefinitely |
| Add read replicas for read-heavy workloads | Overload primary database |
| Implement auto-scaling | Use fixed instance count |
| Use connection pooling (PgBouncer) | Open DB connection per request |
| Cache aggressively at multiple levels | Hit database for every request |
| Shard only when necessary | Premature optimization |
| Implement graceful shutdown | Kill processes abruptly |
| Use health checks | Skip health monitoring |
| Load test before launch | Hope it scales |
| Plan capacity based on data | Guess at instance counts |
| Use predictive scaling for known patterns | Only reactive scaling |
| Partition large tables | Keep billion-row tables |
| Use spot instances for non-critical | Always use on-demand |

---

## References

- [Scalability Rules (Martin Abbott)](https://www.scalabilityrules.com/)
- [Designing Data-Intensive Applications (Martin Kleppmann)](https://dataintensive.net/)
- [AWS Auto Scaling](https://aws.amazon.com/autoscaling/)
- [Kubernetes HPA](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [PostgreSQL Performance Scaling](https://www.postgresql.org/docs/current/high-availability.html)
- [Little's Law](https://en.wikipedia.org/wiki/Little%27s_law)
- [The Scale Cube](https://microservices.io/articles/scalecube.html)
