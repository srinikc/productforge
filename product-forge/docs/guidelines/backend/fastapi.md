# Backend Engineering Standards

> Python 3.12+, FastAPI, SQLAlchemy 2.0, and modern async backend patterns for MyWorld Central Portal.

## Table of Contents

1. [Project Structure](#project-structure)
2. [FastAPI Application Setup](#fastapi-application-setup)
3. [Routing and Endpoints](#routing-and-endpoints)
4. [Request/Response Models (Pydantic)](#requestresponse-models-pydantic)
5. [Database Access (SQLAlchemy 2.0)](#database-access-sqlalchemy-20)
6. [Async Patterns](#async-patterns)
7. [Authentication and Authorization](#authentication-and-authorization)
8. [Error Handling](#error-handling)
9. [Background Tasks](#background-tasks)
10. [Caching](#caching)
11. [Logging and Observability](#logging-and-observability)
12. [Testing](#testing)
13. [API Versioning](#api-versioning)
14. [Performance](#performance)

---

## Project Structure

```
backend/
├── src/
│   └── myworld/
│       ├── __init__.py
│       ├── main.py                # FastAPI app entry point
│       ├── config.py              # Settings (pydantic-settings)
│       ├── api/                   # API routes
│       │   ├── __init__.py
│       │   ├── deps.py            # Dependency injection
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── router.py
│       │       └── endpoints/
│       │           ├── users.py
│       │           ├── products.py
│       │           └── auth.py
│       ├── core/                  # Core functionality
│       │   ├── security.py
│       │   ├── exceptions.py
│       │   └── logging.py
│       ├── models/                # SQLAlchemy models
│       │   ├── base.py
│       │   ├── user.py
│       │   └── product.py
│       ├── schemas/               # Pydantic schemas
│       │   ├── user.py
│       │   └── product.py
│       ├── services/              # Business logic
│       │   ├── user_service.py
│       │   └── product_service.py
│       ├── db/                    # Database
│       │   ├── base.py
│       │   ├── session.py
│       │   └── migrations/        # Alembic
│       └── utils/                 # Utility functions
├── tests/
│   ├── conftest.py
│   ├── api/
│   ├── services/
│   └── integration/
├── pyproject.toml
├── alembic.ini
└── .env.example
```

---

## FastAPI Application Setup

### App Factory Pattern

```python
# src/myworld/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from myworld.api.v1.router import api_router
from myworld.config import settings
from myworld.core.logging import setup_logging
from myworld.db.session import init_db, close_db

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    await init_db()
    logger.info("Application startup complete")
    yield
    # Shutdown
    await close_db()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="MyWorld API",
        version="1.0.0",
        description="MyWorld Central Portal API",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )
    
    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Routers
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    
    return app


app = create_app()
```

### Settings (pydantic-settings)

```python
# src/myworld/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    # App
    PROJECT_NAME: str = "MyWorld API"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    
    # Security
    SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()
```

---

## Routing and Endpoints

### Router Organization

```python
# src/myworld/api/v1/router.py
from fastapi import APIRouter
from myworld.api.v1.endpoints import users, products, auth

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
```

### Endpoint Definition

```python
# src/myworld/api/v1/endpoints/users.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Annotated

from myworld.api.deps import get_db, get_current_user
from myworld.schemas.user import UserCreate, UserUpdate, UserResponse, UserList
from myworld.services.user_service import UserService
from myworld.models.user import User

router = APIRouter()


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    responses={
        409: {"description": "Email already registered"},
        422: {"description": "Validation error"},
    },
)
async def create_user(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Create a new user with the provided data."""
    service = UserService(db)
    existing = await service.get_by_email(user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    return await service.create(user_in)


@router.get("/", response_model=UserList)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
) -> UserList:
    """List users with pagination and optional search."""
    service = UserService(db)
    users, total = await service.list(
        skip=skip, limit=limit, search=search
    )
    return UserList(items=users, total=total, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get a specific user by ID."""
    service = UserService(db)
    user = await service.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Update a user. Only the user themselves or admin can update."""
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user",
        )
    service = UserService(db)
    user = await service.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )
    return await service.update(user, user_in)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a user. Only admins can delete users."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    service = UserService(db)
    deleted = await service.delete(user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )
```

---

## Request/Response Models (Pydantic)

### Schema Pattern

```python
# src/myworld/schemas/user.py
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """All fields optional for PATCH."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)  # Pydantic v2
    
    id: int
    created_at: datetime
    updated_at: datetime


class UserList(BaseModel):
    items: list[UserResponse]
    total: int
    skip: int
    limit: int


class UserInDB(UserResponse):
    """Internal schema with sensitive data."""
    hashed_password: str
```

### Field Validation

```python
from pydantic import BaseModel, Field, field_validator
import re


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Product name")
    sku: str = Field(..., pattern=r"^[A-Z0-9-]+$", description="Stock keeping unit")
    price: float = Field(..., gt=0, le=1_000_000, description="Price in USD")
    description: str | None = Field(None, max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    
    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Lowercase and dedupe tags."""
        return list({tag.lower().strip() for tag in v if tag.strip()})
    
    @field_validator("sku")
    @classmethod
    def validate_sku(cls, v: str) -> str:
        """Ensure SKU is uppercase."""
        return v.upper()
```

### Discriminated Unions

```python
from typing import Literal, Union, Annotated
from pydantic import BaseModel, Field, Discriminator


class TextContent(BaseModel):
    type: Literal["text"]
    text: str


class ImageContent(BaseModel):
    type: Literal["image"]
    url: str
    alt: str


Content = Annotated[
    Union[TextContent, ImageContent],
    Discriminator("type"),
]


class Post(BaseModel):
    title: str
    content: Content
```

---

## Database Access (SQLAlchemy 2.0)

### Model Definition

```python
# src/myworld/models/user.py
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from myworld.db.base import Base

if TYPE_CHECKING:
    from myworld.models.post import Post


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(),
        nullable=False,
    )
    
    # Relationships
    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="author", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User {self.email}>"
```

### Async Session Management

```python
# src/myworld/db/session.py
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from myworld.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before use
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database connection pool."""
    # Test connection
    async with engine.begin() as conn:
        await conn.execute("SELECT 1")


async def close_db() -> None:
    """Close database connection pool."""
    await engine.dispose()
```

### Service Layer Pattern

```python
# src/myworld/services/user_service.py
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from myworld.models.user import User
from myworld.schemas.user import UserCreate, UserUpdate
from myworld.core.security import get_password_hash, verify_password


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
    
    async def get(self, user_id: int) -> User | None:
        """Get user by ID."""
        return await self.db.get(User, user_id)
    
    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        stmt = select(User).where(User.email == email.lower())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list(
        self, 
        skip: int = 0, 
        limit: int = 20,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        """List users with pagination and search."""
        # Base query
        stmt = select(User)
        count_stmt = select(func.count()).select_from(User)
        
        # Search filter
        if search:
            search_filter = or_(
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)
        
        # Pagination
        stmt = stmt.offset(skip).limit(limit).order_by(User.created_at.desc())
        
        # Execute
        result = await self.db.execute(stmt)
        users = list(result.scalars().all())
        
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar_one()
        
        return users, total
    
    async def create(self, user_in: UserCreate) -> User:
        """Create a new user."""
        user = User(
            email=user_in.email.lower(),
            hashed_password=get_password_hash(user_in.password),
            full_name=user_in.full_name,
            is_active=user_in.is_active,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
    
    async def update(self, user: User, user_in: UserUpdate) -> User:
        """Update an existing user."""
        update_data = user_in.model_dump(exclude_unset=True)
        
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        await self.db.commit()
        await self.db.refresh(user)
        return user
    
    async def delete(self, user_id: int) -> bool:
        """Delete a user by ID."""
        user = await self.get(user_id)
        if not user:
            return False
        await self.db.delete(user)
        await self.db.commit()
        return True
    
    async def authenticate(self, email: str, password: str) -> User | None:
        """Authenticate user with email and password."""
        user = await self.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            return None
        return user
```

---

## Async Patterns

### When to Use Async

```python
# GOOD: Async for I/O-bound operations
async def fetch_user_posts(user_id: int) -> list[Post]:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/users/{user_id}/posts")
        return response.json()


# GOOD: Sync for CPU-bound operations (run in thread pool)
from fastapi.concurrency import run_in_threadpool


@router.post("/upload")
async def upload_image(file: UploadFile):
    # CPU-bound image processing
    contents = await run_in_threadpool(process_image, file.read())
    return {"size": len(contents)}


# BAD: Mixing sync DB calls with async
async def get_user_bad(user_id: int):
    user = db.query(User).filter(User.id == user_id).first()  # ❌ Blocks event loop
    return user


# GOOD: Async DB calls
async def get_user_good(db: AsyncSession, user_id: int):
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
```

### Concurrent Operations

```python
import asyncio


async def get_dashboard_data(user_id: int) -> dict:
    """Fetch multiple resources concurrently."""
    # Run all queries in parallel
    user_task = get_user(user_id)
    posts_task = get_user_posts(user_id)
    stats_task = get_user_stats(user_id)
    
    user, posts, stats = await asyncio.gather(
        user_task, posts_task, stats_task, return_exceptions=True
    )
    
    # Handle errors
    if isinstance(user, Exception):
        user = None
    
    return {
        "user": user,
        "posts": posts if not isinstance(posts, Exception) else [],
        "stats": stats if not isinstance(stats, Exception) else {},
    }
```

### Async Context Managers

```python
from contextlib import asynccontextmanager
import httpx


@asynccontextmanager
async def get_http_client():
    """Reusable HTTP client with proper cleanup."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


async def fetch_multiple_urls(urls: list[str]) -> list[dict]:
    async with get_http_client() as client:
        tasks = [client.get(url) for url in urls]
        responses = await asyncio.gather(*tasks)
        return [r.json() for r in responses]
```

---

## Authentication and Authorization

### Password Hashing

```python
# src/myworld/core/security.py
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
import secrets

from myworld.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str | int,
    expires_delta: timedelta | None = None,
    extra_data: dict | None = None,
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    
    if extra_data:
        to_encode.update(extra_data)
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | int) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": secrets.token_urlsafe(16),  # Unique ID for revocation
    }
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")
```

### Authentication Dependencies

```python
# src/myworld/api/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from myworld.db.session import get_db
from myworld.core.security import decode_token
from myworld.models.user import User
from myworld.services.user_service import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get the current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_token(token)
        user_id_str = payload.get("sub")
        token_type = payload.get("type")
        
        if user_id_str is None or token_type != "access":
            raise credentials_exception
        
        user_id = int(user_id_str)
    except (ValueError, KeyError):
        raise credentials_exception
    
    service = UserService(db)
    user = await service.get(user_id)
    
    if user is None or not user.is_active:
        raise credentials_exception
    
    return user


async def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
```

### Login Endpoint

```python
# src/myworld/api/v1/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from datetime import timedelta

from myworld.api.deps import get_db
from myworld.core.security import create_access_token, create_refresh_token
from myworld.services.user_service import UserService
from myworld.schemas.auth import Token, RefreshTokenRequest
from myworld.config import settings

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """OAuth2 compatible login endpoint."""
    service = UserService(db)
    user = await service.authenticate(form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    access_token = create_access_token(
        subject=user.id,
        extra_data={"email": user.email, "is_admin": user.is_admin},
    )
    refresh_token = create_refresh_token(subject=user.id)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_in: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Refresh access token using refresh token."""
    try:
        payload = decode_token(refresh_in.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id = int(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    service = UserService(db)
    user = await service.get(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    new_access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)
    
    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )
```

---

## Error Handling

### Custom Exceptions

```python
# src/myworld/core/exceptions.py
class MyWorldException(Exception):
    """Base exception for MyWorld."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        code: str | None = None,
        details: dict | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.code = code or self.__class__.__name__
        self.details = details or {}
        super().__init__(message)


class NotFoundError(MyWorldException):
    def __init__(self, resource: str, resource_id: int | str):
        super().__init__(
            message=f"{resource} {resource_id} not found",
            status_code=404,
            code="not_found",
            details={"resource": resource, "id": str(resource_id)},
        )


class ConflictError(MyWorldException):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(
            message=message,
            status_code=409,
            code="conflict",
            details=details,
        )


class ValidationError(MyWorldException):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(
            message=message,
            status_code=422,
            code="validation_error",
            details=details,
        )


class AuthenticationError(MyWorldException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            status_code=401,
            code="authentication_error",
        )


class AuthorizationError(MyWorldException):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            status_code=403,
            code="authorization_error",
        )
```

### Global Exception Handlers

```python
# src/myworld/main.py
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, NoResultFound

from myworld.core.exceptions import MyWorldException
import logging

logger = logging.getLogger(__name__)


@app.exception_handler(MyWorldException)
async def myworld_exception_handler(request: Request, exc: MyWorldException):
    """Handle custom MyWorld exceptions."""
    logger.warning(
        f"MyWorldException: {exc.code} - {exc.message}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "details": exc.details,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle database integrity errors."""
    logger.error(f"IntegrityError: {exc}", exc_info=True)
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "integrity_error",
                "message": "Resource conflict (likely unique constraint violation)",
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An internal server error occurred",
            }
        },
    )
```

### Service-Level Error Handling

```python
# In service layer
async def get_or_404(self, user_id: int) -> User:
    """Get user or raise NotFoundError."""
    user = await self.get(user_id)
    if not user:
        raise NotFoundError("User", user_id)
    return user


# In endpoint
@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    service = UserService(db)
    return await service.get_or_404(user_id)  # Exception handler converts to 404
```

---

## Background Tasks

### FastAPI BackgroundTasks (Simple)

```python
from fastapi import BackgroundTasks


@router.post("/register", response_model=UserResponse, status_code=201)
async def register_user(
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    service = UserService(db)
    user = await service.create(user_in)
    
    # Send welcome email after response is sent
    background_tasks.add_task(send_welcome_email, user.email, user.full_name)
    background_tasks.add_task(create_user_profile, user.id)
    
    return user
```

### Celery for Heavy Tasks

```python
# src/myworld/tasks/email.py
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(ConnectionError, TimeoutError),
)
def send_email(self, to: str, subject: str, body: str) -> dict:
    """Send email via SMTP with retry logic."""
    try:
        # SMTP logic
        send_smtp_email(to, subject, body)
        return {"status": "sent", "to": to}
    except (ConnectionError, TimeoutError) as exc:
        logger.error(f"Failed to send email: {exc}")
        raise self.retry(exc=exc)


# In endpoint
@router.post("/orders")
async def create_order(
    order_in: OrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Order:
    order = await OrderService(db).create(order_in)
    
    # Queue async tasks
    send_email.delay(order.customer_email, "Order Confirmation", f"Order #{order.id}")
    process_payment.delay(order.id)
    
    return order
```

---

## Caching

### Redis Cache with Decorator

```python
# src/myworld/core/cache.py
import json
import functools
from typing import Any, Callable
import redis.asyncio as redis
import hashlib

from myworld.config import settings

_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
    return _redis


def cache(
    ttl: int = 300,  # 5 minutes
    key_prefix: str = "",
) -> Callable:
    """Cache function results in Redis."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key from function name and args
            key_data = f"{func.__name__}:{args}:{kwargs}"
            cache_key = f"{key_prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"
            
            r = await get_redis()
            
            # Try cache
            cached = await r.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await r.setex(cache_key, ttl, json.dumps(result, default=str))
            
            return result
        return wrapper
    return decorator


# Usage
@router.get("/{product_id}")
@cache(ttl=600, key_prefix="product")
async def get_product(product_id: int) -> Product:
    return await ProductService(db).get(product_id)
```

### Cache Invalidation

```python
async def invalidate_product_cache(product_id: int) -> None:
    """Invalidate all cached data for a product."""
    r = await get_redis()
    
    # Invalidate specific product
    await r.delete(f"product:get_product:{product_id}")
    
    # Invalidate list endpoints
    pattern = f"product:list_products:*"
    async for key in r.scan_iter(match=pattern):
        await r.delete(key)


# In update endpoint
@router.put("/{product_id}")
async def update_product(product_id: int, product_in: ProductUpdate) -> Product:
    product = await ProductService(db).update(product_id, product_in)
    await invalidate_product_cache(product_id)
    return product
```

---

## Logging and Observability

### Structured Logging

```python
# src/myworld/core/logging.py
import logging
import sys
import json
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add custom fields from extra
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
            }:
                log_data[key] = value
        
        return json.dumps(log_data, default=str)


def setup_logging() -> None:
    """Configure application logging."""
    from myworld.config import settings
    
    # Root logger
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    
    if settings.is_production:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
    
    root.addHandler(handler)
    
    # Reduce noise from libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
```

### Request Logging Middleware

```python
# src/myworld/middleware.py
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(
            "Request started",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            },
        )
        
        # Process request
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                "Request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )
            return response
        except Exception as exc:
            duration = time.time() - start_time
            logger.error(
                "Request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration * 1000, 2),
                    "error": str(exc),
                },
                exc_info=True,
            )
            raise


# In app factory
app.add_middleware(RequestLoggingMiddleware)
```

---

## Testing

### Fixtures (conftest.py)

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import asyncio

from myworld.main import create_app
from myworld.db.base import Base
from myworld.db.session import get_db
from myworld.models.user import User
from myworld.core.security import get_password_hash


@pytest_asyncio.fixture
async def db_session():
    """Create a test database session."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    TestSessionLocal = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with TestSessionLocal() as session:
        yield session
    
    await test_engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    """Create a test client with test database."""
    app = create_app()
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def test_user(db_session) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("testpass123"),
        full_name="Test User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(client, test_user) -> dict:
    """Get auth headers for authenticated requests."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "testpass123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### Endpoint Tests

```python
# tests/api/test_users.py
import pytest


@pytest.mark.asyncio
async def test_create_user(client):
    response = await client.post(
        "/api/v1/users/",
        json={
            "email": "newuser@example.com",
            "full_name": "New User",
            "password": "securepass123",
        },
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "hashed_password" not in data  # Sensitive data excluded


@pytest.mark.asyncio
async def test_create_user_duplicate_email(client, test_user):
    response = await client.post(
        "/api/v1/users/",
        json={
            "email": test_user.email,
            "full_name": "Duplicate",
            "password": "pass1234",
        },
    )
    
    assert response.status_code == 409
    assert "already registered" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_list_users_requires_auth(client):
    response = await client.get("/api/v1/users/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_users(client, auth_headers):
    response = await client.get("/api/v1/users/", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_user_not_found(client, auth_headers):
    response = await client.get("/api/v1/users/99999", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_user_success(client, auth_headers, test_user):
    response = await client.patch(
        f"/api/v1/users/{test_user.id}",
        json={"full_name": "Updated Name"},
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"
```

---

## API Versioning

### URL-Based Versioning (Recommended)

```python
# Good: /api/v1/users, /api/v2/users
app.include_router(v1_router, prefix="/api/v1")
app.include_router(v2_router, prefix="/api/v2")
```

### Versioning Strategy

```python
# src/myworld/api/v1/endpoints/users.py - v1 implementation
@router.get("/{user_id}")
async def get_user_v1(user_id: int) -> UserV1Schema:
    return await service.get(user_id)


# src/myworld/api/v2/endpoints/users.py - v2 with breaking changes
@router.get("/{user_id}")
async def get_user_v2(user_id: int) -> UserV2Schema:
    user = await service.get(user_id)
    return UserV2Schema(
        id=user.id,
        display_name=f"{user.full_name} ({user.email})",  # New field
        # ... different schema
    )
```

---

## Performance

### N+1 Query Prevention

```python
# BAD: N+1 queries
async def get_posts_with_authors_bad(db: AsyncSession):
    posts = (await db.execute(select(Post))).scalars().all()
    for post in posts:
        post.author = await db.get(User, post.author_id)  # ❌ N queries
    return posts


# GOOD: Eager loading with joinedload
from sqlalchemy.orm import selectinload, joinedload


async def get_posts_with_authors_good(db: AsyncSession):
    stmt = select(Post).options(
        selectinload(Post.author),  # Load all authors in one query
        selectinload(Post.tags),    # Load all tags in one query
    )
    posts = (await db.execute(stmt)).scalars().all()
    return posts
```

### Pagination

```python
# GOOD: Cursor-based pagination for large datasets
from fastapi import Query


@router.get("/posts")
async def list_posts(
    cursor: int | None = Query(None, description="Last post ID from previous page"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(Post).order_by(Post.id.desc()).limit(limit + 1)
    
    if cursor:
        stmt = stmt.where(Post.id < cursor)
    
    posts = (await db.execute(stmt)).scalars().all()
    
    has_more = len(posts) > limit
    posts = posts[:limit]
    next_cursor = posts[-1].id if has_more and posts else None
    
    return {
        "items": posts,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }
```

### Database Connection Pool

```python
# Tune for your workload
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,           # Permanent connections
    max_overflow=10,        # Extra connections under load
    pool_timeout=30,        # Wait time for connection
    pool_recycle=3600,      # Recycle connections after 1 hour
    pool_pre_ping=True,     # Verify before use
)
```

---

## Best Practices Summary

| ✅ DO | ❌ DON'T |
|---|---|
| Use async for I/O-bound operations | Mix sync DB calls with async code |
| Use SQLAlchemy 2.0 typed Mapped[] | Use legacy `Column()` syntax |
| Use Pydantic v2 with `model_config` | Use Pydantic v1 `Config` class |
| Hash passwords with bcrypt/argon2 | Store plain-text passwords |
| Use JWT with expiration | Use session-based auth for APIs |
| Validate all input with Pydantic | Trust user input |
| Use `Annotated[Type, Depends()]` | Use `Depends()` as default value |
| Return Pydantic schemas from endpoints | Return SQLAlchemy models directly |
| Use `selectinload` for relationships | N+1 queries |
| Use environment variables for config | Hard-code secrets |
| Use structured logging (JSON) | Log plain strings |
| Write integration tests for endpoints | Only unit test services |
| Use `run_in_threadpool` for CPU work | Block the event loop |
| Use Redis for distributed caching | Use in-memory cache in multi-instance |
| Add request ID to logs for tracing | Log without context |

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Pydantic v2 Documentation](https://docs.pydantic.dev/latest/)
- [Python Type Hints (PEP 484)](https://peps.python.org/pep-0484/)
- [Async IO in Python](https://docs.python.org/3/library/asyncio.html)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [12 Factor App](https://12factor.net/)
