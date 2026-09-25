# Python Coding Standards

> **Scope:** All Python code in Product Forge (root, core/, scripts/, test-framework/, products/<project>/apps/api/)
> **Source:** PEP 8 + Google Python Style Guide + FastAPI/Pydantic best practices
> **Version:** 1.0 | **Date:** 2026-08-24

---

## 1. Code Style

### 1.1 Line Length & Formatting
- **Max line length:** 100 characters (configured in `pyproject.toml`)
- **Indentation:** 4 spaces (no tabs)
- **Quotes:** Double quotes for strings, single quotes for dict keys when needed
- **Trailing commas:** Yes, in multi-line collections
- **Formatter:** `black` (already configured)
- **Linter:** `ruff` with rules E, F, I, N, W, UP, B, C4, SIM (already configured)

### 1.2 Import Order (ruff isort rules)
```python
# 1. Standard library
import os
import sys
from datetime import datetime
from pathlib import Path

# 2. Third-party
import fastapi
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
import sqlalchemy

# 3. Local application
from core.config import settings
from core.database import get_db
```

### 1.3 Naming Conventions
| Type | Convention | Example |
|---|---|---|
| **Variables** | snake_case | `user_name`, `is_active` |
| **Functions** | snake_case | `get_user_by_id`, `validate_email` |
| **Classes** | PascalCase | `UserService`, `TodoRepository` |
| **Constants** | UPPER_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| **Modules** | snake_case | `user_service.py`, `auth_router.py` |
| **Packages** | snake_case | `auth`, `todos` |
| **Type variables** | PascalCase | `UserT`, `ResponseModel` |

---

## 2. Type Hints (Mandatory)

All public functions, methods, and class attributes MUST have type hints.

### 2.1 Basic Types
```python
def get_user_name(user_id: int) -> str:
    return db.query(User).filter(User.id == user_id).first().name
```

### 2.2 Complex Types
```python
from typing import Optional, List, Dict, Tuple
from collections.abc import Sequence

def get_users(
    limit: int = 10,
    offset: int = 0,
    filters: Optional[Dict[str, str]] = None,
) -> Sequence[User]:
    ...
```

### 2.3 Pydantic Models (FastAPI)
```python
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=150)

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    created_at: datetime
    
    class Config:
        from_attributes = True
```

### 2.4 Avoid `Any`
- Use specific types or `Union[A, B]`
- If `Any` is necessary, add comment explaining why

---

## 3. Error Handling

### 3.1 Exception Hierarchy
```python
class AppError(Exception):
    """Base exception for all application errors."""
    pass

class ValidationError(AppError):
    """Raised when input validation fails."""
    pass

class NotFoundError(AppError):
    """Raised when a resource is not found."""
    pass

class AuthError(AppError):
    """Raised when authentication fails."""
    pass

class PermissionError(AppError):
    """Raised when user lacks permission."""
    pass
```

### 3.2 Use Specific Exceptions
```python
# Bad
try:
    user = db.query(User).filter(User.id == user_id).one()
except Exception:
    return None

# Good
try:
    user = db.query(User).filter(User.id == user_id).one()
except NoResultFound:
    raise NotFoundError(f"User {user_id} not found")
except SQLAlchemyError as e:
    logger.error(f"DB error: {e}")
    raise DatabaseError("Database error") from e
```

### 3.3 FastAPI Exception Handlers
```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": {"code": "NOT_FOUND", "message": str(exc)}}
    )
```

### 3.4 Never Use Bare `except`
- Always specify exception type
- Use `Exception` only at top-level boundaries
- Always log unexpected exceptions

---

## 4. Async/Await (FastAPI)

