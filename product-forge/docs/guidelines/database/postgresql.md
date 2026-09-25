# Database Design Standards (PostgreSQL)

> **Scope:** All PostgreSQL databases in Product Forge
> **Source:** PostgreSQL Official Docs + Use The Index, Luke + Microsoft Database Design Best Practices
> **Version:** 1.0 | **Date:** 2026-08-24

---

## 1. Naming Conventions

### 1.1 Tables
- **Plural, snake_case:** `users`, `todo_items`, `user_sessions`
- **No prefixes** (avoid `tbl_users`, `t_users`)
- **Descriptive names:** `user_payment_methods` not `payments`

### 1.2 Columns
- **snake_case:** `user_id`, `created_at`, `is_active`
- **Boolean prefix:** `is_`, `has_`, `should_` (e.g., `is_active`, `has_children`)
- **Timestamp suffix:** `_at` for timestamps, `_date` for dates
- **No abbreviations:** `description` not `desc`, `identifier` not `id`

### 1.3 Constraints
- **Primary key:** `pk_{table}` (e.g., `pk_users`)
- **Foreign key:** `fk_{table}_{referenced_table}` (e.g., `fk_todos_users`)
- **Unique:** `uq_{table}_{column}` (e.g., `uq_users_email`)
- **Check:** `ck_{table}_{description}` (e.g., `ck_users_age_positive`)
- **Index:** `idx_{table}_{column}` (e.g., `idx_todos_user_id`)

### 1.4 Examples
```sql
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(100) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TIMESTAMPTZ,
    
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$')
);

CREATE TABLE todo_items (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL,
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    due_date        TIMESTAMPTZ,
    is_completed    BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_todos_users FOREIGN KEY (user_id) 
        REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT ck_todos_title_not_empty CHECK (LENGTH(TRIM(title)) > 0)
);

CREATE INDEX idx_todos_user_id ON todo_items (user_id);
CREATE INDEX idx_todos_completed ON todo_items (is_completed) WHERE is_completed = FALSE;
CREATE INDEX idx_todos_created_at ON todo_items (created_at DESC);
```

---

## 2. Primary Keys

### 2.1 Choose Strategy
- **Auto-increment (BIGSERIAL):** Simple, sequential, smaller indexes
  - Use for: Internal tables, high-volume inserts, time-series
- **UUID v4 (gen_random_uuid()):** Distributed systems, security, merging
  - Use for: User-facing IDs, public APIs, multi-tenant

