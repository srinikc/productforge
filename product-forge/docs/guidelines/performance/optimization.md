# Performance Engineering Standards

> Application performance optimization for MyWorld Central Portal.

## Table of Contents

1. [Performance Budget](#performance-budget)
2. [Backend Performance](#backend-performance)
3. [Database Performance](#database-performance)
4. [Frontend Performance](#frontend-performance)
5. [API Performance](#api-performance)
6. [Profiling and Measurement](#profiling-and-measurement)
7. [Load Testing](#load-testing)

---

## Performance Budget

### Response Time Targets

| Operation | p50 | p95 | p99 |
|-----------|-----|-----|-----|
| API endpoint (simple) | < 50ms | < 200ms | < 500ms |
| API endpoint (complex) | < 200ms | < 500ms | < 2s |
| Database query | < 10ms | < 50ms | < 200ms |
| Static asset load | < 100ms | < 300ms | < 1s |
| Page load (LCP) | < 1s | < 2.5s | < 4s |
| Time to Interactive (TTI) | < 2s | < 3.8s | < 5s |

### Throughput Targets

| Metric | Target |
|--------|--------|
| Requests per second | 5,000 RPS |
| Concurrent users | 50,000 |
| Database connections | 200 max |
| Active WebSocket connections | 10,000 per instance |

---

## Backend Performance

### Async I/O

```python
# GOOD: Async for concurrent operations
import asyncio
import httpx


async def fetch_user_dashboard(user_id: int) -> dict:
    """Fetch dashboard data concurrently."""
    async with httpx.AsyncClient() as client:
        # Run all requests in parallel
        user_task = client.get(f"https://api/users/{user_id}")
        posts_task = client.get(f"https://api/users/{user_id}/posts")
        stats_task = client.get(f"https://api/users/{user_id}/stats")
        
        user_resp, posts_resp, stats_resp = await asyncio.gather(
            user_task, posts_task, stats_task
        )
        
        return {
            "user": user_resp.json(),
            "posts": posts_resp.json(),
            "stats": stats_resp.json(),
        }
```

### Connection Pooling

```python
# GOOD: Reuse HTTP connections
import httpx


# Module-level client (reuses connection pool)
http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(10.0, connect=5.0),
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
    ),
)


# BAD: Creating client per request
async def bad_request(url: str):
    async with httpx.AsyncClient() as client:  # ❌ New client each time
        return await client.get(url)
```

### Database Connection Pool

```python
# GOOD: Properly sized connection pool
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,           # Permanent connections
    max_overflow=10,        # Extra under load (30 total)
    pool_timeout=30,        # Wait up to 30s for connection
    pool_recycle=3600,      # Recycle after 1 hour
    pool_pre_ping=True,     # Verify before use
)


# GOOD: Monitor pool usage
@router.get("/admin/db-pool-stats")
async def db_pool_stats():
    pool = engine.pool
    return {
        "size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "checked_in": pool.checkedin(),
    }
```

### Response Compression

```python
# GOOD: Enable gzip compression in FastAPI
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)  # Compress >1KB responses
```

### Pagination (Avoid Loading Everything)

```python
# GOOD: Cursor-based pagination
async def list_posts(
    cursor: int | None = None,
    limit: int = 20,
) -> dict:
    stmt = select(Post).order_by(Post.id.desc()).limit(limit + 1)
    if cursor:
        stmt = stmt.where(Post.id < cursor)
    
    posts = (await db.execute(stmt)).scalars().all()
    has_more = len(posts) > limit
    posts = posts[:limit]
    
    return {
        "items": posts,
        "next_cursor": posts[-1].id if has_more and posts else None,
    }


# BAD: Loading all records
async def bad_list_posts() -> list[Post]:
    stmt = select(Post)  # ❌ Loads everything
    return (await db.execute(stmt)).scalars().all()
```

---

## Database Performance

### Query Optimization

```sql
-- GOOD: Use indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_posts_author_created ON posts(author_id, created_at DESC);

-- GOOD: Composite index for common queries
CREATE INDEX idx_orders_tenant_status_created 
    ON orders(tenant_id, status, created_at DESC);

-- BAD: Function on indexed column (prevents index use)
SELECT * FROM users WHERE LOWER(email) = 'user@example.com';

-- GOOD: Functional index (PostgreSQL)
CREATE INDEX idx_users_email_lower ON users(LOWER(email));
SELECT * FROM users WHERE LOWER(email) = 'user@example.com';
```

### Query Analysis

```python
# GOOD: Analyze slow queries
EXPLAIN ANALYZE
SELECT u.id, u.email, COUNT(p.id) as post_count
FROM users u
LEFT JOIN posts p ON p.author_id = u.id
WHERE u.created_at > NOW() - INTERVAL '30 days'
GROUP BY u.id
ORDER BY post_count DESC
LIMIT 20;
```

### Avoid N+1 Queries

```python
# BAD: N+1 query problem
async def get_posts_with_authors_bad(db: AsyncSession) -> list[Post]:
    posts = (await db.execute(select(Post))).scalars().all()
    for post in posts:
        post.author = await db.get(User, post.author_id)  # ❌ N queries
    return posts


# GOOD: Eager loading
from sqlalchemy.orm import selectinload


async def get_posts_with_authors_good(db: AsyncSession) -> list[Post]:
    stmt = select(Post).options(
        selectinload(Post.author),  # Single query for all authors
        selectinload(Post.tags),    # Single query for all tags
    )
    return (await db.execute(stmt)).scalars().all()
```

### Batch Operations

```python
# BAD: Individual inserts
async def create_users_bad(db: AsyncSession, users: list[UserCreate]):
    for user_in in users:
        user = User(**user_in.model_dump())
        db.add(user)
        await db.commit()  # ❌ N commits
    return users


# GOOD: Bulk insert
async def create_users_good(db: AsyncSession, users: list[UserCreate]):
    db.add_all([User(**u.model_dump()) for u in users])
    await db.commit()  # Single commit
    return users
```

### Database Read Replicas

```python
# GOOD: Route reads to replica, writes to primary
from sqlalchemy.ext.asyncio import create_async_engine


primary_engine = create_async_engine(PRIMARY_DATABASE_URL)
replica_engine = create_async_engine(REPLICA_DATABASE_URL)


async def get_user(user_id: int):
    # Read from replica
    async with replica_engine.connect() as conn:
        return await conn.get(User, user_id)


async def create_user(user_in: UserCreate):
    # Write to primary
    async with primary_engine.begin() as conn:
        user = User(**user_in.model_dump())
        conn.add(user)
        await conn.commit()
    return user
```

---

## Frontend Performance

### Code Splitting

```typescript
// GOOD: Lazy load heavy components
import dynamic from 'next/dynamic';

const HeavyChart = dynamic(() => import('./HeavyChart'), {
  loading: () => <ChartSkeleton />,
  ssr: false,
});

// GOOD: Route-based code splitting (automatic in Next.js)
// Each page is automatically code-split
```

### Image Optimization

```typescript
// GOOD: Use next/image
import Image from 'next/image';

<Image
  src="/hero.jpg"
  alt="Hero"
  width={1200}
  height={600}
  priority  // Above-the-fold
  placeholder="blur"
  blurDataURL={blurDataUrl}
  quality={75}  // 75% quality is good balance
/>

// GOOD: Responsive images
<Image
  src="/product.jpg"
  alt={product.name}
  fill
  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
  style={{ objectFit: 'cover' }}
/>
```

### React Optimization

```typescript
// GOOD: Memoize expensive calculations
function ProductList({ products, filter }: Props) {
  const filtered = useMemo(
    () => products.filter(p => p.category === filter),
    [products, filter]
  );
  
  return <List items={filtered} />;
}

// GOOD: Stable callbacks
function Parent() {
  const handleClick = useCallback((id: string) => {
    // Handle click
  }, []);
  
  return <Child onClick={handleClick} />;
}

// GOOD: Memo for pure components
const ProductCard = memo(function ProductCard({ product }: Props) {
  return <div>{product.name}</div>;
});
```

### Bundle Size Optimization

```typescript
// GOOD: Import only what you need
import { Button } from '@/components/ui/button';  // Tree-shakeable

// BAD: Import entire library
import * as MaterialUI from '@material-ui/core';  // ❌ Large bundle
```

### Font Optimization

```typescript
// GOOD: Use next/font
import { Inter } from 'next/font/google';

const inter = Inter({ 
  subsets: ['latin'],
  display: 'swap',  // Show fallback font immediately
  variable: '--font-inter',
});
```

---

## API Performance

### Response Caching

```python
# GOOD: Cache expensive queries
from functools import lru_cache
import time


@lru_cache(maxsize=128)
def get_popular_products_cached():
    """Cache for 5 minutes."""
    return get_popular_products()


# Or use Redis (distributed cache)
@cache(ttl=300, key_prefix="products")
async def get_product(product_id: int):
    return await db.get(Product, product_id)
```

### HTTP Caching Headers

```python
from fastapi import Response


@router.get("/products/{product_id}")
async def get_product(product_id: int, response: Response):
    product = await db.get(Product, product_id)
    
    # Cache for 5 minutes, allow stale for 1 hour
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=3600"
    response.headers["ETag"] = generate_etag(product)
    
    return product
```

### Batch Endpoints

```python
# GOOD: Batch endpoint to reduce round trips
@router.post("/users/batch")
async def get_users_batch(user_ids: list[int]) -> dict[int, User]:
    """Fetch multiple users in one request."""
    stmt = select(User).where(User.id.in_(user_ids))
    users = (await db.execute(stmt)).scalars().all()
    return {u.id: u for u in users}


# Client usage
const users = await api.post('/users/batch', {
  user_ids: [1, 2, 3, 4, 5]
});
```

### GraphQL-style Field Selection (REST)

```python
# GOOD: Allow clients to specify fields
@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    fields: str = Query("id,email,full_name", description="Comma-separated fields"),
):
    user = await db.get(User, user_id)
    
    selected_fields = fields.split(",")
    return {field: getattr(user, field) for field in selected_fields if hasattr(user, field)}
```

---

## Profiling and Measurement

### Application Profiling (Python)

```python
# GOOD: Profile slow endpoints
import cProfile
import pstats
import io


def profile_endpoint(func):
    """Decorator to profile endpoint execution."""
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        
        result = func(*args, **kwargs)
        
        profiler.disable()
        
        # Print top 20 time-consuming functions
        stats = pstats.Stats(profiler)
        stats.sort_stats("cumulative")
        stats.print_stats(20)
        
        return result
    return wrapper


# Or use py-spy for production profiling
# py-spy dump --pid 12345
# py-spy record -o profile.svg --pid 12345 --duration 30
```

### Performance Monitoring (APM)

```python
# GOOD: Use OpenTelemetry for distributed tracing
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# Initialize tracing
tracer = trace.get_tracer(__name__)

# Instrument frameworks
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine)
RedisInstrumentor().instrument()
HTTPXClientInstrumentor().instrument()


# Add custom spans
@router.get("/users/{user_id}")
async def get_user(user_id: int):
    with tracer.start_as_current_span("get_user") as span:
        span.set_attribute("user.id", user_id)
        
        user = await db.get(User, user_id)
        
        span.set_attribute("user.found", user is not None)
        return user
```

### Database Query Monitoring

```python
# GOOD: Log slow queries
import time
from sqlalchemy import event


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - context._query_start_time
    
    if total > 0.1:  # Log queries >100ms
        logger.warning(
            f"Slow query: {total*1000:.0f}ms",
            extra={
                "query": statement[:200],
                "duration_ms": total * 1000,
            }
        )
```

---

## Load Testing

### Locust (Python)

```python
# locustfile.py
from locust import HttpUser, task, between


class MyWorldUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login and get auth token."""
        response = self.client.post("/api/v1/auth/login", json={
            "email": "loadtest@example.com",
            "password": "loadtest123",
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def list_products(self):
        self.client.get("/api/v1/products", headers=self.headers)
    
    @task(2)
    def get_product(self):
        product_id = random.randint(1, 1000)
        self.client.get(f"/api/v1/products/{product_id}", headers=self.headers)
    
    @task(1)
    def create_order(self):
        self.client.post(
            "/api/v1/orders",
            json={
                "product_id": random.randint(1, 1000),
                "quantity": random.randint(1, 5),
            },
            headers=self.headers,
        )
```

```bash
# Run load test
locust -f locustfile.py --host=https://api-staging.myworld.com --users 1000 --spawn-rate 50 --run-time 5m
```

### k6 (JavaScript)

```javascript
// load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 100 },   // Ramp up
    { duration: '3m', target: 1000 },  // Stay at 1000 users
    { duration: '1m', target: 0 },     // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% under 500ms
    http_req_failed: ['rate<0.01'],    // Error rate <1%
  },
};

export default function () {
  const res = http.get('https://api-staging.myworld.com/products');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
  sleep(1);
}
```

```bash
# Run k6 test
k6 run --out json=results.json load-test.js
```

---

## Best Practices Summary

| ✅ DO | ❌ DON'T |
|---|---|
| Measure first, optimize second | Optimize without profiling |
| Use async I/O for concurrent ops | Sequential awaits |
| Use connection pooling | Create new connections per request |
| Add database indexes for queries | Full table scans |
| Use eager loading (selectinload) | N+1 queries |
| Paginate large result sets | Load all records |
| Enable response compression (gzip) | Send uncompressed responses |
| Use CDN for static assets | Serve from origin |
| Lazy load heavy components | Bundle everything |
| Use next/image for images | Raw <img> tags |
| Cache expensive computations | Recalculate every time |
| Profile in production (low overhead) | Profile only in dev |
| Run load tests before launch | Hope it scales |
| Use APM (OpenTelemetry, DataDog) | Debug from logs alone |

---

## References

- [Web Vitals](https://web.dev/vitals/)
- [PostgreSQL Performance Tuning](https://www.postgresql.org/docs/current/performance-tips.html)
- [SQLAlchemy Performance](https://docs.sqlalchemy.org/en/20/faq/performance.html)
- [FastAPI Performance](https://fastapi.tiangolo.com/deployment/concepts/)
- [React Performance Optimization](https://react.dev/learn/render-and-commit)
- [OpenTelemetry](https://opentelemetry.io/)
- [k6 Load Testing](https://k6.io/docs/)
- [Locust Load Testing](https://locust.io/)