### 4.1 Use Async for I/O
```python
# Async DB queries
async def get_user(user_id: int) -> User:
    async with db.session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

# Async HTTP calls
async def fetch_external_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

### 4.2 Don't Mix Sync and Async
- Don't call sync blocking code in async functions
- Use `asyncio.to_thread` for unavoidable sync calls
- Use `run_in_executor` for FastAPI sync routes

---

## 5. Database (SQLAlchemy)

### 5.1 Async Session Pattern
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import AsyncIterator

async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session

# Usage
async def get_user(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

### 5.2 Model Definitions
```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional

class Todo(Base):
    __tablename__ = "todos"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, onupdate=datetime.utcnow)
    
    user: Mapped["User"] = relationship("User", back_populates="todos")
```

### 5.3 Repository Pattern
```python
from abc import ABC, abstractmethod

class TodoRepository(ABC):
    @abstractmethod
    async def get(self, todo_id: int) -> Todo | None: ...
    @abstractmethod
    async def create(self, todo: TodoCreate, user_id: int) -> Todo: ...
    @abstractmethod
    async def update(self, todo_id: int, data: TodoUpdate) -> Todo: ...
    @abstractmethod
    async def delete(self, todo_id: int) -> None: ...

class SQLTodoRepository(TodoRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get(self, todo_id: int) -> Todo | None:
        result = await self.db.execute(select(Todo).where(Todo.id == todo_id))
        return result.scalar_one_or_none()
```

---

## 6. Pydantic Schemas

### 6.1 Separate Input/Output Models
```python
# Input: what user sends
class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    due_date: datetime | None = None

# Update: optional fields
class TodoUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    completed: bool | None = None

# Output: what API returns
class TodoResponse(BaseModel):
    id: int
    title: str
    description: str | None
    completed: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
```

### 6.2 Validation
```python
from pydantic import Field, EmailStr, HttpUrl, field_validator

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1, max_length=100)
    website: HttpUrl | None = None
    
    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Name cannot be empty or whitespace')
        return v.strip()
```

---

## 7. FastAPI Routes

### 7.1 Route Structure
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from schemas.todo import TodoCreate, TodoResponse
from services.todo_service import TodoService
from dependencies import get_current_user

router = APIRouter(prefix="/api/v1/todos", tags=["todos"])

@router.post("", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def create_todo(
    data: TodoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TodoResponse:
    service = TodoService(db)
    todo = await service.create(data, user_id=current_user.id)
    return TodoResponse.model_validate(todo)

@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(
    todo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TodoResponse:
    service = TodoService(db)
    todo = await service.get(todo_id, user_id=current_user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return TodoResponse.model_validate(todo)
```

### 7.2 Always Use:
- `response_model` for output validation
- `status_code` for success codes
- Type hints for all parameters
- Dependency injection for DB, auth, services
- Async handlers for I/O

---

## 8. Logging

### 8.1 Use structured logging
```python
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Bad
logger.info(f"User {user_id} logged in")

# Good
logger.info("User logged in", extra={
    "user_id": user_id,
    "ip": request.client.host,
    "timestamp": datetime.utcnow().isoformat()
})
```

### 8.2 Log Levels
- **DEBUG:** Detailed diagnostic info (dev only)
- **INFO:** General events (startup, request completed)
- **WARNING:** Something unexpected but recoverable
- **ERROR:** Error that prevented an operation
- **CRITICAL:** System-level failure

### 8.3 What to Log
- Request ID, user ID, action
- Errors with full stack trace
- Performance metrics (duration, size)
- Security events (auth attempts, permission denials)

### 8.4 What NOT to Log
- Passwords, tokens, secrets
- PII (unless explicitly required and encrypted)
- Full request/response bodies (unless needed for debugging)

---

## 9. Configuration

### 9.1 Use Pydantic Settings
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    
    database_url: str
    redis_url: str = "redis://localhost:6379"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    environment: str = "development"
    