### 2.2 When to Use UUID
- Public APIs (don't expose sequential IDs)
- Multi-region databases
- Merge/replication scenarios
- Security (prevent enumeration attacks)

### 2.3 When to Use BIGSERIAL
- Internal/joins-only IDs
- Performance-critical paths
- Single-region databases
- Smaller index size matters

### 2.4 Recommendation
```sql
-- Public-facing entities: UUID
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ...
);

-- Internal/junction tables: BIGSERIAL
CREATE TABLE user_roles (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    role_id BIGINT NOT NULL REFERENCES roles(id),
    ...
);
```

---

## 3. Foreign Keys

### 3.1 Always Define
- Every relationship MUST have a foreign key
- Enforces referential integrity
- Helps query planner

### 3.2 Cascade Strategy
```sql
-- ON DELETE CASCADE: Delete children when parent deleted
-- Example: Delete user → delete their todos
ALTER TABLE todo_items 
    ADD CONSTRAINT fk_todos_users 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- ON DELETE SET NULL: Keep children, nullify FK
-- Example: Delete category → keep products, set category_id NULL
ALTER TABLE products 
    ADD CONSTRAINT fk_products_categories 
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL;

-- ON DELETE RESTRICT: Prevent deletion if children exist (default)
-- Example: Can't delete user with active subscriptions
ALTER TABLE subscriptions 
    ADD CONSTRAINT fk_subscriptions_users 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT;
```

### 3.3 Index Foreign Keys
```sql
-- Foreign keys should be indexed for JOIN performance
CREATE INDEX idx_todos_user_id ON todo_items (user_id);
```

---

## 4. Timestamps & Audit

### 4.1 Standard Timestamps
Every table MUST have:
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`

Optional:
- `deleted_at TIMESTAMPTZ` (for soft delete)
- `created_by UUID REFERENCES users(id)` (who created)
- `updated_by UUID REFERENCES users(id)` (who updated)

### 4.2 Auto-Update Trigger
```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### 4.3 Soft Delete Pattern
```sql
-- Add deleted_at column
ALTER TABLE users ADD COLUMN deleted_at TIMESTAMPTZ;

-- Query only non-deleted
SELECT * FROM users WHERE deleted_at IS NULL;

-- Create partial index for performance
CREATE INDEX idx_users_active ON users (id) WHERE deleted_at IS NULL;
```

---

## 5. Indexes

### 5.1 When to Create Index
- Foreign keys (for JOINs)
- WHERE clause columns (frequent filters)
- ORDER BY columns (for sorting)
- Unique constraints

### 5.2 When NOT to Index
- Small tables (< 1000 rows)
- Columns with low cardinality (e.g., boolean with 50/50 split)
- Frequently updated columns
- Wide columns (TEXT, JSONB unless using GIN)

### 5.3 Index Types

**B-Tree (Default):** Equality and range queries
```sql
CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_todos_created_at ON todo_items (created_at DESC);
```

**Partial Index:** Filtered subset
```sql
-- Index only active users
CREATE INDEX idx_users_active ON users (id) WHERE is_active = TRUE;

-- Index only incomplete todos
CREATE INDEX idx_todos_pending ON todo_items (user_id) WHERE is_completed = FALSE;
```

**Composite Index:** Multi-column
```sql
-- Order matters! Most selective first
CREATE INDEX idx_todos_user_status ON todo_items (user_id, is_completed);

-- Good for: WHERE user_id = X AND is_completed = Y
-- Good for: WHERE user_id = X (uses first column)
-- NOT good for: WHERE is_completed = Y (skips first column)
```

**GIN Index:** Full-text search, JSONB, arrays
```sql
-- Full-text search
CREATE INDEX idx_todos_search ON todo_items 
    USING GIN (to_tsvector('english', title || ' ' || description));

-- JSONB
CREATE INDEX idx_users_metadata ON users USING GIN (metadata);

-- Arrays
CREATE INDEX idx_todos_tags ON todo_items USING GIN (tags);
```

**BRIN Index:** Large tables with natural ordering
```sql
-- Time-series data
CREATE INDEX idx_events_time ON events USING BRIN (created_at);
```

### 5.4 EXPLAIN ANALYZE
Always verify index usage:
```sql
EXPLAIN ANALYZE
SELECT * FROM todo_items WHERE user_id = 123 AND is_completed = FALSE;
```

Look for:
- `Index Scan` (good)
- `Seq Scan` on large tables (bad, needs index)
- `Bitmap Index Scan` (acceptable)

---

## 6. Data Types

### 6.1 Choose Right Type
```sql
-- IDs
id BIGSERIAL          -- Auto-increment
id UUID                -- UUID

-- Strings
name VARCHAR(100)      -- Limited length
description TEXT       -- Unlimited
email VARCHAR(255)     -- Standard email length

-- Numbers
age SMALLINT           -- -32K to 32K (use INT or BIGINT for IDs)
price DECIMAL(10, 2)   -- Money (never use FLOAT for money!)
quantity INT           -- Counts
ratio DOUBLE PRECISION -- Scientific

-- Dates/Time
created_at TIMESTAMPTZ  -- Always with timezone!
birth_date DATE         -- Just date
duration INTERVAL       -- Time span

-- Boolean
is_active BOOLEAN       -- NOT is_active INTEGER

-- JSON
metadata JSONB          -- Indexed, queryable (use JSONB not JSON)

-- Arrays
tags TEXT[]             -- Array of text
```

### 6.2 Money
- **Never** use `FLOAT` or `DOUBLE PRECISION` for money
- Use `DECIMAL(precision, scale)` or `NUMERIC`
- Or store as integer cents

```sql
-- Good
price DECIMAL(10, 2) NOT NULL  -- $9,999,999.99 max

-- Or integer cents
price_cents BIGINT NOT NULL
```

### 6.3 Timestamps
- **Always** use `TIMESTAMPTZ` (timestamp with time zone), not `TIMESTAMP`
- Stores in UTC internally
- Handles daylight saving correctly

```sql
created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
```

### 6.4 JSON vs JSONB
- Use `JSONB` (binary, indexed, faster)
- Use `JSON` only for exact preservation

```sql
metadata JSONB NOT NULL DEFAULT '{}'::JSONB
```

---

## 7. Row-Level Security (RLS)

### 7.1 Enable RLS for User-Scoped Data
```sql
-- Enable RLS
ALTER TABLE todo_items ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own todos
CREATE POLICY todos_user_isolation ON todo_items
    USING (user_id = current_setting('app.current_user_id')::BIGINT);

-- Policy: Users can only modify their own todos
CREATE POLICY todos_user_modify ON todo_items
    FOR ALL
    USING (user_id = current_setting('app.current_user_id')::BIGINT);
```

### 7.2 Multi-Tenant Isolation
```sql
-- Tenant isolation
CREATE POLICY tenant_isolation ON todo_items
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

### 7.3 Service Role Bypass
```sql
-- Service accounts can bypass RLS
CREATE POLICY service_role_bypass ON todo_items
    FOR ALL
    TO service_role
    USING (TRUE) WITH CHECK (TRUE);
```

---

## 8. Migrations

### 8.1 Use Alembic (Python)
```python
# alembic/versions/001_create_users.py
def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_users_email', 'users', ['email'])

def downgrade():
    op.drop_index('idx_users_email')
    op.drop_table('users')
```

### 8.2 Migration Rules
- **One change per migration** (easier to review/rollback)
- **Forward-only** (avoid complex data migrations in downgrades)
- **Test before commit** (run up + down)
- **No breaking changes** (add columns nullable, then migrate data, then add NOT NULL)

### 8.3 Zero-Downtime Migrations
```sql
-- Step 1: Add new column nullable
ALTER TABLE users ADD COLUMN full_name_new VARCHAR(100);

-- Step 2: Backfill data
UPDATE users SET full_name_new = full_name WHERE full_name_new IS NULL;

-- Step 3: Add NOT NULL constraint
ALTER TABLE users ALTER COLUMN full_name_new SET NOT NULL;

-- Step 4: Deploy code that uses new column
-- (after deployment, remove old column in later migration)
```

---

## 9. Performance

### 9.1 Avoid SELECT *
```sql
-- Bad
SELECT * FROM users;

-- Good
SELECT id, email, name FROM users;
```

### 9.2 Use EXPLAIN ANALYZE
```sql
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM todo_items WHERE user_id = 123;
```

### 9.3 N+1 Query Prevention
```python
# Bad
todos = db.execute(select(Todo))
for todo in todos:
    user = db.execute(select(User).where(User.id == todo.user_id))

# Good
todos = db.execute(
    select(Todo).options(selectinload(Todo.user))
)
```

### 9.4 Connection Pooling
- Use PgBouncer or pgbouncer-equivalent
- Pool size: 2-4 × CPU cores
- Statement timeout: 30s default

### 9.5 Vacuum & Analyze
```sql
-- Auto-vacuum should handle this, but monitor
VACUUM ANALYZE todo_items;
```

---

## 10. Backup & Recovery

### 10.1 Backup Strategy
- **Daily full backup** (retain 7 days)
- **Hourly incremental** (retain 24 hours)
- **WAL archiving** (point-in-time recovery)
- **Test restores** monthly

### 10.2 Point-in-Time Recovery
```bash
# Restore to specific time
pg_restore --target-time="2026-08-24 10:30:00"
```

---

## 11. Anti-Patterns to Avoid

| Anti-Pattern | Why | Instead |
|---|---|---|
| Using `FLOAT` for money | Precision loss | `DECIMAL` or integer cents |
| `VARCHAR(255)` for everything | Arbitrary limit | Match actual data size |
| `TIMESTAMP` without timezone | Timezone bugs | `TIMESTAMPTZ` |
| `SELECT *` | Inefficient, fragile | Explicit columns |
| No foreign key indexes | Slow JOINs | Index all FKs |
| EAV (Entity-Attribute-Value) | Hard to query, no type safety | Normalized tables + JSONB |
| Storing serialized JSON for queryable data | Can't query efficiently | Proper columns or JSONB |
| `NULL` for required fields | Ambiguous | `NOT NULL` + default |
| Triggers for business logic | Hard to debug | Application code |
| Plural table names (singular is also OK) | Inconsistent | Choose one, be consistent |
| Reserved keywords as column names | Syntax errors | Use different names |
| `ENUM` for frequently changing data | Migration pain | Lookup table or VARCHAR |

---

## 12. References

- [PostgreSQL Official Documentation](https://www.postgresql.org/docs/)
- [Use The Index, Luke!](https://use-the-index-luke.com/)
- [Microsoft Database Design Best Practices](https://docs.microsoft.com/en-us/azure/architecture/data-guide/)
- [SQL Style Guide](https://www.sqlstyle.guide/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [PgBouncer](https://www.pgbouncer.org/)

---

## 13. Enforcement

- **Alembic migrations** (versioned, reversible)
- **Code review** (schema review for new tables)
- **EXPLAIN ANALYZE** (in PR reviews for query changes)
- **pg_stat_statements** (monitor slow queries)
- **pgBadger** (log analysis)
