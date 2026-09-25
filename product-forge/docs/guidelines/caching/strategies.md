# Caching Engineering Standards

> Multi-level caching strategy for MyWorld Central Portal.

## Table of Contents

1. [Caching Strategy](#caching-strategy)
2. [HTTP Caching](#http-caching)
3. [Application-Level Caching](#application-level-caching)
4. [Distributed Caching (Redis)](#distributed-caching-redis)
5. [Database Query Caching](#database-query-caching)
6. [CDN Caching](#cdn-caching)
7. [Cache Invalidation](#cache-invalidation)
8. [Cache Stampede Prevention](#cache-stampede-prevention)

---

## Caching Strategy

### Cache Hierarchy

```
┌─────────────────────────┐
│  Browser Cache          │  < 1ms  │ Static assets, user data
├─────────────────────────┤
│  CDN (CloudFront)       │  < 50ms │ Static assets, public API responses
├─────────────────────────┤
│  Application Memory     │  < 5ms  │ Session data, hot data
├─────────────────────────┤
│  Redis (Distributed)    │  < 10ms │ Sessions, rate limits, computed data
├─────────────────────────┤
│  Database Query Cache   │  < 50ms │ Query results
├─────────────────────────┤
│  Database (PostgreSQL)  │  < 100ms│ Source of truth
└─────────────────────────┘
```

### When to Cache

✅ **Cache:**
- Expensive computations (reports, aggregations)
- Frequently accessed, rarely changed data (user profiles, product catalog)
- Session data (user sessions, JWT tokens, rate limits)
- API responses (public endpoints)
- Static assets (images, CSS, JS)

❌ **Don't cache:**
- User-specific sensitive data (passwords, PII) - use proper auth instead
- Frequently changing real-time data (live scores, stock prices)
- Large objects (>1MB)
- Data that must always be fresh (compliance-sensitive)

### Cache Key Naming

```python
# GOOD: Hierarchical, namespaced cache keys
cache_key = f"user:{user_id}:profile"
cache_key = f"product:{product_id}:details"
cache_key = f"org:{org_id}:members:page:{page}"
cache_key = f"search:products:q:{query_hash}:page:{page}"

# GOOD: Use colons for hierarchy
# Pattern: <entity>:<id>:<sub_resource>:<modifier>

# BAD: No naming convention
cache_key = str(user_id)  # ❌ No context
cache_key = f"{product_id}_{details}"  # ❌ Inconsistent separator
```

---

## HTTP Caching

### Cache-Control Headers

```python
from fastapi import Response


# GOOD: Public assets, long cache
@router.get("/static/images/{filename}")
async def get_image(filename: str, response: Response):
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return FileResponse(f"static/images/{filename}")


# GOOD: Public API responses, short cache
@router.get("/api/v1/products")
async def list_products(response: Response):
    products = await get_products()
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    return products


# GOOD: Private user data, no cache
@router.get("/api/v1/users/me")
async def get_current_user(response: Response):
    response.headers["Cache-Control"] = "private, no-cache, no-store, must-revalidate"
    return current_user


# GOOD: Conditional responses with ETag
@router.get("/api/v1/products/{product_id}")
async def get_product(product_id: int, response: Response, request: Request):
    product = await get_product_from_db(product_id)
    etag = generate_etag(product)
    
    # Check if client has current version
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "public, max-age=300"
    return product
```

### Cache Directive Reference

| Directive | Purpose |
|-----------|---------|
| `public` | Can be cached by any cache (browser, CDN, proxy) |
| `private` | Only browser cache, not CDN |
| `no-cache` | Must revalidate before using cached version |
| `no-store` | Don't cache at all (sensitive data) |
| `max-age=N` | Cache for N seconds |
| `s-maxage=N` | Cache for N seconds in shared cache (CDN) |
| `must-revalidate` | Must revalidate when stale |
| `immutable` | Never changes, skip revalidation |
| `stale-while-revalidate=N` | Serve stale while revalidating in background |

---

## Application-Level Caching

### In-Memory Cache (LRU)

```python
from functools import lru_cache
import time


# GOOD: Cache expensive function results
@lru_cache(maxsize=128)
def get_popular_products():
    """Cache result in memory, TTL via wrapper."""
    return db.query(Product).order_by(Product.sales.desc()).limit(20).all()


# GOOD: TTL-based cache (manual)
_cache = {}


def cache_with_ttl(ttl_seconds: int):
    """Decorator for time-based caching."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{kwargs}"
            
            if key in _cache:
                value, timestamp = _cache[key]
                if time.time() - timestamp < ttl_seconds:
                    return value
            
            value = func(*args, **kwargs)
            _cache[key] = (value, time.time())
            return value
        return wrapper
    return decorator


@cache_with_ttl(ttl_seconds=300)
def get_user_stats(user_id: int):
    return db.query(User).filter_by(id=user_id).one().stats
```

**Limitation:** In-memory cache is per-process. Use Redis for multi-instance deployments.

---

## Distributed Caching (Redis)

### Redis Client Setup

```python
import redis.asyncio as redis
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from myworld.config import settings


# Create Redis client pool
redis_client: redis.Redis | None = None


async def init_redis():
    global redis_client
    redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
        socket_keepalive=True,
    )
    # Test connection
    await redis_client.ping()


async def close_redis():
    if redis_client:
        await redis_client.close()


@asynccontextmanager
async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    yield redis_client


# FastAPI dependency
async def redis_dep() -> redis.Redis:
    return redis_client
```

### Basic Cache Operations

```python
# GOOD: Get/Set with JSON serialization
import json


async def cache_get(key: str) -> any:
    """Get value from cache."""
    value = await redis_client.get(key)
    if value:
        return json.loads(value)
    return None


async def cache_set(key: str, value: any, ttl: int = 300) -> None:
    """Set value in cache with TTL."""
    await redis_client.setex(
        key,
        ttl,
        json.dumps(value, default=str)
    )


async def cache_delete(key: str) -> None:
    """Delete cache key."""
    await redis_client.delete(key)


# GOOD: Cache decorator
def cache(ttl: int = 300, key_prefix: str = ""):
    """Cache function results in Redis."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_data = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            import hashlib
            key = f"{key_prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"
            
            # Try cache
            cached = await cache_get(key)
            if cached is not None:
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache_set(key, result, ttl)
            
            return result
        return wrapper
    return decorator


# Usage
@router.get("/products/{product_id}")
@cache(ttl=600, key_prefix="product")
async def get_product(product_id: int):
    return await db.get(Product, product_id)
```

### Advanced Redis Patterns

#### Cache-Aside (Lazy Loading)

```python
async def get_user_cache_aside(user_id: int) -> User | None:
    """Cache-aside pattern: Check cache, fall back to DB, populate cache."""
    cache_key = f"user:{user_id}:profile"
    
    # 1. Check cache
    cached = await cache_get(cache_key)
    if cached:
        return User(**cached)
    
    # 2. Cache miss: Fetch from DB
    user = await db.get(User, user_id)
    if not user:
        return None
    
    # 3. Populate cache
    await cache_set(cache_key, user.model_dump(), ttl=600)
    
    return user
```

#### Write-Through

```python
async def update_user_write_through(user_id: int, user_in: UserUpdate) -> User:
    """Write-through: Update DB and cache simultaneously."""
    # 1. Update database
    user = await db.execute(
        update(User).where(User.id == user_id).values(**user_in.model_dump())
    )
    
    # 2. Update cache
    cache_key = f"user:{user_id}:profile"
    await cache_set(cache_key, user.model_dump(), ttl=600)
    
    return user
```

#### Write-Behind (Write-Back)

```python
async def update_user_write_behind(user_id: int, user_in: UserUpdate) -> None:
    """Write-behind: Update cache immediately, DB asynchronously."""
    # 1. Update cache immediately
    cache_key = f"user:{user_id}:profile"
    user_data = await cache_get(cache_key) or {}
    user_data.update(user_in.model_dump())
    await cache_set(cache_key, user_data, ttl=600)
    
    # 2. Queue DB update (async)
    await celery_app.send_task(
        "update_user_db",
        args=[user_id, user_in.model_dump()],
    )
```

#### Read-Through

```python
async def get_user_read_through(user_id: int) -> User | None:
    """Read-through: Cache handles DB lookup."""
    cache_key = f"user:{user_id}:profile"
    
    # Check cache
    cached = await cache_get(cache_key)
    if cached:
        return User(**cached)
    
    # Cache miss: Fetch from DB and populate
    user = await db.get(User, user_id)
    if user:
        await cache_set(cache_key, user.model_dump(), ttl=600)
    
    return user
```

### Cache Tagging and Grouping

```python
# GOOD: Tag-based invalidation
async def cache_set_tagged(key: str, value: any, tags: list[str], ttl: int = 300):
    """Set value with tags for group invalidation."""
    await cache_set(key, value, ttl)
    
    # Store key reference in each tag set
    for tag in tags:
        await redis_client.sadd(f"tag:{tag}", key)
        await redis_client.expire(f"tag:{tag}", ttl)


async def cache_invalidate_tag(tag: str):
    """Invalidate all keys with a specific tag."""
    # Get all keys with this tag
    keys = await redis_client.smembers(f"tag:{tag}")
    
    if keys:
        # Delete all keys
        await redis_client.delete(*keys)
        # Delete the tag set
        await redis_client.delete(f"tag:{tag}")


# Usage
async def get_user_dashboard(user_id: int):
    user = await db.get(User, user_id)
    
    cache_key = f"user:{user_id}:dashboard"
    await cache_set_tagged(
        cache_key,
        {"user": user, "stats": get_stats(user_id)},
        tags=[f"user:{user_id}", "dashboard"],
        ttl=600,
    )
    return cache_get(cache_key)


# Invalidate when user updates
async def update_user(user_id: int, data: dict):
    await db.update_user(user_id, data)
    await cache_invalidate_tag(f"user:{user_id}")
```

---

## Database Query Caching

### Query Result Caching

```python
# GOOD: Cache expensive aggregations
@cache(ttl=300, key_prefix="stats")
async def get_user_stats(user_id: int) -> dict:
    """Cache aggregated stats."""
    return await db.execute(
        select(
            func.count(Post.id).label("post_count"),
            func.sum(Post.views).label("total_views"),
        ).where(Post.author_id == user_id)
    )


# GOOD: Cache with query hash
import hashlib


async def cached_query(query: str, params: dict, ttl: int = 300):
    """Cache raw SQL query results."""
    query_hash = hashlib.md5(f"{query}:{params}".encode()).hexdigest()
    cache_key = f"query:{query_hash}"
    
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    result = await db.execute(text(query), params)
    data = result.fetchall()
    
    await cache_set(cache_key, [dict(row) for row in data], ttl)
    return data
```

---

## CDN Caching

### CloudFront Cache Behaviors

```hcl
# Static assets: Long cache
ordered_cache_behavior {
  path_pattern     = "/_next/static/*"
  target_origin_id = "web"
  viewer_protocol_policy = "redirect-to-https"
  
  forwarded_values {
    query_string = false
    cookies { forward = "none" }
  }
  
  min_ttl     = 31536000  # 1 year
  default_ttl = 31536000
  max_ttl     = 31536000
}

# API responses: Short cache with revalidation
ordered_cache_behavior {
  path_pattern     = "/api/v1/public/*"
  target_origin_id = "api"
  
  forwarded_values {
    query_string = true
    headers      = ["Authorization"]  # Pass auth header
  }
  
  min_ttl     = 0
  default_ttl = 300    # 5 minutes
  max_ttl     = 3600   # 1 hour
}
```

### Cache-Purge on Deploy

```python
# GOOD: Invalidate CDN cache on deployment
import boto3

cloudfront = boto3.client("cloudfront")


def invalidate_cdn_cache(paths: list[str]) -> str:
    """Create CloudFront invalidation."""
    response = cloudfront.create_invalidation(
        DistributionId="E1234567890ABC",
        InvalidationBatch={
            "Paths": {
                "Quantity": len(paths),
                "Items": paths,
            },
            "CallerReference": str(time.time()),
        },
    )
    return response["Invalidation"]["Id"]


# In CI/CD pipeline
invalidate_cdn_cache(["/api/v1/products/*", "/products"])
```

---

## Cache Invalidation

### Invalidation Strategies

| Strategy | Use Case | Trade-off |
|----------|----------|-----------|
| **TTL-based** | Data with predictable freshness needs | May serve stale data |
| **Event-based** | Data tied to specific events | Complex to track events |
| **Tag-based** | Related data invalidated together | Memory overhead |
| **Write-through** | Strong consistency required | Higher write latency |
| **Manual purge** | Critical data updates | Operational burden |

### Event-Based Invalidation

```python
# GOOD: Invalidate on specific events
from myworld.events import event_bus
from myworld.events.user_events import UserUpdatedEvent


@event_bus.on("user.updated")
async def invalidate_user_cache(event: UserUpdatedEvent):
    """Invalidate all user-related cache when user is updated."""
    user_id = event.user_id
    
    # Invalidate specific keys
    await cache_delete(f"user:{user_id}:profile")
    await cache_delete(f"user:{user_id}:stats")
    
    # Invalidate by tag
    await cache_invalidate_tag(f"user:{user_id}")
    
    # Invalidate list queries that include this user
    async for key in redis_client.scan_iter(match=f"users:list:*"):
        await redis_client.delete(key)
```

### Pattern-Based Invalidation

```python
# GOOD: Delete all keys matching a pattern
async def invalidate_pattern(pattern: str):
    """Delete all keys matching pattern (e.g., 'user:123:*')."""
    deleted = 0
    async for key in redis_client.scan_iter(match=pattern, count=100):
        await redis_client.delete(key)
        deleted += 1
    return deleted


# Usage
await invalidate_pattern(f"user:{user_id}:*")
await invalidate_pattern("products:top:*")
```

---

## Cache Stampede Prevention

### What is Cache Stampede?

When a popular cache key expires, multiple concurrent requests hit the database simultaneously, overwhelming it.

### Solution 1: Lock-Based (Mutex)

```python
# GOOD: Lock to prevent stampede
async def get_user_with_lock(user_id: int) -> User:
    """Prevent cache stampede with distributed lock."""
    cache_key = f"user:{user_id}:profile"
    lock_key = f"lock:{cache_key}"
    
    # Try cache first
    cached = await cache_get(cache_key)
    if cached:
        return User(**cached)
    
    # Try to acquire lock
    lock_acquired = await redis_client.set(
        lock_key, "1", nx=True, ex=10  # 10-second lock
    )
    
    if lock_acquired:
        try:
            # We have the lock, fetch from DB
            user = await db.get(User, user_id)
            if user:
                await cache_set(cache_key, user.model_dump(), ttl=600)
            return user
        finally:
            await redis_client.delete(lock_key)
    else:
        # Another request is fetching, wait and retry cache
        await asyncio.sleep(0.1)
        return await get_user_with_lock(user_id)
```

### Solution 2: Probabilistic Early Expiration

```python
# GOOD: Probabilistic early refresh
import random


async def get_with_early_refresh(
    cache_key: str, fetch_func, ttl: int = 300, beta: float = 1.0
):
    """Probabilistically refresh cache before expiration."""
    # Get cached value with timestamp
    cached = await redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        value = data["value"]
        stored_at = data["timestamp"]
        
        # Calculate time since stored
        elapsed = time.time() - stored_at
        
        # Calculate delta (how much longer until expiration)
        delta = ttl - elapsed
        
        # Probabilistic early expiration
        # As delta approaches 0, probability of refresh increases
        if delta > 0 and random.random() < (-delta / beta * math.log(random.random())):
            # Refresh in background
            asyncio.create_task(refresh_cache(cache_key, fetch_func, ttl))
        
        return value
    
    # Cache miss
    value = await fetch_func()
    await cache_set_with_timestamp(cache_key, value, ttl)
    return value


async def cache_set_with_timestamp(key: str, value: any, ttl: int):
    """Cache with timestamp for early expiration calculation."""
    data = {
        "value": value,
        "timestamp": time.time(),
    }
    await redis_client.setex(key, ttl, json.dumps(data, default=str))
```

### Solution 3: Stale-While-Revalidate

```python
# GOOD: Serve stale while revalidating
async def get_with_swr(cache_key: str, fetch_func, ttl: int = 300, stale_ttl: int = 3600):
    """Serve stale data while refreshing in background."""
    cached = await cache_get_with_ttl(cache_key)
    
    if cached:
        value, age = cached
        
        if age < ttl:
            # Fresh
            return value
        
        if age < stale_ttl:
            # Stale but acceptable, refresh in background
            asyncio.create_task(refresh_cache(cache_key, fetch_func, ttl))
            return value
    
    # Cache miss or too stale
    value = await fetch_func()
    await cache_set(cache_key, value, ttl)
    return value
```

---

## Best Practices Summary

| ✅ DO | ❌ DON'T |
|---|---|
| Use hierarchical cache keys | Use random or unstructured keys |
| Set appropriate TTLs | Cache forever without invalidation |
| Use distributed cache (Redis) in multi-instance | Use in-memory only cache |
| Implement cache stampede prevention | Let cache expire without protection |
| Invalidate cache on writes | Rely only on TTL |
| Use ETag for conditional responses | Always send full responses |
| Use CDN for static assets | Serve from origin |
| Use stale-while-revalidate | Block on cache miss for non-critical data |
| Monitor cache hit rate | Cache blindly without metrics |
| Use cache tags for group invalidation | Track individual keys manually |
| Compress large cached values | Cache uncompressed large data |
| Use read-through for simple cases | Manually check cache every time |
| Test cache failure scenarios | Assume cache is always available |

---

## References

- [Redis Documentation](https://redis.io/docs/)
- [HTTP Caching (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching)
- [Cache-Control Header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control)
- [Caching Best Practices](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Expiration.html)
- [Cache Stampede Problem](https://en.wikipedia.org/wiki/Cache_stampede)
- [CloudFront Caching](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cache-content.html)