settings = Settings()
```

### 9.2 Never Hardcode
- Secrets (use env vars or secret manager)
- URLs (use config)
- Magic numbers (use constants)
- Feature flags (use config)

---

## 10. Testing

### 10.1 Test Structure (see testing.md for full standards)
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_todo(client: AsyncClient, auth_headers: dict):
    # Arrange
    data = {"title": "Buy groceries"}
    
    # Act
    response = await client.post("/api/v1/todos", json=data, headers=auth_headers)
    
    # Assert
    assert response.status_code == 201
    assert response.json()["title"] == "Buy groceries"
```

### 10.2 Test Naming
- `test_<unit>_<scenario>_<expected_result>`
- `test_create_todo_with_valid_data_returns_201`
- `test_get_todo_with_invalid_id_returns_404`

---

## 11. Documentation

### 11.1 Docstrings (Google Style)
```python
def calculate_total(items: list[Item], tax_rate: float) -> Decimal:
    """Calculate total price including tax.
    
    Args:
        items: List of items with price and quantity.
        tax_rate: Tax rate as decimal (e.g., 0.08 for 8%).
    
    Returns:
        Total price including tax.
    
    Raises:
        ValueError: If tax_rate is negative.
    """
    if tax_rate < 0:
        raise ValueError("Tax rate cannot be negative")
    subtotal = sum(item.price * item.quantity for item in items)
    return subtotal * (1 + tax_rate)
```

### 11.2 Type Hints > Docstrings
- Type hints are the source of truth
- Docstrings explain WHY, not WHAT
- Complex business logic needs docstrings

---

## 12. Security (see security.md for full standards)

### 12.1 Input Validation
- Always validate via Pydantic
- Never trust user input
- Sanitize strings for SQL injection (use SQLAlchemy ORM)
- Use parameterized queries

### 12.2 Secrets
- Never commit secrets
- Use environment variables
- Use secret manager in production (AWS Secrets Manager, HashiCorp Vault)

### 12.3 Authentication
- Use established libraries (passlib, python-jose)
- Hash passwords with bcrypt/argon2
- Use JWT with short expiration
- Implement refresh token rotation

---

## 13. Performance

### 13.1 Avoid N+1 Queries
```python
# Bad
todos = await db.execute(select(Todo))
for todo in todos:
    user = await db.execute(select(User).where(User.id == todo.user_id))

# Good
from sqlalchemy.orm import selectinload
todos = await db.execute(
    select(Todo).options(selectinload(Todo.user))
)
```

### 13.2 Use Indexes
- Index foreign keys
- Index frequently queried columns
- Use composite indexes for multi-column queries
- Use partial indexes for filtered queries

### 13.3 Cache When Appropriate
- Cache expensive computations
- Cache external API calls
- Use Redis for session/data caching
- Set appropriate TTLs

---

## 14. Anti-Patterns to Avoid

| Anti-Pattern | Why | Instead |
|---|---|---|
| Mutable default arguments | Shared state bugs | Use `None` and check inside |
| Bare `except:` | Catches everything, hides bugs | Specify exception type |
| `print()` for logging | Not structured, no levels | Use `logging` module |
| Global state | Hard to test, hidden deps | Dependency injection |
| Magic numbers | Hard to understand | Use named constants |
| Deep nesting | Hard to read | Extract functions, early returns |
| Commented-out code | Confusion, no version control | Delete, use git history |
| `from module import *` | Pollutes namespace | Explicit imports |
| `assert` in production | Can be disabled with -O | Use proper validation |
| SQL string concatenation | SQL injection | Use ORM or parameterized queries |

---

## 15. References

- [PEP 8](https://peps.python.org/pep-0008/) — Style Guide for Python Code
- [PEP 484](https://peps.python.org/pep-0484/) — Type Hints
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)

---

## 16. Enforcement

These standards are enforced by:
- **`black`** — Formatting (automatic in CI)
- **`ruff`** — Linting (automatic in CI)
- **`mypy`** — Type checking (automatic in CI)
- **Code review** — Standards not caught by tools
- **Pre-commit hooks** — Local enforcement before commit

Configuration is in `pyproject.toml` at the root.
