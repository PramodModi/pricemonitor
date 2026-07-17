# PriceWatch — Low-Level Design

| Field      | Value                                                        |
|------------|--------------------------------------------------------------|
| Version    | 1.0                                                          |
| Status     | Draft — MVP                                                  |
| Date       | July 2026                                                    |
| Depends on | SAD v2.0, API Specification v3.0, Alembic Migrations v2.0   |
| Author     | PriceWatch Team                                              |

---

## Table of Contents

1. [Document Purpose and Scope](#1-document-purpose-and-scope)
2. [Directory Structure](#2-directory-structure)
3. [Configuration Layer](#3-configuration-layer)
4. [Custom Exceptions](#4-custom-exceptions)
5. [ORM Models](#5-orm-models)
6. [Pydantic Schemas](#6-pydantic-schemas)
7. [Repository Layer](#7-repository-layer)
8. [Service Layer](#8-service-layer)
9. [Preview Cache](#9-preview-cache)
10. [URL Validator](#10-url-validator)
11. [Scraper Layer](#11-scraper-layer)
12. [Worker Layer](#12-worker-layer)
13. [Notification Worker](#13-notification-worker)
14. [Run Manager](#14-run-manager)
15. [API Router Layer](#15-api-router-layer)
16. [Application Entry Point](#16-application-entry-point)
17. [Logging Utilities](#17-logging-utilities)
18. [Inter-Component Data Contracts](#18-inter-component-data-contracts)
19. [Error Handling Reference](#19-error-handling-reference)
20. [File-to-Class Index](#20-file-to-class-index)

---

## 1. Document Purpose and Scope

This Low-Level Design (LLD) document defines the class structure, method signatures, docstrings, return types, and inter-component contracts for all backend components of PriceWatch. It is the implementation blueprint — a developer should be able to write production code directly from this document without any ambiguity.

**Scope of this document:**

- `app/core/` — ORM models, configuration, custom exceptions, database session factory
- `app/repositories/` — data access objects for every table
- `app/services/` — business logic: URL validation, product sync, subscription management, preview cache
- `app/scrapers/` — base scraper, Amazon scraper, Flipkart scraper, ScraperAPI fallback
- `app/workers/` — Worker Manager, Scraper Worker, Email Worker
- `app/scheduler/` — Run Manager
- `app/api/` — FastAPI routers and dependency injection
- `app/main.py` — application entry point, lifespan hooks
- `app/utils/` — structured logging, price formatting

**Not in scope:**
- Alembic migration scripts (covered in Alembic Migrations v2.0)
- Streamlit UI components (covered in Streamlit UI Design v3.0)
- Email HTML template rendering (covered in Email Template Design Spec v1.0)
- Infrastructure and deployment configuration

---

## 2. Directory Structure

```
pricewatch/
├── app/
│   ├── main.py                        # FastAPI app factory, lifespan hooks
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                  # Settings via pydantic-settings
│   │   ├── database.py                # SQLAlchemy engine, session factory
│   │   ├── models.py                  # ORM models for all 6 tables
│   │   └── exceptions.py              # Custom exception hierarchy
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── product.py                 # PreviewRequest, PreviewResponse, ProductOut
│   │   ├── subscription.py            # SubscribeRequest, SubscriptionOut, ItemsOut
│   │   ├── run.py                     # RunOut, RunListOut
│   │   └── error.py                   # ErrorDetail, ErrorResponse
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── user_repo.py               # UserRepository
│   │   ├── product_repo.py            # ProductRepository
│   │   ├── subscription_repo.py       # SubscriptionRepository
│   │   ├── price_history_repo.py      # PriceHistoryRepository
│   │   ├── notification_log_repo.py   # NotificationLogRepository
│   │   └── scheduler_run_repo.py      # SchedulerRunRepository
│   ├── services/
│   │   ├── __init__.py
│   │   ├── url_validator.py           # URLValidator
│   │   ├── preview_cache.py           # PreviewCache, ProductSnapshot
│   │   ├── product_sync.py            # ProductSyncService
│   │   └── subscription_service.py    # SubscriptionService
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py                    # BaseScraper (ABC), ScrapeResult dataclass
│   │   ├── amazon.py                  # AmazonScraper
│   │   ├── flipkart.py                # FlipkartScraper
│   │   └── scraperapi_fallback.py     # ScraperAPIFallback
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── worker_manager.py          # WorkerManager
│   │   ├── scraper_worker.py          # ScraperWorker
│   │   └── email_worker.py            # EmailWorker
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── run_manager.py             # RunManager
│   ├── notifications/
│   │   ├── __init__.py
│   │   └── email_sender.py            # EmailSender
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py            # get_db, verify_internal_token
│   │   ├── error_handlers.py          # FastAPI exception handlers
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── products.py            # /v1/products router
│   │       ├── subscriptions.py       # /v1/subscriptions router
│   │       ├── items.py               # /v1/items router
│   │       ├── runs.py                # /v1/runs router
│   │       ├── health.py              # /v1/health router
│   │       └── internal.py            # /v1/internal router
│   └── utils/
│       ├── __init__.py
│       ├── logging.py                 # Structured JSON logger factory
│       └── price.py                   # format_inr, calculate_drop
├── scraper_entrypoint.py              # GitHub Actions entry point (standalone)
├── alembic/                           # Migration scripts (separate document)
├── alembic.ini
├── pyproject.toml
├── .env.example
└── .gitignore
```

---

## 3. Configuration Layer

**File:** `app/core/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Central configuration loaded from environment variables.
    
    All fields with no default are required — startup fails if absent.
    Fields with defaults are optional and suitable for local development.
    """

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str
    """Full SQLAlchemy-compatible PostgreSQL URL.
    Example: postgresql+psycopg2://user:pass@host:5432/pricewatch"""

    # ── External services ─────────────────────────────────────────────────────
    sendgrid_api_key: str
    """SendGrid API key. Used only by the scraper / email worker process."""

    scraper_api_key: str
    """ScraperAPI key for bot-detection fallback. 1,000 req/month on free tier."""

    # ── Internal security ─────────────────────────────────────────────────────
    secret_key: str
    """Bearer token for /v1/internal/* endpoints. Must be kept secret."""

    # ── Worker configuration ──────────────────────────────────────────────────
    max_scraper_workers: int = 3
    """Number of concurrent Playwright browser workers."""

    scrape_retry_limit: int = 3
    """Maximum scrape attempts per product per run before marking as failed."""

    scrape_timeout_seconds: int = 60
    """Hard timeout (seconds) for a single product scrape, including retries."""

    page_goto_timeout_ms: int = 30_000
    """Playwright page.goto() timeout in milliseconds."""

    page_selector_timeout_ms: int = 10_000
    """Playwright wait_for_selector() timeout in milliseconds."""

    worker_health_check_interval: int = 30
    """Seconds between WorkerManager health-check polls."""

    queue_drain_timeout: int = 60
    """Seconds to wait for queue drain on graceful shutdown."""

    # ── Email ─────────────────────────────────────────────────────────────────
    email_retry_limit: int = 3
    """Maximum SendGrid delivery attempts per recipient before giving up."""

    email_from_address: str = "alerts@pricewatch.app"
    email_from_name: str = "PriceWatch"
    email_reply_to: str = "no-reply@pricewatch.app"
    dashboard_url: str = "https://pricewatch.app/dashboard"

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    """Python log level name: DEBUG, INFO, WARNING, ERROR, CRITICAL."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns the cached Settings singleton.
    
    Uses lru_cache so the .env file is read exactly once at startup.
    In tests, call get_settings.cache_clear() before patching env vars.
    
    Returns:
        Settings: The fully validated application settings object.
    """
    return Settings()


settings = get_settings()
```

---

**File:** `app/core/database.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from typing import Generator
from app.core.config import settings


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base. All ORM models inherit from this class.
    Alembic reads Base.metadata to generate migration scripts.
    """
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    # pool_pre_ping issues a lightweight SELECT 1 before each connection use,
    # detecting stale connections and recycling them transparently.
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a SQLAlchemy Session and guarantees cleanup.
    
    Usage in a router:
        def my_endpoint(db: Session = Depends(get_db)):
            ...
    
    Yields:
        Session: An active SQLAlchemy session bound to the request lifecycle.
    
    Raises:
        Any SQLAlchemy exception that occurs during the request is propagated
        upward; the finally block ensures the session is always closed.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 4. Custom Exceptions

**File:** `app/core/exceptions.py`

All domain exceptions inherit from `PriceWatchError`. FastAPI exception handlers in `app/api/error_handlers.py` catch these and convert them to the standard error envelope.

```python
class PriceWatchError(Exception):
    """Base exception for all PriceWatch domain errors."""
    pass


# ── URL Validation ─────────────────────────────────────────────────────────────

class InvalidURLError(PriceWatchError):
    """
    Raised when the submitted URL does not match a supported product page pattern.
    Maps to HTTP 400 / INVALID_URL.
    
    Attributes:
        url (str): The rejected URL, for logging.
    """
    def __init__(self, url: str, detail: str = "") -> None:
        self.url = url
        self.detail = detail
        super().__init__(f"Invalid product URL: {url}")


class UnsupportedPlatformError(PriceWatchError):
    """
    Raised when the URL domain is recognised but the platform is not supported.
    Maps to HTTP 400 / UNSUPPORTED_PLATFORM.
    
    Attributes:
        domain (str): The rejected domain (e.g. 'croma.com').
    """
    def __init__(self, domain: str) -> None:
        self.domain = domain
        super().__init__(f"Unsupported platform: {domain}")


# ── Scraping ───────────────────────────────────────────────────────────────────

class ScrapeError(PriceWatchError):
    """
    Raised when a scrape attempt fails to extract product details.
    Maps to HTTP 502 / SCRAPE_FAILED.
    
    Attributes:
        url (str): The product URL that failed.
        reason (str): Human-readable failure description.
    """
    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"Scrape failed for {url}: {reason}")


class ScrapeBotDetectedError(ScrapeError):
    """
    Raised when the scraper detects bot-blocking (CAPTCHA, 429, redirect to
    challenge page). Signals the worker to route to the ScraperAPI fallback.
    Maps to HTTP 502 / SCRAPE_BLOCKED.
    """
    pass


class ScrapeTimeoutError(ScrapeError):
    """
    Raised when page.goto() or wait_for_selector() exceeds its configured
    timeout. Treated as a transient failure — eligible for retry.
    """
    pass


# ── Preview Cache ──────────────────────────────────────────────────────────────

class PreviewNotFoundError(PriceWatchError):
    """
    Raised when a preview_id does not resolve to a cached ProductSnapshot.
    Maps to HTTP 404 / PREVIEW_NOT_FOUND.
    
    Attributes:
        preview_id (str): The UUID that was not found.
    """
    def __init__(self, preview_id: str) -> None:
        self.preview_id = preview_id
        super().__init__(f"Preview not found: {preview_id}")


# ── Subscription ───────────────────────────────────────────────────────────────

class SubscriptionNotFoundError(PriceWatchError):
    """
    Raised when a subscription_id does not exist or does not belong to the
    requesting email. Maps to HTTP 404 / SUBSCRIPTION_NOT_FOUND.
    Intentionally non-distinguishing — avoids leaking subscription existence.
    """
    def __init__(self, subscription_id: str) -> None:
        self.subscription_id = subscription_id
        super().__init__(f"Subscription not found: {subscription_id}")


# ── Infrastructure ─────────────────────────────────────────────────────────────

class DatabaseConnectionError(PriceWatchError):
    """
    Raised when the database is unreachable after exhausting retries.
    Maps to HTTP 503 / SERVICE_UNAVAILABLE.
    """
    pass


class EmailDeliveryError(PriceWatchError):
    """
    Raised when SendGrid returns a non-retriable error.
    Caught by EmailWorker, logged, and recorded in notification_log.
    """
    def __init__(self, to_email: str, status_code: int, body: str) -> None:
        self.to_email = to_email
        self.status_code = status_code
        self.body = body
        super().__init__(
            f"Email delivery failed to {to_email}: HTTP {status_code}"
        )
```

---

## 5. ORM Models

**File:** `app/core/models.py`

All models inherit from `Base` defined in `database.py`. Column definitions mirror the Alembic migration scripts exactly.

```python
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, ForeignKey, Integer, Numeric, String, Text,
    TIMESTAMP, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """
    Represents a PriceWatch user, identified by email address in MVP.
    
    One User has many Subscriptions (tracked products).
    No password is stored in MVP — authentication is email-only.
    """
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan"
    )
    notification_logs: Mapped[list["NotificationLog"]] = relationship(
        "NotificationLog", back_populates="user"
    )


class Product(Base):
    """
    Represents a unique product tracked in the catalog.
    
    Deduplication key: (platform, marketplace_product_id).
    One Product is shared across all Users who submit the same URL —
    scraping happens once per Product per run.
    
    current_price is NULL until the first scrape succeeds (at subscription
    confirm time or at the next scheduler run).
    """
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("url", name="uq_products_url"),
        UniqueConstraint(
            "platform", "marketplace_product_id",
            name="uq_products_platform_marketplace_id",
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    marketplace_product_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="INR"
    )
    availability: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1), nullable=True)
    review_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    seller: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="product"
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="product", cascade="all, delete-orphan"
    )
    notification_logs: Mapped[list["NotificationLog"]] = relationship(
        "NotificationLog", back_populates="product", cascade="all, delete-orphan"
    )


class Subscription(Base):
    """
    Join table linking a User to a Product they are tracking.
    
    The UNIQUE constraint on (user_id, product_id) prevents a user from
    subscribing to the same product twice. The service layer uses
    INSERT ... ON CONFLICT DO NOTHING for silent idempotency.
    """
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "product_id", name="uq_subscriptions_user_product"
        ),
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.product_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    product: Mapped["Product"] = relationship(
        "Product", back_populates="subscriptions"
    )


class PriceHistory(Base):
    """
    Append-only log of every scrape result for a product.
    
    run_id is NULL for rows written at subscription-confirm time (no scheduler
    run is associated). run_id is set for all scheduler-run writes.
    
    price is NULL when scrape_status is 'failed' or 'blocked'.
    """
    __tablename__ = "price_history"

    history_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheduler_runs.run_id", ondelete="RESTRICT"),
        nullable=True,
    )
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    scrape_status: Mapped[str] = mapped_column(String(20), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    product: Mapped["Product"] = relationship(
        "Product", back_populates="price_history"
    )
    scheduler_run: Mapped[Optional["SchedulerRun"]] = relationship(
        "SchedulerRun", back_populates="price_history_rows"
    )


class NotificationLog(Base):
    """
    Records every email notification attempt.
    
    Supports:
    - Delivery diagnostics (query by status = 'failed')
    - Phase 3 cooldown check (composite index on user_id, product_id, sent_at)
    """
    __tablename__ = "notification_log"

    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheduler_runs.run_id", ondelete="RESTRICT"),
        nullable=False,
    )
    old_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    new_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", back_populates="notification_logs"
    )
    product: Mapped["Product"] = relationship(
        "Product", back_populates="notification_logs"
    )
    scheduler_run: Mapped["SchedulerRun"] = relationship(
        "SchedulerRun", back_populates="notification_log_rows"
    )


class SchedulerRun(Base):
    """
    One row per scheduled scraper execution.
    
    Created at run start with status='running'. Updated at run end with
    final status and aggregate metrics. The primary observability instrument.
    
    status values:
      'running'   — run currently in progress
      'completed' — all products scraped, no failures
      'partial'   — one or more products failed after max retries
      'failed'    — run could not start (e.g. DB unreachable)
    """
    __tablename__ = "scheduler_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    products_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    products_scraped: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    products_failed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price_drops_found: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    emails_sent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    price_history_rows: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="scheduler_run"
    )
    notification_log_rows: Mapped[list["NotificationLog"]] = relationship(
        "NotificationLog", back_populates="scheduler_run"
    )
```

---

## 6. Pydantic Schemas

**File:** `app/schemas/error.py`

```python
from pydantic import BaseModel
from typing import Optional


class ErrorDetail(BaseModel):
    """Machine-readable error envelope returned by all error responses."""
    code: str
    """Machine-readable error code. See API Specification §4 for full list."""
    message: str
    """Human-readable summary suitable for display."""
    detail: Optional[str] = None
    """Additional context when helpful (e.g. supported platforms)."""


class ErrorResponse(BaseModel):
    """Top-level wrapper for all error responses."""
    error: ErrorDetail
```

---

**File:** `app/schemas/product.py`

```python
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, HttpUrl, field_validator


class PreviewRequest(BaseModel):
    """Request body for POST /v1/products/preview."""
    url: str
    """Raw product URL as submitted by the user. Validated by URLValidator."""


class LiveData(BaseModel):
    """
    Live scrape result for a product. Populated by the Playwright scraper.
    Always present in a PreviewResponse.
    """
    marketplace_product_id: str
    url: str
    platform: str
    name: str
    brand: Optional[str] = None
    image_url: Optional[str] = None
    current_price: Decimal
    currency: str = "INR"
    availability: bool
    rating: Optional[Decimal] = None
    review_count: Optional[int] = None
    seller: Optional[str] = None
    scraped_at: datetime


class PriceStats(BaseModel):
    """Aggregate price statistics from price_history. Used in catalog_data."""
    all_time_low: Decimal
    all_time_high: Decimal
    drop_count: int
    first_tracked_at: datetime


class CatalogData(BaseModel):
    """
    Existing catalog context for a product that is already in the database.
    Null in PreviewResponse when is_new_product = True.
    """
    product_id: uuid.UUID
    last_tracked_price: Optional[Decimal] = None
    price_change_indicator: Optional[str] = None
    """'up', 'down', 'unchanged', or None if no prior price."""
    price_change_amount: Optional[Decimal] = None
    last_checked_at: Optional[datetime] = None
    watcher_count: int
    price_stats: Optional[PriceStats] = None


class PreviewResponse(BaseModel):
    """Response body for POST /v1/products/preview."""
    preview_id: uuid.UUID
    expires_at: datetime
    is_new_product: bool
    live_data: LiveData
    catalog_data: Optional[CatalogData] = None


class ProductOut(BaseModel):
    """
    Full product representation returned after subscription confirm
    and by GET /v1/products/{product_id}.
    """
    product_id: uuid.UUID
    marketplace_product_id: str
    url: str
    platform: str
    name: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None
    current_price: Optional[Decimal] = None
    currency: str
    availability: Optional[bool] = None
    rating: Optional[Decimal] = None
    review_count: Optional[int] = None
    seller: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    created_at: datetime
    watcher_count: Optional[int] = None
    price_stats: Optional[PriceStats] = None

    model_config = {"from_attributes": True}
```

---

**File:** `app/schemas/subscription.py`

```python
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.schemas.product import ProductOut


class SubscribeRequest(BaseModel):
    """Request body for POST /v1/subscriptions."""
    preview_id: uuid.UUID
    """Token from a prior POST /v1/products/preview call."""
    email: EmailStr
    """User email — stored lowercase. Identifies the user in MVP."""


class SubscriptionOut(BaseModel):
    """Response body for POST /v1/subscriptions."""
    subscription_id: uuid.UUID
    is_new_subscription: bool
    """False if the user was already subscribed — idempotent success."""
    re_scraped: bool
    """True if the preview had expired and a fresh scrape was performed."""
    product: ProductOut


class ItemOut(BaseModel):
    """One tracked item in the GET /v1/items response."""
    subscription_id: uuid.UUID
    subscribed_at: datetime
    product: ProductOut

    model_config = {"from_attributes": True}


class ItemsOut(BaseModel):
    """Response body for GET /v1/items."""
    email: str
    count: int
    items: list[ItemOut]


class DeleteSubscriptionOut(BaseModel):
    """Response body for DELETE /v1/subscriptions/{subscription_id}."""
    subscription_id: uuid.UUID
    product_deleted: bool
    """True if this was the last subscriber and the product row was deleted."""
    message: str
```

---

**File:** `app/schemas/run.py`

```python
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class RunFailureItem(BaseModel):
    """One product failure within a partial or failed run."""
    product_id: uuid.UUID
    product_name: Optional[str] = None
    url: str
    scrape_status: str
    checked_at: datetime


class RunOut(BaseModel):
    """Response body for GET /v1/runs/{run_id}."""
    run_id: uuid.UUID
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    products_total: Optional[int] = None
    products_scraped: Optional[int] = None
    products_failed: Optional[int] = None
    price_drops_found: Optional[int] = None
    emails_sent: Optional[int] = None
    failures: Optional[list[RunFailureItem]] = None
    """Populated only for GET /v1/runs/{run_id}, not in list view."""

    model_config = {"from_attributes": True}


class RunListOut(BaseModel):
    """Response body for GET /v1/runs."""
    total: int
    limit: int
    offset: int
    runs: list[RunOut]
```

---

## 7. Repository Layer

Each repository receives a `Session` via constructor injection. No repository ever creates its own session — the session lifecycle is owned by the caller (FastAPI dependency or service layer).

---

**File:** `app/repositories/user_repo.py`

```python
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.models import User
from typing import Optional


class UserRepository:
    """Data access object for the users table."""

    def __init__(self, db: Session) -> None:
        """
        Args:
            db: Active SQLAlchemy session. Not owned by this repository.
        """
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Retrieve a User by email address (case-insensitive).
        
        Args:
            email: Email address to look up. Compared case-insensitively.
        
        Returns:
            The matching User, or None if not found.
        """
        return self.db.scalar(
            select(User).where(User.email == email.strip().lower())
        )

    def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """
        Retrieve a User by primary key.
        
        Args:
            user_id: The UUID primary key.
        
        Returns:
            The matching User, or None if not found.
        """
        return self.db.get(User, user_id)

    def create(self, email: str) -> User:
        """
        Insert a new User row. Caller must commit the session.
        
        Args:
            email: Email address stored in lowercase.
        
        Returns:
            The newly created User (not yet committed).
        """
        user = User(email=email.strip().lower())
        self.db.add(user)
        self.db.flush()   # assigns user_id without committing
        return user

    def get_or_create(self, email: str) -> tuple[User, bool]:
        """
        Retrieve an existing User or create a new one atomically.
        
        Args:
            email: Email address, normalised to lowercase internally.
        
        Returns:
            A tuple of (User, created) where created is True if a new
            row was inserted, False if an existing row was returned.
        """
        user = self.get_by_email(email)
        if user:
            return user, False
        user = self.create(email)
        return user, True
```

---

**File:** `app/repositories/product_repo.py`

```python
import uuid
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.core.models import Product, Subscription, PriceHistory


class ProductRepository:
    """Data access object for the products table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, product_id: uuid.UUID) -> Optional[Product]:
        """
        Retrieve a Product by primary key.
        
        Args:
            product_id: The UUID primary key.
        
        Returns:
            The matching Product, or None if not found.
        """
        return self.db.get(Product, product_id)

    def get_by_platform_and_marketplace_id(
        self,
        platform: str,
        marketplace_product_id: str,
    ) -> Optional[Product]:
        """
        Primary deduplication lookup. Find an existing product by the
        platform-native product identifier (ASIN for Amazon, PID for Flipkart).
        
        Args:
            platform: 'amazon' or 'flipkart'.
            marketplace_product_id: ASIN or PID extracted from the URL or scrape.
        
        Returns:
            The matching Product, or None if this is a new product.
        """
        return self.db.scalar(
            select(Product).where(
                Product.platform == platform,
                Product.marketplace_product_id == marketplace_product_id,
            )
        )

    def get_by_url(self, url: str) -> Optional[Product]:
        """
        Secondary deduplication lookup by canonical URL.
        
        Args:
            url: Canonical product URL (tracking parameters stripped).
        
        Returns:
            The matching Product, or None.
        """
        return self.db.scalar(select(Product).where(Product.url == url))

    def create(self, **fields) -> Product:
        """
        Insert a new Product row. Caller must commit.
        
        Args:
            **fields: Column values matching Product model attributes.
                      Must include: url, platform, marketplace_product_id.
        
        Returns:
            The newly created Product (flushed, not committed).
        """
        product = Product(**fields)
        self.db.add(product)
        self.db.flush()
        return product

    def update_from_live_data(
        self,
        product: Product,
        live_data: dict,
    ) -> Product:
        """
        Overwrite mutable metadata fields from a fresh scrape result.
        Fields updated: name, brand, image_url, availability, rating,
        review_count, seller, last_checked_at.
        current_price is NOT updated here — that is handled by
        ProductSyncService to enable price drop detection.
        
        Args:
            product: The existing Product ORM object to update.
            live_data: Dict matching LiveData schema fields.
        
        Returns:
            The updated Product (not committed).
        """
        updatable_fields = [
            "name", "brand", "image_url", "availability",
            "rating", "review_count", "seller", "last_checked_at",
        ]
        for field in updatable_fields:
            if field in live_data:
                setattr(product, field, live_data[field])
        self.db.flush()
        return product

    def update_current_price(
        self,
        product: Product,
        new_price: Decimal,
    ) -> Product:
        """
        Update the current_price field after confirming a price drop.
        Called only when scraped price < current_price.
        
        Args:
            product: The Product to update.
            new_price: The newly scraped price.
        
        Returns:
            The updated Product (not committed).
        """
        product.current_price = new_price
        self.db.flush()
        return product

    def get_all_for_scraping(self) -> list[Product]:
        """
        Retrieve all products ordered for stable scraping.
        Used by RunManager to enqueue the full scrape batch.
        
        Returns:
            All Product rows, ordered by created_at ascending so older
            products are scraped first (predictable ordering for diagnostics).
        """
        return list(
            self.db.scalars(
                select(Product).order_by(Product.created_at.asc())
            )
        )

    def get_watcher_count(self, product_id: uuid.UUID) -> int:
        """
        Count the number of active subscribers for a product.
        Used in preview catalog_data and GET /products/{product_id}.
        
        Args:
            product_id: The product UUID.
        
        Returns:
            Integer count of active subscriptions.
        """
        result = self.db.scalar(
            select(func.count(Subscription.subscription_id)).where(
                Subscription.product_id == product_id
            )
        )
        return result or 0

    def get_price_stats(self, product_id: uuid.UUID) -> Optional[dict]:
        """
        Compute aggregate price statistics from price_history for a product.
        Returns None if no successful price history rows exist.
        
        Args:
            product_id: The product UUID.
        
        Returns:
            Dict with keys: all_time_low, all_time_high, drop_count,
            first_tracked_at. Or None if no history exists.
        """
        row = self.db.execute(
            select(
                func.min(PriceHistory.price).label("all_time_low"),
                func.max(PriceHistory.price).label("all_time_high"),
                func.min(PriceHistory.checked_at).label("first_tracked_at"),
            ).where(
                PriceHistory.product_id == product_id,
                PriceHistory.scrape_status == "success",
                PriceHistory.price.isnot(None),
            )
        ).one()

        if row.all_time_low is None:
            return None

        # Count price drops: rows where price < the previous recorded price.
        # Simplified for MVP: count distinct runs where current_price was updated.
        # Full drop detection uses a window function in Phase 2.
        drop_count = self.db.scalar(
            select(func.count()).select_from(PriceHistory).where(
                PriceHistory.product_id == product_id,
                PriceHistory.scrape_status == "success",
            )
        ) or 0

        return {
            "all_time_low": row.all_time_low,
            "all_time_high": row.all_time_high,
            "drop_count": drop_count,
            "first_tracked_at": row.first_tracked_at,
        }

    def delete(self, product: Product) -> None:
        """
        Delete a Product and cascade to price_history and notification_log.
        Called by SubscriptionService when the last subscriber unsubscribes.
        Caller must commit.
        
        Args:
            product: The Product ORM object to delete.
        """
        self.db.delete(product)
        self.db.flush()
```

---

**File:** `app/repositories/subscription_repo.py`

```python
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.core.models import Subscription, User, Product


class SubscriptionRepository:
    """Data access object for the subscriptions table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, subscription_id: uuid.UUID) -> Optional[Subscription]:
        """
        Retrieve a Subscription by primary key, eager-loading product.
        
        Args:
            subscription_id: The subscription UUID.
        
        Returns:
            The Subscription with product loaded, or None.
        """
        return self.db.get(Subscription, subscription_id)

    def get_by_user_and_product(
        self,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> Optional[Subscription]:
        """
        Check whether a subscription already exists for a user-product pair.
        Used to detect duplicates before the upsert.
        
        Args:
            user_id: User UUID.
            product_id: Product UUID.
        
        Returns:
            Existing Subscription or None.
        """
        return self.db.scalar(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.product_id == product_id,
            )
        )

    def get_or_create(
        self,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> tuple[Subscription, bool]:
        """
        Get an existing subscription or create a new one.
        Silent on duplicate — does not raise if subscription already exists.
        
        Args:
            user_id: The user's UUID.
            product_id: The product's UUID.
        
        Returns:
            Tuple of (Subscription, created). created=True means a new row
            was inserted; False means an existing row was returned.
        """
        existing = self.get_by_user_and_product(user_id, product_id)
        if existing:
            return existing, False

        sub = Subscription(user_id=user_id, product_id=product_id)
        self.db.add(sub)
        self.db.flush()
        return sub, True

    def get_all_for_user(self, user_id: uuid.UUID) -> list[Subscription]:
        """
        Retrieve all subscriptions for a user, with products eager-loaded.
        Used by GET /v1/items.
        
        Args:
            user_id: The user's UUID.
        
        Returns:
            List of Subscription objects, each with .product populated.
        """
        from sqlalchemy.orm import joinedload
        return list(
            self.db.scalars(
                select(Subscription)
                .options(joinedload(Subscription.product))
                .where(Subscription.user_id == user_id)
                .order_by(Subscription.created_at.desc())
            )
        )

    def get_subscriber_emails_for_product(
        self,
        product_id: uuid.UUID,
    ) -> list[str]:
        """
        Return all subscriber email addresses for a given product.
        Called by EmailWorker at notification fan-out time.
        
        Args:
            product_id: The product UUID.
        
        Returns:
            List of email address strings (lowercase).
        """
        rows = self.db.execute(
            select(User.email)
            .join(Subscription, Subscription.user_id == User.user_id)
            .where(Subscription.product_id == product_id)
        ).all()
        return [row.email for row in rows]

    def delete(self, subscription: Subscription) -> None:
        """
        Delete a Subscription row. Caller must commit.
        Does NOT delete the Product — that decision belongs to SubscriptionService.
        
        Args:
            subscription: The Subscription ORM object to delete.
        """
        self.db.delete(subscription)
        self.db.flush()

    def count_for_product(self, product_id: uuid.UUID) -> int:
        """
        Count remaining subscriptions for a product after a deletion.
        Used by SubscriptionService to decide whether to delete the product.
        
        Args:
            product_id: The product UUID.
        
        Returns:
            Integer count.
        """
        from sqlalchemy import func
        return self.db.scalar(
            select(func.count(Subscription.subscription_id)).where(
                Subscription.product_id == product_id
            )
        ) or 0
```

---

**File:** `app/repositories/price_history_repo.py`

```python
import uuid
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from app.core.models import PriceHistory


class PriceHistoryRepository:
    """Data access object for the price_history table (append-only)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def insert(
        self,
        product_id: uuid.UUID,
        price: Optional[Decimal],
        scrape_status: str,
        run_id: Optional[uuid.UUID] = None,
    ) -> PriceHistory:
        """
        Append one price history row. Caller must commit.
        
        Args:
            product_id: FK to products.
            price: Scraped price. None if scrape_status is 'failed' or 'blocked'.
            scrape_status: One of 'success', 'failed', 'blocked'.
            run_id: FK to scheduler_runs. None for subscription-time writes.
        
        Returns:
            The newly created PriceHistory row (flushed).
        """
        row = PriceHistory(
            product_id=product_id,
            price=price,
            scrape_status=scrape_status,
            run_id=run_id,
        )
        self.db.add(row)
        self.db.flush()
        return row
```

---

**File:** `app/repositories/scheduler_run_repo.py`

```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.core.models import SchedulerRun


class SchedulerRunRepository:
    """Data access object for the scheduler_runs table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self) -> SchedulerRun:
        """
        Insert a new SchedulerRun with status='running'.
        Called at the very start of each scrape cycle.
        Caller must commit.
        
        Returns:
            The newly created SchedulerRun (flushed).
        """
        run = SchedulerRun(
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        self.db.add(run)
        self.db.flush()
        return run

    def get_by_id(self, run_id: uuid.UUID) -> Optional[SchedulerRun]:
        """
        Retrieve a SchedulerRun by primary key.
        
        Args:
            run_id: The run UUID.
        
        Returns:
            The matching SchedulerRun, or None.
        """
        return self.db.get(SchedulerRun, run_id)

    def complete(
        self,
        run: SchedulerRun,
        status: str,
        products_total: int,
        products_scraped: int,
        products_failed: int,
        price_drops_found: int,
        emails_sent: int,
    ) -> SchedulerRun:
        """
        Mark a run as complete with final metrics. Caller must commit.
        
        Args:
            run: The SchedulerRun to update.
            status: Final status — 'completed' or 'partial'.
            products_total: Total products enqueued.
            products_scraped: Successfully scraped count.
            products_failed: Failed after max retries.
            price_drops_found: Price drops detected this run.
            emails_sent: Notification emails dispatched.
        
        Returns:
            The updated SchedulerRun (not committed).
        """
        run.completed_at = datetime.now(timezone.utc)
        run.status = status
        run.products_total = products_total
        run.products_scraped = products_scraped
        run.products_failed = products_failed
        run.price_drops_found = price_drops_found
        run.emails_sent = emails_sent
        self.db.flush()
        return run

    def mark_failed(self, run: SchedulerRun) -> SchedulerRun:
        """
        Mark a run as failed (could not complete). Caller must commit.
        Used when the database is unreachable or a fatal error occurs.
        
        Args:
            run: The SchedulerRun to update.
        
        Returns:
            The updated SchedulerRun.
        """
        run.completed_at = datetime.now(timezone.utc)
        run.status = "failed"
        self.db.flush()
        return run

    def list_recent(self, limit: int = 10, offset: int = 0) -> tuple[int, list[SchedulerRun]]:
        """
        Retrieve recent runs for the admin /runs endpoint.
        
        Args:
            limit: Maximum rows to return.
            offset: Pagination offset.
        
        Returns:
            Tuple of (total_count, list_of_runs).
        """
        total = self.db.scalar(
            select(func.count(SchedulerRun.run_id))
        ) or 0
        runs = list(
            self.db.scalars(
                select(SchedulerRun)
                .order_by(SchedulerRun.started_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return total, runs
```

---

**File:** `app/repositories/notification_log_repo.py`

```python
import uuid
from decimal import Decimal
from sqlalchemy.orm import Session
from app.core.models import NotificationLog


class NotificationLogRepository:
    """Data access object for the notification_log table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def insert(
        self,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
        run_id: uuid.UUID,
        old_price: Decimal,
        new_price: Decimal,
        status: str,
    ) -> NotificationLog:
        """
        Record one email notification attempt. Caller must commit.
        
        Args:
            user_id: FK to users.
            product_id: FK to products.
            run_id: FK to scheduler_runs. Always set for notification rows.
            old_price: Price before the drop.
            new_price: Price after the drop.
            status: 'sent', 'failed', or 'skipped'.
        
        Returns:
            The newly created NotificationLog row (flushed).
        """
        row = NotificationLog(
            user_id=user_id,
            product_id=product_id,
            run_id=run_id,
            old_price=old_price,
            new_price=new_price,
            status=status,
        )
        self.db.add(row)
        self.db.flush()
        return row
```

---

## 8. Service Layer

### 8.1 URL Validator

**File:** `app/services/url_validator.py`

```python
import re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from app.core.exceptions import InvalidURLError, UnsupportedPlatformError


# Tracking parameters stripped from Amazon and Flipkart URLs before storage.
_AMAZON_STRIP_PARAMS = {"ref", "ref_", "tag", "linkCode", "th", "psc"}
_FLIPKART_STRIP_PARAMS = {"affid", "affExtParam1", "affExtParam2", "otracker"}

# Compiled patterns per platform. Must match before a URL is accepted.
_AMAZON_PRODUCT_PATTERNS = [
    re.compile(r"/dp/([A-Z0-9]{10})"),
    re.compile(r"/gp/product/([A-Z0-9]{10})"),
]
_FLIPKART_PRODUCT_PATTERNS = [
    re.compile(r"/p/([a-zA-Z0-9]+)"),
    re.compile(r"/dl/[^/]+/[^/]+/p/([a-zA-Z0-9]+)"),
]

SUPPORTED_DOMAINS = {
    "amazon.in": "amazon",
    "www.amazon.in": "amazon",
    "amzn.in": "amazon",
    "flipkart.com": "flipkart",
    "www.flipkart.com": "flipkart",
}

MAX_URL_LENGTH = 2048


@dataclass
class ValidatedURL:
    """Result of a successful URL validation."""
    platform: str
    """'amazon' or 'flipkart'."""
    canonical_url: str
    """URL with tracking parameters removed."""
    marketplace_product_id: str
    """ASIN for Amazon. PID for Flipkart."""


class URLValidator:
    """
    Stateless URL validation and canonicalisation.
    
    Validates that a submitted URL is:
      1. Within the length limit
      2. A recognised and supported domain
      3. Matching a known product page URL pattern
    
    Strips tracking parameters and returns a canonical form.
    Extracts the marketplace_product_id (ASIN / PID) from the URL.
    
    Note: For amzn.in short URLs, marketplace_product_id cannot be extracted
    from the URL alone — it will be filled in from the scrape result.
    """

    def validate(self, raw_url: str) -> ValidatedURL:
        """
        Validate and canonicalise a product URL.
        
        Args:
            raw_url: The URL string as submitted by the user.
        
        Returns:
            A ValidatedURL with platform, canonical_url, and
            marketplace_product_id.
        
        Raises:
            InvalidURLError: URL is malformed, too long, or does not match
                             a product page pattern.
            UnsupportedPlatformError: Domain is recognised but not supported.
        """
        if not raw_url or len(raw_url) > MAX_URL_LENGTH:
            raise InvalidURLError(raw_url, "URL exceeds maximum length or is empty.")

        parsed = urlparse(raw_url.strip())
        if parsed.scheme not in ("http", "https"):
            raise InvalidURLError(raw_url, "URL must use http or https.")

        domain = parsed.netloc.lower()
        if domain not in SUPPORTED_DOMAINS:
            # Check if it's any known e-commerce domain we don't support yet
            known_unsupported = {"croma.com", "reliancedigital.in", "myntra.com"}
            if any(d in domain for d in known_unsupported):
                raise UnsupportedPlatformError(domain)
            raise InvalidURLError(raw_url, f"Domain '{domain}' is not supported.")

        platform = SUPPORTED_DOMAINS[domain]

        # amzn.in short URLs — accept but defer ASIN extraction to scraper
        if domain == "amzn.in":
            return ValidatedURL(
                platform="amazon",
                canonical_url=raw_url.strip(),
                marketplace_product_id="",  # filled by scraper
            )

        marketplace_product_id = self._extract_product_id(platform, parsed.path, raw_url)
        canonical_url = self._canonicalise(platform, parsed)
        return ValidatedURL(
            platform=platform,
            canonical_url=canonical_url,
            marketplace_product_id=marketplace_product_id,
        )

    def _extract_product_id(
        self,
        platform: str,
        path: str,
        raw_url: str,
    ) -> str:
        """
        Extract the marketplace product ID from the URL path.
        
        Args:
            platform: 'amazon' or 'flipkart'.
            path: The URL path component.
            raw_url: Original URL, used in error messages.
        
        Returns:
            ASIN (for Amazon) or PID (for Flipkart) as a string.
        
        Raises:
            InvalidURLError: Path does not match any known product page pattern.
        """
        patterns = (
            _AMAZON_PRODUCT_PATTERNS
            if platform == "amazon"
            else _FLIPKART_PRODUCT_PATTERNS
        )
        for pattern in patterns:
            match = pattern.search(path)
            if match:
                return match.group(1)
        raise InvalidURLError(
            raw_url,
            f"URL path does not match a known {platform} product page pattern.",
        )

    def _canonicalise(self, platform: str, parsed) -> str:
        """
        Strip tracking query parameters and rebuild a clean URL.
        
        Args:
            platform: 'amazon' or 'flipkart'.
            parsed: Result of urlparse() on the submitted URL.
        
        Returns:
            Canonical URL string.
        """
        strip_params = (
            _AMAZON_STRIP_PARAMS if platform == "amazon" else _FLIPKART_STRIP_PARAMS
        )
        query_params = parse_qs(parsed.query, keep_blank_values=False)
        clean_params = {
            k: v for k, v in query_params.items() if k not in strip_params
        }
        clean_query = urlencode(clean_params, doseq=True)
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            clean_query,
            "",  # strip fragment
        ))
```

---

### 8.2 Preview Cache

**File:** `app/services/preview_cache.py`

```python
import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.schemas.product import LiveData, CatalogData
from app.core.exceptions import PreviewNotFoundError
from app.core.config import settings


PREVIEW_TTL_MINUTES = 10


@dataclass
class ProductSnapshot:
    """
    Cached result of POST /products/preview. Combines live scrape data with
    any existing catalog context. Held in memory for PREVIEW_TTL_MINUTES.
    
    Never persisted to the database. Lost on process restart (Railway restart
    causes PREVIEW_NOT_FOUND — user retries with one extra click; acceptable
    for MVP. See SAD ADR-012).
    """
    preview_id: uuid.UUID
    expires_at: datetime
    is_new_product: bool
    live_data: LiveData
    catalog_data: Optional[CatalogData] = None

    def is_expired(self) -> bool:
        """Return True if this snapshot has passed its TTL."""
        return datetime.now(timezone.utc) >= self.expires_at


class PreviewCache:
    """
    Thread-safe in-memory store for ProductSnapshot objects.
    
    Backed by a plain dict protected by a RLock. A background APScheduler
    job calls purge_expired() every 15 minutes to release memory from
    abandoned previews (user fetched but never confirmed).
    
    At MVP scale (< 100 concurrent previews), this is entirely sufficient.
    Replace with Redis at Phase 2 scale (see SAD §22.1).
    """

    def __init__(self) -> None:
        self._store: dict[str, ProductSnapshot] = {}
        self._lock = threading.RLock()

    def store(self, snapshot: ProductSnapshot) -> None:
        """
        Add or replace a snapshot keyed by its preview_id.
        
        Args:
            snapshot: The ProductSnapshot to cache.
        """
        with self._lock:
            self._store[str(snapshot.preview_id)] = snapshot

    def get(self, preview_id: str) -> ProductSnapshot:
        """
        Retrieve a snapshot by preview_id.
        
        Args:
            preview_id: UUID string of the preview.
        
        Returns:
            The matching ProductSnapshot (may be expired — caller checks).
        
        Raises:
            PreviewNotFoundError: No snapshot exists for this preview_id.
        """
        with self._lock:
            snapshot = self._store.get(preview_id)
            if snapshot is None:
                raise PreviewNotFoundError(preview_id)
            return snapshot

    def consume(self, preview_id: str) -> ProductSnapshot:
        """
        Retrieve a snapshot and immediately delete it from the cache.
        Called by POST /subscriptions after successful processing.
        
        Args:
            preview_id: UUID string of the preview.
        
        Returns:
            The matching ProductSnapshot.
        
        Raises:
            PreviewNotFoundError: No snapshot exists for this preview_id.
        """
        with self._lock:
            snapshot = self._store.pop(preview_id, None)
            if snapshot is None:
                raise PreviewNotFoundError(preview_id)
            return snapshot

    def purge_expired(self) -> int:
        """
        Remove all expired snapshots. Called by the APScheduler purge job.
        
        Returns:
            Number of entries removed.
        """
        with self._lock:
            expired_keys = [
                k for k, v in self._store.items() if v.is_expired()
            ]
            for k in expired_keys:
                del self._store[k]
            return len(expired_keys)

    @staticmethod
    def make_expires_at() -> datetime:
        """Return a UTC datetime PREVIEW_TTL_MINUTES from now."""
        return datetime.now(timezone.utc) + timedelta(minutes=PREVIEW_TTL_MINUTES)


# Module-level singleton shared across all FastAPI requests
preview_cache = PreviewCache()
```

---

### 8.3 Product Sync Service

**File:** `app/services/product_sync.py`

```python
import uuid
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.core.models import Product, User
from app.repositories.user_repo import UserRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.price_history_repo import PriceHistoryRepository
from app.services.preview_cache import ProductSnapshot
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SyncResult:
    """
    Return value from ProductSyncService.sync(). Carries all IDs
    needed by the POST /subscriptions response.
    """
    def __init__(
        self,
        user: User,
        product: Product,
        subscription_id: uuid.UUID,
        is_new_subscription: bool,
        price_updated: bool,
    ) -> None:
        self.user = user
        self.product = product
        self.subscription_id = subscription_id
        self.is_new_subscription = is_new_subscription
        self.price_updated = price_updated


class ProductSyncService:
    """
    Orchestrates the confirm-subscription write path.
    
    Executed inside POST /subscriptions after a preview_id is consumed
    from the cache. Responsible for:
    
    1. Get or create User by email
    2. Upsert Product (create if new, update metadata if existing)
    3. Compare live price with stored price, insert price_history row
    4. Update current_price if changed
    5. Get or create Subscription (idempotent)
    
    All writes happen in a single database transaction owned by the caller.
    The session is passed in — this service does not commit.
    """

    def __init__(self, db: Session) -> None:
        """
        Args:
            db: Active SQLAlchemy session. Transaction managed by caller.
        """
        self.db = db
        self.user_repo = UserRepository(db)
        self.product_repo = ProductRepository(db)
        self.sub_repo = SubscriptionRepository(db)
        self.ph_repo = PriceHistoryRepository(db)

    def sync(self, snapshot: ProductSnapshot, email: str) -> SyncResult:
        """
        Execute the full subscription confirm write path atomically.
        
        Args:
            snapshot: The ProductSnapshot consumed from the preview cache.
                      Contains live_data (from scrape) and catalog_data
                      (from prior DB lookup, may be None for new products).
            email: User email address. Will be normalised to lowercase.
        
        Returns:
            SyncResult with user, product, subscription_id, is_new_subscription,
            and price_updated flag.
        
        Note:
            run_id is None for price_history rows written here — they are
            subscription-time writes, not scheduler-run writes. See SAD §11.5.
        """
        live = snapshot.live_data
        email = email.strip().lower()

        # Step 1 — User
        user, _ = self.user_repo.get_or_create(email)

        # Step 2 — Product upsert
        product = self.product_repo.get_by_platform_and_marketplace_id(
            live.platform, live.marketplace_product_id
        )
        price_updated = False

        if product is None:
            logger.info(
                "Creating new product",
                platform=live.platform,
                marketplace_product_id=live.marketplace_product_id,
            )
            product = self.product_repo.create(
                url=live.url,
                platform=live.platform,
                marketplace_product_id=live.marketplace_product_id,
                name=live.name,
                brand=live.brand,
                image_url=live.image_url,
                current_price=live.current_price,
                availability=live.availability,
                rating=live.rating,
                review_count=live.review_count,
                seller=live.seller,
                last_checked_at=live.scraped_at,
            )
            # First-ever price — write to history, no email
            self.ph_repo.insert(
                product_id=product.product_id,
                price=live.current_price,
                scrape_status="success",
                run_id=None,
            )
        else:
            logger.info(
                "Updating existing product metadata",
                product_id=str(product.product_id),
            )
            # Step 2a — update mutable metadata fields
            self.product_repo.update_from_live_data(
                product,
                {
                    "name": live.name,
                    "brand": live.brand,
                    "image_url": live.image_url,
                    "availability": live.availability,
                    "rating": live.rating,
                    "review_count": live.review_count,
                    "seller": live.seller,
                    "last_checked_at": live.scraped_at,
                },
            )
            # Step 3 — price comparison and history write
            if product.current_price is None:
                # Product exists but was never successfully scraped by scheduler
                self.product_repo.update_current_price(product, live.current_price)
                self.ph_repo.insert(
                    product_id=product.product_id,
                    price=live.current_price,
                    scrape_status="success",
                    run_id=None,
                )
            elif live.current_price != product.current_price:
                # Price changed since last scheduler scrape
                price_updated = True
                self.product_repo.update_current_price(product, live.current_price)
                self.ph_repo.insert(
                    product_id=product.product_id,
                    price=live.current_price,
                    scrape_status="success",
                    run_id=None,
                )
            else:
                # Same price — still log for completeness
                self.ph_repo.insert(
                    product_id=product.product_id,
                    price=live.current_price,
                    scrape_status="success",
                    run_id=None,
                )

        # Step 4 — Subscription
        sub, is_new = self.sub_repo.get_or_create(user.user_id, product.product_id)

        return SyncResult(
            user=user,
            product=product,
            subscription_id=sub.subscription_id,
            is_new_subscription=is_new,
            price_updated=price_updated,
        )
```

---

### 8.4 Subscription Service

**File:** `app/services/subscription_service.py`

```python
import uuid
from sqlalchemy.orm import Session

from app.core.models import Subscription
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.product_repo import ProductRepository
from app.core.exceptions import SubscriptionNotFoundError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class UnsubscribeResult:
    """Return value from SubscriptionService.unsubscribe()."""
    def __init__(
        self,
        subscription_id: uuid.UUID,
        product_deleted: bool,
        message: str,
    ) -> None:
        self.subscription_id = subscription_id
        self.product_deleted = product_deleted
        self.message = message


class SubscriptionService:
    """
    Handles subscription deletion with product cleanup logic.
    
    When the last subscriber unsubscribes, the product record and all its
    associated price_history rows are deleted (via CASCADE). This keeps the
    catalog clean — orphaned products are never retained.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.sub_repo = SubscriptionRepository(db)
        self.product_repo = ProductRepository(db)

    def unsubscribe(
        self,
        subscription_id: uuid.UUID,
        email: str,
    ) -> UnsubscribeResult:
        """
        Remove a user's subscription. Delete the product if no subscribers remain.
        
        Args:
            subscription_id: The subscription to remove.
            email: Must match the subscription owner's email. Returns 404 if
                   mismatch (intentional — avoids confirming existence).
        
        Returns:
            UnsubscribeResult with product_deleted flag and message.
        
        Raises:
            SubscriptionNotFoundError: subscription_id does not exist, or
                                       email does not match the owner.
        """
        subscription = self.sub_repo.get_by_id(subscription_id)

        if subscription is None:
            raise SubscriptionNotFoundError(str(subscription_id))

        # Email ownership check — 404 on mismatch (see SAD §17 / API Spec §5.4)
        if subscription.user.email != email.strip().lower():
            raise SubscriptionNotFoundError(str(subscription_id))

        product_id = subscription.product_id
        self.sub_repo.delete(subscription)

        remaining = self.sub_repo.count_for_product(product_id)
        product_deleted = False

        if remaining == 0:
            product = self.product_repo.get_by_id(product_id)
            if product:
                logger.info(
                    "Deleting product — no subscribers remain",
                    product_id=str(product_id),
                )
                self.product_repo.delete(product)
                product_deleted = True

        return UnsubscribeResult(
            subscription_id=subscription_id,
            product_deleted=product_deleted,
            message=(
                "Product removed and deleted from catalog (no remaining watchers)."
                if product_deleted
                else "Product removed from your tracking list."
            ),
        )
```

---

## 9. Preview Cache

Covered in §8.2. The module-level `preview_cache` singleton is imported wherever it is needed:

```python
from app.services.preview_cache import preview_cache
```

It is also registered with APScheduler for periodic purge — see §16 (Application Entry Point).

---

## 10. URL Validator

Covered in §8.1. The `URLValidator` is instantiated once and reused:

```python
# app/services/url_validator.py — module level
url_validator = URLValidator()
```

---

## 11. Scraper Layer

### 11.1 Base Scraper and ScrapeResult

**File:** `app/scrapers/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from playwright.sync_api import Page


@dataclass
class ScrapeResult:
    """
    Structured output from a single scrape attempt.
    All fields except marketplace_product_id and current_price are optional
    because the scraper extracts what it can without failing hard on missing
    secondary fields (brand, rating, etc.).
    """
    marketplace_product_id: str
    """ASIN for Amazon, PID for Flipkart. Required — if absent, scrape fails."""
    current_price: Decimal
    """Listed price in INR. Required — if absent, scrape fails."""
    name: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None
    availability: bool = True
    rating: Optional[Decimal] = None
    review_count: Optional[int] = None
    seller: Optional[str] = None
    currency: str = "INR"


class BaseScraper(ABC):
    """
    Abstract base class for all platform-specific scrapers.
    
    Defines the contract that AmazonScraper and FlipkartScraper must fulfil.
    Each concrete scraper implements extract() for its platform.
    
    The ScraperWorker owns the Page lifecycle — it creates a fresh
    BrowserContext and Page for each job, calls extract(), and closes the
    context. The scraper never manages browser or page lifecycle directly.
    """

    @abstractmethod
    def extract(self, page: Page, url: str) -> ScrapeResult:
        """
        Navigate to url and extract all available product fields.
        
        Args:
            page: A fresh Playwright Page within an isolated BrowserContext.
                  The page has not been navigated yet when this is called.
            url: The canonical product URL to scrape.
        
        Returns:
            A ScrapeResult with at minimum marketplace_product_id and
            current_price populated.
        
        Raises:
            ScrapeBotDetectedError: Bot detection triggered — CAPTCHA, 429,
                                    or redirect to a challenge page.
            ScrapeTimeoutError: page.goto() or wait_for_selector() timed out.
            ScrapeError: Any other extraction failure (selector not found,
                         price parse error, etc.).
        """
        raise NotImplementedError

    def _parse_price(self, raw: str) -> Decimal:
        """
        Convert a price string as it appears on the page to a Decimal.
        Handles '₹69,999', '69,999.00', '₹1,29,999' (Indian number system).
        
        Args:
            raw: Raw price string scraped from the DOM.
        
        Returns:
            Decimal price value.
        
        Raises:
            ValueError: raw cannot be parsed as a numeric value.
        """
        cleaned = raw.replace("₹", "").replace(",", "").strip()
        return Decimal(cleaned)
```

---

### 11.2 Amazon Scraper

**File:** `app/scrapers/amazon.py`

```python
import re
from decimal import Decimal
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from app.scrapers.base import BaseScraper, ScrapeResult
from app.core.exceptions import (
    ScrapeBotDetectedError, ScrapeError, ScrapeTimeoutError,
)
from app.core.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# CSS selectors for Amazon India product pages.
# These are the primary selectors. Secondary selectors are fallbacks for
# alternate page layouts (e.g. refreshed storefront vs. classic).
_PRICE_SELECTORS = [
    "span.a-price-whole",
    "#priceblock_ourprice",
    "#priceblock_dealprice",
    ".a-price .a-offscreen",
]
_TITLE_SELECTOR = "#productTitle"
_BRAND_SELECTOR = "#bylineInfo"
_IMAGE_SELECTOR = "#landingImage"
_AVAILABILITY_SELECTOR = "#availability span"
_RATING_SELECTOR = "span[data-hook='rating-out-of-text']"
_REVIEW_COUNT_SELECTOR = "#acrCustomerReviewText"
_SELLER_SELECTOR = "#sellerProfileTriggerId"

_ASIN_FROM_URL_PATTERN = re.compile(r"/dp/([A-Z0-9]{10})")
_BOT_DETECTION_INDICATORS = [
    "api-services-support@amazon.com",
    "Enter the characters you see below",
    "Sorry, we just need to make sure you're not a robot",
    "captcha",
]


class AmazonScraper(BaseScraper):
    """
    Playwright-based scraper for Amazon India product pages.
    
    Navigates to the product URL, waits for the price element, then
    extracts all available product fields. Detects CAPTCHA and bot
    challenges by inspecting page title and body text before extraction.
    """

    def extract(self, page: Page, url: str) -> ScrapeResult:
        """
        Scrape a single Amazon India product page.
        
        Args:
            page: Fresh Playwright Page, pre-configured with stealth.
            url: Amazon India product URL (canonical form).
        
        Returns:
            ScrapeResult with all available fields populated.
        
        Raises:
            ScrapeBotDetectedError: Bot detection triggered.
            ScrapeTimeoutError: Page navigation or selector wait timed out.
            ScrapeError: Price or ASIN could not be extracted.
        """
        try:
            page.goto(url, timeout=settings.page_goto_timeout_ms, wait_until="domcontentloaded")
        except PlaywrightTimeout:
            raise ScrapeTimeoutError(url, "page.goto() timed out")

        self._check_for_bot_detection(page, url)

        price = self._extract_price(page, url)
        asin = self._extract_asin(page, url)
        name = self._extract_text(page, _TITLE_SELECTOR)
        brand = self._extract_brand(page)
        image_url = self._extract_attribute(page, _IMAGE_SELECTOR, "src")
        availability = self._extract_availability(page)
        rating = self._extract_rating(page)
        review_count = self._extract_review_count(page)
        seller = self._extract_text(page, _SELLER_SELECTOR)

        return ScrapeResult(
            marketplace_product_id=asin,
            current_price=price,
            name=name.strip() if name else None,
            brand=self._clean_brand(brand),
            image_url=image_url,
            availability=availability,
            rating=rating,
            review_count=review_count,
            seller=seller.strip() if seller else None,
        )

    def _check_for_bot_detection(self, page: Page, url: str) -> None:
        """
        Inspect page content for known bot-detection indicators.
        Raises ScrapeBotDetectedError before any extraction is attempted.
        
        Args:
            page: The navigated Playwright page.
            url: Product URL (for error context).
        
        Raises:
            ScrapeBotDetectedError: Bot detection found in page content.
        """
        body_text = page.inner_text("body") or ""
        for indicator in _BOT_DETECTION_INDICATORS:
            if indicator.lower() in body_text.lower():
                logger.warning("Bot detection triggered", url=url, indicator=indicator)
                raise ScrapeBotDetectedError(url, f"Bot detection: '{indicator}'")

    def _extract_price(self, page: Page, url: str) -> Decimal:
        """
        Try each price selector in order until one resolves.
        
        Args:
            page: The navigated Playwright page.
            url: Product URL (for error context).
        
        Returns:
            Decimal price value.
        
        Raises:
            ScrapeError: No price selector resolved or value could not be parsed.
        """
        for selector in _PRICE_SELECTORS:
            try:
                el = page.wait_for_selector(
                    selector, timeout=settings.page_selector_timeout_ms
                )
                if el:
                    raw = el.inner_text().strip()
                    return self._parse_price(raw)
            except (PlaywrightTimeout, ValueError):
                continue
        raise ScrapeError(url, "Could not find a price element on the page.")

    def _extract_asin(self, page: Page, url: str) -> str:
        """
        Extract ASIN from the current page URL (which may differ from the
        submitted URL after redirects) or from the page's canonical link.
        
        Args:
            page: The navigated Playwright page.
            url: Original product URL.
        
        Returns:
            10-character ASIN string.
        
        Raises:
            ScrapeError: ASIN could not be found.
        """
        # Try current URL first (most reliable)
        current_url = page.url
        match = _ASIN_FROM_URL_PATTERN.search(current_url)
        if match:
            return match.group(1)
        # Fall back to original URL
        match = _ASIN_FROM_URL_PATTERN.search(url)
        if match:
            return match.group(1)
        raise ScrapeError(url, "Could not extract ASIN from URL or page.")

    def _extract_text(self, page: Page, selector: str) -> Optional[str]:
        """Safely extract inner text from a selector. Returns None on any failure."""
        try:
            el = page.query_selector(selector)
            return el.inner_text() if el else None
        except Exception:
            return None

    def _extract_attribute(
        self, page: Page, selector: str, attribute: str
    ) -> Optional[str]:
        """Safely extract an attribute from a selector. Returns None on failure."""
        try:
            el = page.query_selector(selector)
            return el.get_attribute(attribute) if el else None
        except Exception:
            return None

    def _extract_availability(self, page: Page) -> bool:
        """
        Return True if the product is in stock, False if explicitly out of stock.
        Defaults to True when availability text is ambiguous or missing.
        """
        text = self._extract_text(page, _AVAILABILITY_SELECTOR) or ""
        return "out of stock" not in text.lower()

    def _extract_rating(self, page: Page) -> Optional[Decimal]:
        """Parse star rating, e.g. '4.5 out of 5 stars' → Decimal('4.5')."""
        text = self._extract_text(page, _RATING_SELECTOR) or ""
        match = re.search(r"(\d+\.?\d*)\s+out of", text)
        if match:
            try:
                return Decimal(match.group(1))
            except Exception:
                return None
        return None

    def _extract_review_count(self, page: Page) -> Optional[int]:
        """Parse review count, e.g. '12,483 ratings' → 12483."""
        text = self._extract_text(page, _REVIEW_COUNT_SELECTOR) or ""
        cleaned = re.sub(r"[^\d]", "", text)
        return int(cleaned) if cleaned else None

    def _clean_brand(self, raw: Optional[str]) -> Optional[str]:
        """Strip 'Visit the X Store' or 'Brand: X' prefixes from byline text."""
        if not raw:
            return None
        for prefix in ("Visit the ", " Store", "Brand: "]:
            raw = raw.replace(prefix, "")
        return raw.strip() or None
```

---

### 11.3 Flipkart Scraper

**File:** `app/scrapers/flipkart.py`

```python
import re
from decimal import Decimal
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from app.scrapers.base import BaseScraper, ScrapeResult
from app.core.exceptions import (
    ScrapeBotDetectedError, ScrapeError, ScrapeTimeoutError,
)
from app.core.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

_PRICE_SELECTORS = [
    "div._30jeq3._16Jk6d",   # primary price div
    "div._30jeq3",             # fallback
    "div[class*='_30jeq3']",  # attribute-contains fallback
]
_TITLE_SELECTOR = "span.B_NuCI"
_IMAGE_SELECTOR = "img._396cs4"
_AVAILABILITY_SELECTOR = "div._16FRp0"
_RATING_SELECTOR = "div._3LWZlK"
_REVIEW_COUNT_SELECTOR = "span._2_R_DZ"
_SELLER_SELECTOR = "div#sellerName span"

_PID_FROM_URL_PATTERN = re.compile(r"/p/([a-zA-Z0-9]+)")
_BOT_DETECTION_INDICATORS = ["unusual traffic", "captcha", "verify you are human"]


class FlipkartScraper(BaseScraper):
    """
    Playwright-based scraper for Flipkart product pages.
    
    Handles Flipkart's SPA-style rendering by waiting for the price
    element to be visible before extraction. Detects common bot signals.
    """

    def extract(self, page: Page, url: str) -> ScrapeResult:
        """
        Scrape a single Flipkart product page.
        
        Args:
            page: Fresh Playwright Page, pre-configured with stealth.
            url: Flipkart product URL (canonical form).
        
        Returns:
            ScrapeResult with all available fields populated.
        
        Raises:
            ScrapeBotDetectedError: Bot detection triggered.
            ScrapeTimeoutError: Page navigation or selector wait timed out.
            ScrapeError: Price or PID could not be extracted.
        """
        try:
            page.goto(url, timeout=settings.page_goto_timeout_ms, wait_until="domcontentloaded")
        except PlaywrightTimeout:
            raise ScrapeTimeoutError(url, "page.goto() timed out")

        self._check_for_bot_detection(page, url)

        price = self._extract_price(page, url)
        pid = self._extract_pid(page, url)
        name = self._extract_text(page, _TITLE_SELECTOR)
        image_url = self._extract_attribute(page, _IMAGE_SELECTOR, "src")
        availability = self._extract_availability(page)
        rating = self._extract_rating(page)
        review_count = self._extract_review_count(page)
        seller = self._extract_text(page, _SELLER_SELECTOR)

        return ScrapeResult(
            marketplace_product_id=pid,
            current_price=price,
            name=name.strip() if name else None,
            image_url=image_url,
            availability=availability,
            rating=rating,
            review_count=review_count,
            seller=seller.strip() if seller else None,
        )

    def _check_for_bot_detection(self, page: Page, url: str) -> None:
        body_text = page.inner_text("body") or ""
        for indicator in _BOT_DETECTION_INDICATORS:
            if indicator.lower() in body_text.lower():
                raise ScrapeBotDetectedError(url, f"Bot detection: '{indicator}'")

    def _extract_price(self, page: Page, url: str) -> Decimal:
        for selector in _PRICE_SELECTORS:
            try:
                el = page.wait_for_selector(
                    selector, timeout=settings.page_selector_timeout_ms
                )
                if el:
                    raw = el.inner_text().strip()
                    return self._parse_price(raw)
            except (PlaywrightTimeout, ValueError):
                continue
        raise ScrapeError(url, "Could not find a price element on the Flipkart page.")

    def _extract_pid(self, page: Page, url: str) -> str:
        """Extract Flipkart PID from the current page URL or original URL."""
        for candidate_url in (page.url, url):
            match = _PID_FROM_URL_PATTERN.search(candidate_url)
            if match:
                return match.group(1)
        raise ScrapeError(url, "Could not extract PID from Flipkart URL.")

    def _extract_text(self, page: Page, selector: str) -> Optional[str]:
        try:
            el = page.query_selector(selector)
            return el.inner_text() if el else None
        except Exception:
            return None

    def _extract_attribute(
        self, page: Page, selector: str, attribute: str
    ) -> Optional[str]:
        try:
            el = page.query_selector(selector)
            return el.get_attribute(attribute) if el else None
        except Exception:
            return None

    def _extract_availability(self, page: Page) -> bool:
        text = self._extract_text(page, _AVAILABILITY_SELECTOR) or ""
        return "out of stock" not in text.lower()

    def _extract_rating(self, page: Page) -> Optional[Decimal]:
        text = self._extract_text(page, _RATING_SELECTOR) or ""
        try:
            return Decimal(text.strip()) if text.strip() else None
        except Exception:
            return None

    def _extract_review_count(self, page: Page) -> Optional[int]:
        text = self._extract_text(page, _REVIEW_COUNT_SELECTOR) or ""
        cleaned = re.sub(r"[^\d]", "", text.split("Ratings")[0])
        return int(cleaned) if cleaned else None
```

---

### 11.4 ScraperAPI Fallback

**File:** `app/scrapers/scraperapi_fallback.py`

```python
import requests
from decimal import Decimal
from app.scrapers.base import ScrapeResult
from app.scrapers.amazon import AmazonScraper
from app.scrapers.flipkart import FlipkartScraper
from app.core.config import settings
from app.core.exceptions import ScrapeError
from app.utils.logging import get_logger
from playwright.sync_api import sync_playwright

logger = get_logger(__name__)

SCRAPERAPI_ENDPOINT = "http://api.scraperapi.com"


class ScraperAPIFallback:
    """
    Fallback scraper routing requests through ScraperAPI when Playwright
    is blocked by bot detection on the target marketplace.
    
    ScraperAPI handles proxy rotation and CAPTCHA solving transparently.
    Responses are rendered HTML — we pass them to the same extraction
    logic as Playwright by rendering via a Playwright page loaded with
    the HTML content directly.
    
    Free tier: 1,000 requests/month. Used only on bot-detection fallback,
    not on every scrape. Monitor via scrape_status='blocked' count.
    """

    def __init__(self) -> None:
        self._amazon = AmazonScraper()
        self._flipkart = FlipkartScraper()

    def scrape(self, url: str, platform: str) -> ScrapeResult:
        """
        Fetch rendered HTML via ScraperAPI and extract product fields.
        
        Args:
            url: Canonical product URL.
            platform: 'amazon' or 'flipkart'.
        
        Returns:
            ScrapeResult from the platform-specific extractor.
        
        Raises:
            ScrapeError: ScraperAPI returned a non-200 status or extraction
                         failed on the fetched HTML.
        """
        logger.info("Routing to ScraperAPI fallback", url=url, platform=platform)

        try:
            response = requests.get(
                SCRAPERAPI_ENDPOINT,
                params={
                    "api_key": settings.scraper_api_key,
                    "url": url,
                    "render": "true",
                },
                timeout=60,
            )
        except requests.RequestException as exc:
            raise ScrapeError(url, f"ScraperAPI request failed: {exc}")

        if response.status_code != 200:
            raise ScrapeError(
                url,
                f"ScraperAPI returned HTTP {response.status_code}",
            )

        html_content = response.text
        scraper = self._amazon if platform == "amazon" else self._flipkart

        # Load HTML into a Playwright page for extraction using the same
        # selector logic as the primary Playwright scrape path.
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.set_content(html_content, wait_until="domcontentloaded")
            try:
                result = scraper.extract(page, url)
            finally:
                context.close()
                browser.close()

        return result
```

---

## 12. Worker Layer

### 12.1 Scraper Worker

**File:** `app/workers/scraper_worker.py`

```python
import queue
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright, Browser, BrowserContext
from playwright_stealth import stealth_sync

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import ScrapeBotDetectedError, ScrapeError, ScrapeTimeoutError
from app.scrapers.amazon import AmazonScraper
from app.scrapers.flipkart import FlipkartScraper
from app.scrapers.scraperapi_fallback import ScraperAPIFallback
from app.repositories.product_repo import ProductRepository
from app.repositories.price_history_repo import PriceHistoryRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ScrapeJob:
    """
    One unit of work dequeued from scrape_queue by a ScraperWorker.
    Published by RunManager at the start of each scraper cycle.
    """
    product_id: uuid.UUID
    url: str
    platform: str
    run_id: uuid.UUID


@dataclass
class NotificationJob:
    """
    Published to email_queue by ScraperWorker when a price drop is detected.
    Consumed by EmailWorker.
    """
    product_id: uuid.UUID
    product_name: Optional[str]
    product_image_url: Optional[str]
    product_url: str
    old_price: Decimal
    new_price: Decimal
    run_id: uuid.UUID


class ScraperWorker:
    """
    Long-running worker thread that processes ScrapeJobs from scrape_queue.
    
    Each worker owns exactly one Playwright Browser instance for its lifetime.
    A fresh BrowserContext is created per job and closed after extraction,
    ensuring full cookie/storage isolation between products.
    
    On price drop: publishes a NotificationJob to email_queue.
    On failure: logs and records scrape_status in price_history, moves on.
    
    The worker loop runs until it dequeues a sentinel None value (shutdown
    signal from WorkerManager).
    """

    def __init__(
        self,
        worker_id: int,
        scrape_queue: queue.Queue,
        email_queue: queue.Queue,
    ) -> None:
        """
        Args:
            worker_id: Unique integer identifier for logging and monitoring.
            scrape_queue: Shared input queue of ScrapeJob objects.
            email_queue: Shared output queue for NotificationJob objects.
        """
        self.worker_id = worker_id
        self.scrape_queue = scrape_queue
        self.email_queue = email_queue
        self._amazon = AmazonScraper()
        self._flipkart = FlipkartScraper()
        self._fallback = ScraperAPIFallback()
        self._browser: Optional[Browser] = None

    def run(self) -> None:
        """
        Main worker loop. Launched as a daemon thread by WorkerManager.
        
        Initialises Playwright and a Chromium browser, then loops on the
        scrape_queue until a None sentinel is received.
        Playwright and browser are cleaned up in a finally block.
        """
        logger.info("Worker starting", worker_id=self.worker_id)
        with sync_playwright() as pw:
            self._browser = pw.chromium.launch(headless=True)
            try:
                self._loop()
            finally:
                self._browser.close()
                logger.info("Worker stopped", worker_id=self.worker_id)

    def _loop(self) -> None:
        """
        Inner loop: dequeue jobs and process them until sentinel received.
        A None value in the queue signals graceful shutdown.
        """
        while True:
            job = self.scrape_queue.get()
            if job is None:
                logger.info("Worker received shutdown sentinel", worker_id=self.worker_id)
                self.scrape_queue.task_done()
                break
            try:
                self._process_job(job)
            except Exception as exc:
                # Unhandled exception — log and continue. WorkerManager will
                # restart the thread if it exits due to a fatal error.
                logger.error(
                    "Unhandled exception in worker job",
                    worker_id=self.worker_id,
                    product_id=str(job.product_id),
                    error=str(exc),
                )
            finally:
                self.scrape_queue.task_done()

    def _process_job(self, job: ScrapeJob) -> None:
        """
        Process one ScrapeJob with retry logic and ScraperAPI fallback.
        Writes the result to price_history and publishes a NotificationJob
        if a price drop is detected.
        
        Args:
            job: The ScrapeJob dequeued from scrape_queue.
        """
        scraper = self._amazon if job.platform == "amazon" else self._flipkart
        last_error: Optional[Exception] = None
        result = None

        for attempt in range(1, settings.scrape_retry_limit + 1):
            context: Optional[BrowserContext] = None
            try:
                context = self._browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    locale="en-IN",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                )
                page = context.new_page()
                stealth_sync(page)
                result = scraper.extract(page, job.url)
                break  # success — exit retry loop

            except ScrapeBotDetectedError as exc:
                logger.warning(
                    "Bot detected — routing to ScraperAPI",
                    worker_id=self.worker_id,
                    product_id=str(job.product_id),
                    attempt=attempt,
                )
                last_error = exc
                # Route to ScraperAPI — counts as one attempt
                try:
                    result = self._fallback.scrape(job.url, job.platform)
                    break
                except ScrapeError as fallback_exc:
                    last_error = fallback_exc
                    break  # fallback failed — do not retry further

            except (ScrapeError, ScrapeTimeoutError) as exc:
                last_error = exc
                backoff = 2 ** attempt
                logger.warning(
                    "Scrape failed, retrying",
                    worker_id=self.worker_id,
                    product_id=str(job.product_id),
                    attempt=attempt,
                    backoff_seconds=backoff,
                    error=str(exc),
                )
                time.sleep(backoff)

            finally:
                if context:
                    context.close()

        self._write_result(job, result, last_error)

    def _write_result(
        self,
        job: ScrapeJob,
        result,
        last_error: Optional[Exception],
    ) -> None:
        """
        Persist the scrape outcome to the database and enqueue notifications.
        
        Args:
            job: Original ScrapeJob.
            result: ScrapeResult if successful, None if all attempts failed.
            last_error: The last exception encountered, for logging.
        """
        db = SessionLocal()
        try:
            product_repo = ProductRepository(db)
            ph_repo = PriceHistoryRepository(db)
            product = product_repo.get_by_id(job.product_id)

            if product is None:
                logger.error(
                    "Product not found in DB during scrape write",
                    product_id=str(job.product_id),
                )
                return

            if result is None:
                # All attempts failed
                scrape_status = (
                    "blocked"
                    if isinstance(last_error, ScrapeBotDetectedError)
                    else "failed"
                )
                ph_repo.insert(
                    product_id=job.product_id,
                    price=None,
                    scrape_status=scrape_status,
                    run_id=job.run_id,
                )
                logger.error(
                    "Scrape permanently failed",
                    product_id=str(job.product_id),
                    scrape_status=scrape_status,
                    error=str(last_error),
                )
                db.commit()
                return

            # Successful scrape — detect price drop
            old_price = product.current_price
            new_price = result.current_price
            price_dropped = (
                old_price is not None and new_price < old_price
            )

            if price_dropped:
                product_repo.update_current_price(product, new_price)
                logger.info(
                    "Price drop detected",
                    product_id=str(job.product_id),
                    old_price=str(old_price),
                    new_price=str(new_price),
                )
                self.email_queue.put(NotificationJob(
                    product_id=job.product_id,
                    product_name=product.name,
                    product_image_url=product.image_url,
                    product_url=product.url,
                    old_price=old_price,
                    new_price=new_price,
                    run_id=job.run_id,
                ))

            # Always update metadata from latest scrape
            product_repo.update_from_live_data(
                product,
                {
                    "name": result.name,
                    "brand": result.brand,
                    "image_url": result.image_url,
                    "availability": result.availability,
                    "rating": result.rating,
                    "review_count": result.review_count,
                    "seller": result.seller,
                    "last_checked_at": datetime.now(timezone.utc),
                },
            )

            ph_repo.insert(
                product_id=job.product_id,
                price=new_price,
                scrape_status="success",
                run_id=job.run_id,
            )

            db.commit()
            logger.info(
                "Scrape succeeded",
                worker_id=self.worker_id,
                product_id=str(job.product_id),
                price=str(new_price),
                price_dropped=price_dropped,
            )

        except Exception as exc:
            db.rollback()
            logger.error(
                "DB write failed after scrape",
                product_id=str(job.product_id),
                error=str(exc),
            )
        finally:
            db.close()
```

---

### 12.2 Worker Manager

**File:** `app/workers/worker_manager.py`

```python
import queue
import threading
import time
from app.workers.scraper_worker import ScraperWorker
from app.core.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class WorkerManager:
    """
    Supervisor that owns the lifecycle of all ScraperWorker threads.
    
    Spawns exactly settings.max_scraper_workers threads at start().
    Monitors thread health every settings.worker_health_check_interval seconds.
    Restarts any dead thread immediately.
    Coordinates graceful shutdown via a shutdown_event.
    
    The WorkerManager itself runs as a daemon thread spawned by main.py
    (FastAPI) or scraper_entrypoint.py (GitHub Actions).
    """

    def __init__(
        self,
        scrape_queue: queue.Queue,
        email_queue: queue.Queue,
    ) -> None:
        """
        Args:
            scrape_queue: Shared scrape job queue. Passed to each ScraperWorker.
            email_queue: Shared notification queue. Passed to each ScraperWorker.
        """
        self.scrape_queue = scrape_queue
        self.email_queue = email_queue
        self.shutdown_event = threading.Event()
        self._workers: dict[int, threading.Thread] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        """
        Spawn all worker threads and begin health monitoring.
        Called once at application startup.
        """
        for worker_id in range(settings.max_scraper_workers):
            self._spawn_worker(worker_id)

        monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="WorkerManagerMonitor",
        )
        monitor_thread.start()
        logger.info(
            "WorkerManager started",
            num_workers=settings.max_scraper_workers,
        )

    def _spawn_worker(self, worker_id: int) -> threading.Thread:
        """
        Create and start a ScraperWorker thread for the given worker_id.
        Registers the thread in the internal registry.
        
        Args:
            worker_id: Integer identifier for the worker (0-indexed).
        
        Returns:
            The newly started Thread object.
        """
        worker = ScraperWorker(
            worker_id=worker_id,
            scrape_queue=self.scrape_queue,
            email_queue=self.email_queue,
        )
        thread = threading.Thread(
            target=worker.run,
            daemon=True,
            name=f"ScraperWorker-{worker_id}",
        )
        with self._lock:
            self._workers[worker_id] = thread
        thread.start()
        logger.info("Worker spawned", worker_id=worker_id)
        return thread

    def _monitor_loop(self) -> None:
        """
        Background health-check loop.
        Polls thread liveness every worker_health_check_interval seconds.
        Restarts any thread that is no longer alive.
        Exits when shutdown_event is set.
        """
        while not self.shutdown_event.is_set():
            time.sleep(settings.worker_health_check_interval)
            with self._lock:
                for worker_id, thread in list(self._workers.items()):
                    if not thread.is_alive():
                        logger.warning(
                            "Worker thread died — restarting",
                            worker_id=worker_id,
                        )
                        self._spawn_worker(worker_id)

    def shutdown(self) -> None:
        """
        Initiate graceful shutdown.
        Sends one None sentinel per worker to unblock queue.get() calls.
        Waits up to settings.queue_drain_timeout seconds for workers to finish.
        """
        logger.info("WorkerManager shutdown initiated")
        self.shutdown_event.set()

        with self._lock:
            num_workers = len(self._workers)

        for _ in range(num_workers):
            self.scrape_queue.put(None)

        with self._lock:
            threads = list(self._workers.values())

        for thread in threads:
            thread.join(timeout=settings.queue_drain_timeout)
            if thread.is_alive():
                logger.warning(
                    "Worker did not exit within timeout",
                    thread_name=thread.name,
                )

        logger.info("WorkerManager shutdown complete")
```

---

## 13. Notification Worker

**File:** `app/workers/email_worker.py`

```python
import queue
import threading
import time
import uuid
from decimal import Decimal

from app.core.config import settings
from app.core.database import SessionLocal
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.user_repo import UserRepository
from app.repositories.notification_log_repo import NotificationLogRepository
from app.notifications.email_sender import EmailSender
from app.workers.scraper_worker import NotificationJob
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EmailWorker:
    """
    Single-threaded consumer of the email_queue.
    
    For each NotificationJob, fetches all subscriber emails for the product,
    sends one personalised price-drop email per subscriber via SendGrid,
    and records each delivery attempt in notification_log.
    
    Retry policy: up to settings.email_retry_limit attempts per recipient,
    with exponential backoff. SendGrid 4xx errors are not retried.
    """

    def __init__(self, email_queue: queue.Queue) -> None:
        """
        Args:
            email_queue: Shared notification queue produced by ScraperWorkers.
        """
        self.email_queue = email_queue
        self._sender = EmailSender()
        self._shutdown = threading.Event()

    def run(self) -> None:
        """
        Main loop. Runs as a daemon thread. Exits on None sentinel.
        """
        logger.info("EmailWorker started")
        while True:
            job = self.email_queue.get()
            if job is None:
                logger.info("EmailWorker received shutdown sentinel")
                self.email_queue.task_done()
                break
            try:
                self._process_notification(job)
            except Exception as exc:
                logger.error(
                    "Unhandled exception in EmailWorker",
                    product_id=str(job.product_id),
                    error=str(exc),
                )
            finally:
                self.email_queue.task_done()

    def _process_notification(self, job: NotificationJob) -> None:
        """
        Fan out one price-drop notification to all product subscribers.
        
        Fetches subscriber emails live from the database to ensure the list
        is current (users may have unsubscribed since the job was enqueued).
        
        Args:
            job: NotificationJob with product details and price information.
        """
        db = SessionLocal()
        try:
            sub_repo = SubscriptionRepository(db)
            nl_repo = NotificationLogRepository(db)
            user_repo = UserRepository(db)

            emails = sub_repo.get_subscriber_emails_for_product(job.product_id)
            logger.info(
                "Dispatching price drop notifications",
                product_id=str(job.product_id),
                subscriber_count=len(emails),
            )

            emails_sent = 0
            for email in emails:
                user = user_repo.get_by_email(email)
                if user is None:
                    continue

                status = self._deliver_with_retry(job, email)
                nl_repo.insert(
                    user_id=user.user_id,
                    product_id=job.product_id,
                    run_id=job.run_id,
                    old_price=job.old_price,
                    new_price=job.new_price,
                    status=status,
                )
                if status == "sent":
                    emails_sent += 1

            db.commit()
            logger.info(
                "Notification fan-out complete",
                product_id=str(job.product_id),
                emails_sent=emails_sent,
                total_subscribers=len(emails),
            )

        except Exception as exc:
            db.rollback()
            logger.error(
                "DB error during notification fan-out",
                product_id=str(job.product_id),
                error=str(exc),
            )
        finally:
            db.close()

    def _deliver_with_retry(self, job: NotificationJob, to_email: str) -> str:
        """
        Attempt to deliver one email with exponential backoff.
        
        Args:
            job: The NotificationJob containing product and price data.
            to_email: Recipient email address.
        
        Returns:
            'sent' on success, 'failed' on all retries exhausted.
        """
        for attempt in range(1, settings.email_retry_limit + 1):
            success = self._sender.send_price_drop(
                to_email=to_email,
                product_name=job.product_name or "Product",
                product_image_url=job.product_image_url,
                product_url=job.product_url,
                old_price=job.old_price,
                new_price=job.new_price,
                platform=self._infer_platform(job.product_url),
            )
            if success:
                return "sent"

            backoff = 2 ** attempt
            logger.warning(
                "Email delivery failed, retrying",
                to_email=to_email,
                attempt=attempt,
                backoff_seconds=backoff,
            )
            time.sleep(backoff)

        logger.error(
            "Email delivery permanently failed",
            to_email=to_email,
            product_id=str(job.product_id),
        )
        return "failed"

    @staticmethod
    def _infer_platform(url: str) -> str:
        """Derive platform string from URL for email template label."""
        return "amazon" if "amazon.in" in url else "flipkart"
```

---

**File:** `app/notifications/email_sender.py`

```python
from decimal import Decimal
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.core.config import settings
from app.utils.price import format_inr, calculate_drop
from app.utils.logging import get_logger
import html

logger = get_logger(__name__)


class EmailSender:
    """
    Thin wrapper around the SendGrid Python SDK.
    
    Builds the HTML and plain-text email bodies for price-drop notifications,
    then sends via the SendGrid REST API. Returns True on HTTP 202, False
    on any error. Retry logic is the responsibility of EmailWorker.
    
    Email content follows Email Template Design Spec v1.0.
    """

    def __init__(self) -> None:
        self._client = SendGridAPIClient(settings.sendgrid_api_key)

    def send_price_drop(
        self,
        to_email: str,
        product_name: str,
        product_image_url: Optional[str],
        product_url: str,
        old_price: Decimal,
        new_price: Decimal,
        platform: str,
    ) -> bool:
        """
        Send one price-drop notification email.
        
        Args:
            to_email: Recipient email address.
            product_name: Full product title (HTML-escaped internally).
            product_image_url: Product image URL. Placeholder used if None.
            product_url: Direct link to the product page.
            old_price: Price before the drop.
            new_price: Price after the drop.
            platform: 'amazon' or 'flipkart' — determines CTA label and icon.
        
        Returns:
            True if SendGrid accepted the message (HTTP 202).
            False on any exception or non-202 response.
        """
        drop_amount, drop_pct = calculate_drop(old_price, new_price)
        platform_label = "Amazon India" if platform == "amazon" else "Flipkart"
        platform_icon = "🛒" if platform == "amazon" else "🛍️"

        subject = (
            f"Price drop: {product_name[:60]} is now {format_inr(new_price)}"
        )
        html_body = self._build_html(
            product_name=product_name,
            product_image_url=product_image_url,
            product_url=product_url,
            old_price=old_price,
            new_price=new_price,
            drop_amount=drop_amount,
            drop_pct=drop_pct,
            platform_label=platform_label,
            platform_icon=platform_icon,
        )
        plain_body = self._build_plain(
            product_name=product_name,
            product_url=product_url,
            old_price=old_price,
            new_price=new_price,
            drop_amount=drop_amount,
            drop_pct=drop_pct,
            platform_label=platform_label,
        )

        message = Mail(
            from_email=(settings.email_from_address, settings.email_from_name),
            to_emails=to_email,
            subject=subject,
            html_content=html_body,
            plain_text_content=plain_body,
        )
        message.reply_to = settings.email_reply_to

        try:
            response = self._client.send(message)
            if response.status_code == 202:
                logger.info("Email sent", to=to_email, subject=subject)
                return True
            logger.error(
                "SendGrid unexpected status",
                status=response.status_code,
                to=to_email,
            )
            return False
        except Exception as exc:
            logger.error("SendGrid exception", to=to_email, error=str(exc))
            return False

    def _build_html(self, **kwargs) -> str:
        """
        Build the HTML email body string from template variables.
        Full template follows Email Template Design Spec v1.0.
        HTML-escapes product_name before injection.
        
        Returns:
            Complete HTML string for the multipart MIME message.
        """
        safe_name = html.escape(kwargs["product_name"])
        old_fmt = format_inr(kwargs["old_price"])
        new_fmt = format_inr(kwargs["new_price"])
        drop_fmt = format_inr(kwargs["drop_amount"])
        pct = round(kwargs["drop_pct"])
        img_src = kwargs.get("product_image_url") or ""
        img_block = (
            f'<img src="{img_src}" alt="{safe_name}" '
            f'style="max-width:120px;max-height:120px;object-fit:contain;" />'
            if img_src
            else '<div style="width:80px;height:80px;background:#e5e7eb;'
                 'display:flex;align-items:center;justify-content:center;">📦</div>'
        )
        major = "🔥 Major price drop!<br>" if pct >= 50 else ""

        # Inline styles follow Email Template Design Spec §6 colour palette.
        return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f3f4f6;">
<table width="100%" bgcolor="#f3f4f6" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:24px 16px;">
<table width="600" style="max-width:600px;background:#ffffff;border-radius:8px;overflow:hidden;">
  <tr><td bgcolor="#1a1a2e" style="padding:24px 32px;">
    <span style="color:#ffffff;font-size:22px;font-weight:bold;letter-spacing:1px;">
      👁️ PRICEWATCH
    </span><br>
    <span style="color:#a0a0c0;font-size:12px;text-transform:uppercase;letter-spacing:2px;">
      Price Drop Alert
    </span>
  </td></tr>
  <tr><td bgcolor="#ffffff" style="padding:32px 32px 16px;">
    <p style="color:#6b7280;font-size:15px;text-transform:uppercase;letter-spacing:2px;margin:0 0 12px;">
      Price just dropped
    </p>
    {major}
    <p style="color:#9ca3af;font-size:18px;text-decoration:line-through;margin:0;">
      {old_fmt}
    </p>
    <p style="color:#16a34a;font-size:36px;font-weight:bold;margin:4px 0;">
      {new_fmt}
    </p>
    <span style="background:#dcfce7;color:#15803d;padding:4px 10px;border-radius:999px;font-size:13px;font-weight:bold;">
      ▼ {drop_fmt} off · {pct}% drop
    </span>
  </td></tr>
  <tr><td bgcolor="#f9fafb" style="padding:24px 32px;border-top:1px solid #e5e7eb;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td width="120" valign="top">{img_block}</td>
      <td style="padding-left:16px;" valign="top">
        <p style="font-size:16px;font-weight:600;color:#111827;margin:0 0 6px;">{safe_name}</p>
        <span style="background:#e5e7eb;color:#374151;padding:2px 8px;border-radius:999px;font-size:12px;">
          {kwargs["platform_icon"]} {kwargs["platform_label"]}
        </span>
      </td>
    </tr></table>
  </td></tr>
  <tr><td bgcolor="#ffffff" style="padding:24px 32px;text-align:center;">
    <a href="{kwargs["product_url"]}"
       style="background:#1d4ed8;color:#ffffff;padding:14px 32px;border-radius:6px;
              font-size:16px;font-weight:bold;text-decoration:none;display:inline-block;">
      View on {kwargs["platform_label"]} →
    </a>
    <p style="font-size:12px;color:#6b7280;margin:12px 0 0;">
      Prices can change at any time.
    </p>
  </td></tr>
  <tr><td bgcolor="#f3f4f6" style="padding:24px 32px;border-top:1px solid #e5e7eb;text-align:center;">
    <p style="font-size:12px;color:#6b7280;margin:0;">
      You're receiving this because you're tracking {safe_name} on PriceWatch.<br>
      To stop tracking, visit your
      <a href="{settings.dashboard_url}" style="color:#4b5563;">dashboard</a>
      and remove the item.
    </p>
  </td></tr>
</table></td></tr></table>
</body></html>"""

    def _build_plain(self, **kwargs) -> str:
        """
        Build the plain-text fallback email body.
        
        Returns:
            Plain-text string for the multipart MIME message.
        """
        old_fmt = format_inr(kwargs["old_price"])
        new_fmt = format_inr(kwargs["new_price"])
        drop_fmt = format_inr(kwargs["drop_amount"])
        pct = round(kwargs["drop_pct"])
        return (
            f"PRICEWATCH — PRICE DROP ALERT\n"
            f"==============================\n\n"
            f"{kwargs['product_name']} just dropped in price!\n\n"
            f"OLD PRICE: {old_fmt}\n"
            f"NEW PRICE: {new_fmt}\n"
            f"SAVING:    {drop_fmt} ({pct}% off)\n\n"
            f"Platform: {kwargs['platform_label']}\n\n"
            f"View the product:\n{kwargs['product_url']}\n\n"
            f"---\n"
            f"You're receiving this because you're tracking this product on PriceWatch.\n"
            f"To stop tracking, visit your dashboard: {settings.dashboard_url}\n"
        )
```

---

## 14. Run Manager

**File:** `app/scheduler/run_manager.py`

```python
import queue
from app.core.database import SessionLocal
from app.repositories.product_repo import ProductRepository
from app.repositories.scheduler_run_repo import SchedulerRunRepository
from app.workers.scraper_worker import ScrapeJob
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RunManager:
    """
    Orchestrates a single price-check cycle.
    
    Executed by:
    - GitHub Actions (primary trigger): scraper_entrypoint.py calls run().
    - APScheduler fallback (in FastAPI process): calls run() via a scheduled job.
    
    Responsibilities:
    1. Create a SchedulerRun row (status='running')
    2. Fetch all products from the database
    3. Enqueue one ScrapeJob per product onto the scrape_queue
    4. Wait for the queue to drain (all jobs processed)
    5. Update the SchedulerRun row with final status and metrics
    
    The RunManager does not scrape — it only coordinates.
    """

    def __init__(self, scrape_queue: queue.Queue) -> None:
        """
        Args:
            scrape_queue: Shared input queue for ScrapeJobs.
        """
        self.scrape_queue = scrape_queue

    def run(self) -> None:
        """
        Execute one full price-check cycle.
        
        Creates a scheduler_run record, enqueues all products, waits for
        completion, and records final metrics. Handles database failures
        gracefully — a DB error marks the run as 'failed' before exiting.
        """
        db = SessionLocal()
        run = None
        try:
            run_repo = SchedulerRunRepository(db)
            product_repo = ProductRepository(db)

            run = run_repo.create()
            db.commit()
            logger.info("Scheduler run started", run_id=str(run.run_id))

            products = product_repo.get_all_for_scraping()
            total = len(products)
            logger.info("Products fetched for scraping", count=total)

            if total == 0:
                run_repo.complete(
                    run, status="completed",
                    products_total=0, products_scraped=0,
                    products_failed=0, price_drops_found=0, emails_sent=0,
                )
                db.commit()
                return

            for product in products:
                self.scrape_queue.put(ScrapeJob(
                    product_id=product.product_id,
                    url=product.url,
                    platform=product.platform,
                    run_id=run.run_id,
                ))

            # Block until all workers have called task_done()
            self.scrape_queue.join()

            # Collect metrics from price_history for this run
            metrics = self._collect_metrics(db, run.run_id, total)
            final_status = "partial" if metrics["products_failed"] > 0 else "completed"

            run_repo.complete(run, status=final_status, **metrics)
            db.commit()
            logger.info(
                "Scheduler run completed",
                run_id=str(run.run_id),
                status=final_status,
                **metrics,
            )

        except Exception as exc:
            logger.error(
                "Scheduler run failed with exception",
                run_id=str(run.run_id) if run else "N/A",
                error=str(exc),
            )
            if run:
                try:
                    run_repo = SchedulerRunRepository(db)
                    run_repo.mark_failed(run)
                    db.commit()
                except Exception:
                    pass
        finally:
            db.close()

    def _collect_metrics(
        self,
        db,
        run_id,
        total: int,
    ) -> dict:
        """
        Query price_history and notification_log to compute run metrics.
        
        Args:
            db: Active SQLAlchemy session.
            run_id: The SchedulerRun's UUID.
            total: Total products enqueued.
        
        Returns:
            Dict with keys: products_total, products_scraped, products_failed,
            price_drops_found, emails_sent.
        """
        from sqlalchemy import select, func
        from app.core.models import PriceHistory, NotificationLog

        scraped = db.scalar(
            select(func.count(PriceHistory.history_id)).where(
                PriceHistory.run_id == run_id,
                PriceHistory.scrape_status == "success",
            )
        ) or 0

        failed = db.scalar(
            select(func.count(PriceHistory.history_id)).where(
                PriceHistory.run_id == run_id,
                PriceHistory.scrape_status.in_(["failed", "blocked"]),
            )
        ) or 0

        emails_sent = db.scalar(
            select(func.count(NotificationLog.notification_id)).where(
                NotificationLog.run_id == run_id,
                NotificationLog.status == "sent",
            )
        ) or 0

        # Price drops = distinct products that had at least one notification sent
        from app.core.models import NotificationLog as NL
        drops = db.scalar(
            select(func.count(func.distinct(NL.product_id))).where(
                NL.run_id == run_id,
                NL.status == "sent",
            )
        ) or 0

        return {
            "products_total": total,
            "products_scraped": scraped,
            "products_failed": failed,
            "price_drops_found": drops,
            "emails_sent": emails_sent,
        }
```

---

## 15. API Router Layer

### 15.1 Dependencies

**File:** `app/api/dependencies.py`

```python
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings

bearer_scheme = HTTPBearer()


def verify_internal_token(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> None:
    """
    FastAPI dependency that validates the Bearer token for internal endpoints.
    Raises HTTP 401 if the token does not match settings.secret_key.
    
    Usage:
        @router.post("/trigger-run", dependencies=[Depends(verify_internal_token)])
    """
    if credentials.credentials != settings.secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid token."},
        )
```

---

### 15.2 Products Router

**File:** `app/api/v1/products.py`

```python
import uuid
from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.product import PreviewRequest, PreviewResponse, ProductOut, LiveData, CatalogData, PriceStats
from app.services.url_validator import URLValidator
from app.services.preview_cache import preview_cache, ProductSnapshot
from app.repositories.product_repo import ProductRepository
from app.core.exceptions import InvalidURLError, UnsupportedPlatformError, ScrapeBotDetectedError, ScrapeError
from app.scrapers.amazon import AmazonScraper
from app.scrapers.flipkart import FlipkartScraper
from app.utils.logging import get_logger
from app.utils.price import calculate_drop
from datetime import datetime

router = APIRouter(prefix="/products", tags=["products"])
logger = get_logger(__name__)
_validator = URLValidator()


@router.post(
    "/preview",
    response_model=PreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview a product before tracking",
)
def preview_product(
    body: PreviewRequest,
    db: Session = Depends(get_db),
) -> PreviewResponse:
    """
    Validate a product URL, scrape live data, look up existing catalog context,
    and return a preview token valid for 10 minutes.
    
    No database writes occur at this step.
    
    Raises:
        400 INVALID_URL: URL validation failed.
        400 UNSUPPORTED_PLATFORM: Domain not supported.
        502 SCRAPE_BLOCKED: Marketplace bot-detection triggered.
        502 SCRAPE_FAILED: Scrape succeeded but product data could not be extracted.
        503 SERVICE_UNAVAILABLE: Database unreachable during catalog lookup.
    """
    try:
        validated = _validator.validate(body.url)
    except InvalidURLError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_URL", "message": str(exc), "detail": exc.detail},
        )
    except UnsupportedPlatformError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "UNSUPPORTED_PLATFORM",
                "message": f"{exc.domain} is not a supported platform.",
            },
        )

    # Live scrape
    scraper = AmazonScraper() if validated.platform == "amazon" else FlipkartScraper()
    from playwright.sync_api import sync_playwright
    from playwright_stealth import stealth_sync

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(locale="en-IN")
            page = context.new_page()
            stealth_sync(page)
            try:
                result = scraper.extract(page, validated.canonical_url)
            finally:
                context.close()
                browser.close()
    except ScrapeBotDetectedError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "SCRAPE_BLOCKED", "message": "The marketplace blocked our request. Please try again."},
        )
    except ScrapeError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "SCRAPE_FAILED", "message": "Could not extract product details. Please check the URL."},
        )

    marketplace_product_id = result.marketplace_product_id or validated.marketplace_product_id
    scraped_at = datetime.now(timezone.utc)

    live_data = LiveData(
        marketplace_product_id=marketplace_product_id,
        url=validated.canonical_url,
        platform=validated.platform,
        name=result.name or "",
        brand=result.brand,
        image_url=result.image_url,
        current_price=result.current_price,
        currency="INR",
        availability=result.availability,
        rating=result.rating,
        review_count=result.review_count,
        seller=result.seller,
        scraped_at=scraped_at,
    )

    # DB lookup (read-only)
    product_repo = ProductRepository(db)
    existing = product_repo.get_by_platform_and_marketplace_id(
        validated.platform, marketplace_product_id
    )

    catalog_data = None
    is_new_product = existing is None

    if existing:
        watcher_count = product_repo.get_watcher_count(existing.product_id)
        price_stats_raw = product_repo.get_price_stats(existing.product_id)
        price_change_indicator = None
        price_change_amount = None
        if existing.current_price is not None:
            if result.current_price < existing.current_price:
                price_change_indicator = "down"
                price_change_amount = existing.current_price - result.current_price
            elif result.current_price > existing.current_price:
                price_change_indicator = "up"
                price_change_amount = result.current_price - existing.current_price
            else:
                price_change_indicator = "unchanged"

        catalog_data = CatalogData(
            product_id=existing.product_id,
            last_tracked_price=existing.current_price,
            price_change_indicator=price_change_indicator,
            price_change_amount=price_change_amount,
            last_checked_at=existing.last_checked_at,
            watcher_count=watcher_count,
            price_stats=PriceStats(**price_stats_raw) if price_stats_raw else None,
        )

    preview_id = uuid.uuid4()
    expires_at = preview_cache.make_expires_at()
    snapshot = ProductSnapshot(
        preview_id=preview_id,
        expires_at=expires_at,
        is_new_product=is_new_product,
        live_data=live_data,
        catalog_data=catalog_data,
    )
    preview_cache.store(snapshot)

    return PreviewResponse(
        preview_id=preview_id,
        expires_at=expires_at,
        is_new_product=is_new_product,
        live_data=live_data,
        catalog_data=catalog_data,
    )


@router.get(
    "/{product_id}",
    response_model=ProductOut,
    summary="Get product details",
)
def get_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ProductOut:
    """
    Retrieve full product details including watcher count and price stats.
    Used by the product details page after subscription confirmation.
    
    Raises:
        404 PRODUCT_NOT_FOUND: product_id does not exist.
    """
    product_repo = ProductRepository(db)
    product = product_repo.get_by_id(product_id)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PRODUCT_NOT_FOUND", "message": "Product not found."},
        )
    watcher_count = product_repo.get_watcher_count(product_id)
    price_stats_raw = product_repo.get_price_stats(product_id)
    return ProductOut(
        **product.__dict__,
        watcher_count=watcher_count,
        price_stats=PriceStats(**price_stats_raw) if price_stats_raw else None,
    )
```

---

### 15.3 Subscriptions Router

**File:** `app/api/v1/subscriptions.py`

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.subscription import SubscribeRequest, SubscriptionOut, DeleteSubscriptionOut
from app.schemas.product import ProductOut
from app.services.preview_cache import preview_cache
from app.services.product_sync import ProductSyncService
from app.services.subscription_service import SubscriptionService
from app.core.exceptions import (
    PreviewNotFoundError, SubscriptionNotFoundError, ScrapeError, ScrapeBotDetectedError,
)
from app.utils.logging import get_logger

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
logger = get_logger(__name__)


@router.post(
    "",
    response_model=SubscriptionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm product tracking subscription",
)
def subscribe(
    body: SubscribeRequest,
    db: Session = Depends(get_db),
) -> SubscriptionOut:
    """
    Consume a preview token and create (or confirm existing) subscription.
    
    Retrieves the cached ProductSnapshot. If expired, re-scrapes transparently.
    Runs ProductSyncService to upsert product and create subscription.
    
    Raises:
        404 PREVIEW_NOT_FOUND: preview_id not in cache and re-scrape also failed.
        400 INVALID_EMAIL: email field fails Pydantic EmailStr validation (handled by FastAPI).
        502 SCRAPE_FAILED: Re-scrape triggered by expiry but failed.
    """
    re_scraped = False
    try:
        snapshot = preview_cache.consume(str(body.preview_id))
        if snapshot.is_expired():
            raise PreviewNotFoundError(str(body.preview_id))
    except PreviewNotFoundError:
        # Transparent re-scrape on expiry
        logger.info("Preview expired — re-scraping", preview_id=str(body.preview_id))
        snapshot = _re_scrape(str(body.preview_id))
        re_scraped = True

    sync_svc = ProductSyncService(db)
    result = sync_svc.sync(snapshot, str(body.email))
    db.commit()

    product_out = ProductOut.model_validate(result.product)
    return SubscriptionOut(
        subscription_id=result.subscription_id,
        is_new_subscription=result.is_new_subscription,
        re_scraped=re_scraped,
        product=product_out,
    )


@router.delete(
    "/{subscription_id}",
    response_model=DeleteSubscriptionOut,
    summary="Remove a tracked product",
)
def unsubscribe(
    subscription_id: uuid.UUID,
    email: str = Query(..., description="Email address of the subscription owner."),
    db: Session = Depends(get_db),
) -> DeleteSubscriptionOut:
    """
    Remove a user's subscription. Deletes the product if no subscribers remain.
    
    Raises:
        404 SUBSCRIPTION_NOT_FOUND: subscription_id not found or email mismatch.
    """
    svc = SubscriptionService(db)
    try:
        result = svc.unsubscribe(subscription_id, email)
        db.commit()
    except SubscriptionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "SUBSCRIPTION_NOT_FOUND", "message": "Subscription not found."},
        )
    return DeleteSubscriptionOut(
        subscription_id=result.subscription_id,
        product_deleted=result.product_deleted,
        message=result.message,
    )


def _re_scrape(preview_id: str):
    """
    Re-scrape a product when a preview has expired.
    Raises HTTP 502 if the fresh scrape fails.
    """
    # This would re-run the full preview logic — reuse preview_product logic
    # In production, extract the shared logic to a PreviewService for reuse.
    raise HTTPException(
        status_code=502,
        detail={
            "code": "SCRAPE_FAILED",
            "message": "Could not refresh product data. Please preview again.",
        },
    )
```

---

### 15.4 Items Router

**File:** `app/api/v1/items.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.subscription import ItemsOut, ItemOut
from app.schemas.product import ProductOut
from app.repositories.user_repo import UserRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.utils.logging import get_logger

router = APIRouter(prefix="/items", tags=["items"])
logger = get_logger(__name__)


@router.get(
    "",
    response_model=ItemsOut,
    summary="Get all tracked items for an email",
)
def get_items(
    email: str = Query(..., description="User email address."),
    db: Session = Depends(get_db),
) -> ItemsOut:
    """
    Return all products tracked by the given email address.
    Returns an empty list (not 404) if the email has no tracked products.
    
    Raises:
        400 INVALID_EMAIL: Email format fails basic validation.
    """
    email = email.strip().lower()
    if "@" not in email:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_EMAIL", "message": "Please provide a valid email address."},
        )

    user_repo = UserRepository(db)
    user = user_repo.get_by_email(email)

    if user is None:
        return ItemsOut(email=email, count=0, items=[])

    sub_repo = SubscriptionRepository(db)
    subscriptions = sub_repo.get_all_for_user(user.user_id)

    items = [
        ItemOut(
            subscription_id=sub.subscription_id,
            subscribed_at=sub.created_at,
            product=ProductOut.model_validate(sub.product),
        )
        for sub in subscriptions
    ]

    return ItemsOut(email=email, count=len(items), items=items)
```

---

### 15.5 Runs and Health Routers

**File:** `app/api/v1/runs.py`

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, verify_internal_token
from app.schemas.run import RunOut, RunListOut, RunFailureItem
from app.repositories.scheduler_run_repo import SchedulerRunRepository
from app.core.models import PriceHistory, Product
from sqlalchemy import select

router = APIRouter(prefix="/runs", tags=["runs"], dependencies=[Depends(verify_internal_token)])


@router.get("", response_model=RunListOut)
def list_runs(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> RunListOut:
    """List recent scheduler runs. Requires Bearer token."""
    repo = SchedulerRunRepository(db)
    total, runs = repo.list_recent(limit=limit, offset=offset)
    return RunListOut(
        total=total, limit=limit, offset=offset,
        runs=[RunOut.model_validate(r) for r in runs],
    )


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> RunOut:
    """Get one scheduler run with failure details. Requires Bearer token."""
    repo = SchedulerRunRepository(db)
    run = repo.get_by_id(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND", "message": "Run not found."})

    failures_raw = db.execute(
        select(PriceHistory, Product.url, Product.name)
        .join(Product, PriceHistory.product_id == Product.product_id)
        .where(
            PriceHistory.run_id == run_id,
            PriceHistory.scrape_status.in_(["failed", "blocked"]),
        )
    ).all()

    failures = [
        RunFailureItem(
            product_id=row.PriceHistory.product_id,
            product_name=row.name,
            url=row.url,
            scrape_status=row.PriceHistory.scrape_status,
            checked_at=row.PriceHistory.checked_at,
        )
        for row in failures_raw
    ]
    out = RunOut.model_validate(run)
    out.failures = failures
    return out
```

---

**File:** `app/api/v1/health.py`

```python
from fastapi import APIRouter, Response, status
from sqlalchemy import text
from app.core.database import SessionLocal
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(response: Response) -> dict:
    """
    Lightweight health probe for Railway uptime monitoring.
    Checks database connectivity with a SELECT 1.
    Returns 200 if healthy, 503 if database is unreachable.
    """
    db_status = "ok"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "unreachable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "version": "1.0.0",
    }
```

---

## 16. Application Entry Point

**File:** `app/main.py`

```python
import queue
import threading
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app.api.v1 import products, subscriptions, items, runs, health
from app.api.error_handlers import register_error_handlers
from app.core.config import settings
from app.services.preview_cache import preview_cache
from app.workers.worker_manager import WorkerManager
from app.workers.email_worker import EmailWorker
from app.scheduler.run_manager import RunManager
from app.utils.logging import configure_logging

# Shared queues — module-level singletons
scrape_queue: queue.Queue = queue.Queue()
email_queue: queue.Queue = queue.Queue()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    
    Startup:
    - Configure structured logging
    - Start WorkerManager (scraper thread pool)
    - Start EmailWorker thread
    - Start APScheduler (fallback trigger + preview cache purge)
    
    Shutdown:
    - Signal WorkerManager graceful shutdown
    - Signal EmailWorker shutdown
    - Shut down APScheduler
    """
    configure_logging(settings.log_level)

    # Worker pool
    worker_manager = WorkerManager(scrape_queue, email_queue)
    worker_manager.start()

    # Email worker
    email_worker = EmailWorker(email_queue)
    email_thread = threading.Thread(
        target=email_worker.run, daemon=True, name="EmailWorker"
    )
    email_thread.start()

    # APScheduler — fallback trigger (every 4h) + cache purge (every 15m)
    scheduler = BackgroundScheduler()
    run_manager = RunManager(scrape_queue)
    scheduler.add_job(
        run_manager.run,
        trigger="cron",
        hour="*/4",
        minute=0,
        id="price_check",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        preview_cache.purge_expired,
        trigger="interval",
        minutes=15,
        id="cache_purge",
    )
    scheduler.start()

    yield  # Application is running

    # Shutdown
    scheduler.shutdown(wait=False)
    worker_manager.shutdown()
    email_queue.put(None)  # signal EmailWorker to exit
    email_thread.join(timeout=30)


def create_app() -> FastAPI:
    """
    FastAPI application factory.
    
    Returns:
        Configured FastAPI application with all routers and lifespan hooks.
    """
    app = FastAPI(
        title="PriceWatch API",
        description="Price tracking for Amazon India and Flipkart.",
        version="1.0.0",
        lifespan=lifespan,
    )

    register_error_handlers(app)

    prefix = "/v1"
    app.include_router(products.router, prefix=prefix)
    app.include_router(subscriptions.router, prefix=prefix)
    app.include_router(items.router, prefix=prefix)
    app.include_router(runs.router, prefix=prefix)
    app.include_router(health.router)

    return app


app = create_app()
```

---

**File:** `scraper_entrypoint.py`

```python
"""
GitHub Actions entry point for the scheduled scraper.

Invoked by the cron workflow every 4 hours:
    python scraper_entrypoint.py

Runs a single price-check cycle:
1. Starts a WorkerManager (3 Playwright workers)
2. Starts an EmailWorker
3. RunManager fetches all products and enqueues scrape jobs
4. Waits for all jobs to complete
5. Shuts down cleanly

Exit code 0 on success, 1 on failure (triggers GitHub Actions failure alert).
"""
import queue
import sys
import threading

from app.core.config import settings
from app.utils.logging import configure_logging
from app.workers.worker_manager import WorkerManager
from app.workers.email_worker import EmailWorker
from app.scheduler.run_manager import RunManager

def main() -> int:
    configure_logging(settings.log_level)

    scrape_queue: queue.Queue = queue.Queue()
    email_queue: queue.Queue = queue.Queue()

    worker_manager = WorkerManager(scrape_queue, email_queue)
    worker_manager.start()

    email_worker = EmailWorker(email_queue)
    email_thread = threading.Thread(
        target=email_worker.run, daemon=True, name="EmailWorker"
    )
    email_thread.start()

    try:
        run_manager = RunManager(scrape_queue)
        run_manager.run()
    except Exception as exc:
        print(f"[ERROR] Scraper run failed: {exc}", file=sys.stderr)
        return 1
    finally:
        worker_manager.shutdown()
        email_queue.put(None)
        email_thread.join(timeout=30)

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## 17. Logging Utilities

**File:** `app/utils/logging.py`

```python
import logging
import json
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.
    Compatible with Railway's log aggregation and Datadog ingestion.
    Extra keyword arguments passed to logger calls are included as top-level fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include any extra fields passed via logger.info("msg", key=value)
        for key, value in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "module", "msecs", "message", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName",
            ):
                log_obj[key] = value

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


def configure_logging(level: str = "INFO") -> None:
    """
    Configure root logger with JSONFormatter for production.
    Called once at application startup.
    
    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=getattr(logging, level.upper()), handlers=[handler])


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger. Supports structured keyword arguments via LoggerAdapter.
    
    Usage:
        logger = get_logger(__name__)
        logger.info("Scrape complete", product_id="abc", price=3499.0)
    
    Args:
        name: Logger name, typically __name__ of the calling module.
    
    Returns:
        A standard logging.Logger instance.
    """
    return logging.getLogger(name)
```

---

**File:** `app/utils/price.py`

```python
from decimal import Decimal
from typing import Tuple


def format_inr(amount: Decimal) -> str:
    """
    Format a price as Indian Rupee string with standard comma formatting.
    
    For MVP, standard international comma formatting is used.
    Phase 2 may switch to the Indian number system (e.g. ₹1,29,999).
    
    Args:
        amount: Price as Decimal.
    
    Returns:
        Formatted string, e.g. '₹69,999'.
    
    Examples:
        >>> format_inr(Decimal('69999.00'))
        '₹69,999'
        >>> format_inr(Decimal('129999.00'))
        '₹1,29,999'
    """
    return f"₹{amount:,.0f}"


def calculate_drop(
    old_price: Decimal,
    new_price: Decimal,
) -> Tuple[Decimal, float]:
    """
    Calculate the drop amount and percentage between two prices.
    
    Args:
        old_price: Price before the drop.
        new_price: Price after the drop. Must be < old_price.
    
    Returns:
        Tuple of (drop_amount, drop_pct) where drop_amount is a Decimal
        and drop_pct is a float percentage (0–100).
    
    Example:
        >>> calculate_drop(Decimal('79999'), Decimal('69999'))
        (Decimal('10000'), 12.5001...)
    """
    drop_amount = old_price - new_price
    drop_pct = float(drop_amount / old_price * 100)
    return drop_amount, drop_pct
```

---

## 18. Inter-Component Data Contracts

This section summarises what each component produces and consumes, for quick reference during implementation.

| Producer | Consumer | Data type | Transport |
|---|---|---|---|
| `RunManager` | `ScraperWorker` | `ScrapeJob` dataclass | `scrape_queue` (queue.Queue) |
| `ScraperWorker` | `EmailWorker` | `NotificationJob` dataclass | `email_queue` (queue.Queue) |
| `WorkerManager` | `ScraperWorker` | `None` sentinel | `scrape_queue` |
| `WorkerManager` | `EmailWorker` | `None` sentinel | `email_queue` |
| `POST /products/preview` | `POST /subscriptions` | `ProductSnapshot` | `PreviewCache` (in-memory dict) |
| `AmazonScraper` / `FlipkartScraper` | `ScraperWorker`, `preview_product` endpoint | `ScrapeResult` dataclass | direct return |
| `ProductSyncService` | `POST /subscriptions` router | `SyncResult` object | direct return |
| `SubscriptionService` | `DELETE /subscriptions` router | `UnsubscribeResult` object | direct return |

---

## 19. Error Handling Reference

| Exception | Raised by | Caught by | HTTP mapping |
|---|---|---|---|
| `InvalidURLError` | `URLValidator` | Products router | 400 INVALID_URL |
| `UnsupportedPlatformError` | `URLValidator` | Products router | 400 UNSUPPORTED_PLATFORM |
| `ScrapeBotDetectedError` | `AmazonScraper`, `FlipkartScraper` | Products router, `ScraperWorker` | 502 SCRAPE_BLOCKED |
| `ScrapeTimeoutError` | `AmazonScraper`, `FlipkartScraper` | `ScraperWorker` (retry) | Internal retry |
| `ScrapeError` | `AmazonScraper`, `FlipkartScraper`, `ScraperAPIFallback` | Products router, `ScraperWorker` | 502 SCRAPE_FAILED |
| `PreviewNotFoundError` | `PreviewCache.consume()` | Subscriptions router | 404 PREVIEW_NOT_FOUND |
| `SubscriptionNotFoundError` | `SubscriptionService` | Subscriptions router | 404 SUBSCRIPTION_NOT_FOUND |
| `DatabaseConnectionError` | `get_db`, repositories | Global error handler | 503 SERVICE_UNAVAILABLE |
| `EmailDeliveryError` | `EmailSender` | `EmailWorker` (retry, then log) | Not HTTP — logged to notification_log |

---

## 20. File-to-Class Index

| File | Class / Function |
|---|---|
| `app/core/config.py` | `Settings`, `get_settings()` |
| `app/core/database.py` | `Base`, `SessionLocal`, `get_db()` |
| `app/core/exceptions.py` | `PriceWatchError`, `InvalidURLError`, `UnsupportedPlatformError`, `ScrapeError`, `ScrapeBotDetectedError`, `ScrapeTimeoutError`, `PreviewNotFoundError`, `SubscriptionNotFoundError`, `DatabaseConnectionError`, `EmailDeliveryError` |
| `app/core/models.py` | `User`, `Product`, `Subscription`, `PriceHistory`, `NotificationLog`, `SchedulerRun` |
| `app/schemas/product.py` | `PreviewRequest`, `LiveData`, `PriceStats`, `CatalogData`, `PreviewResponse`, `ProductOut` |
| `app/schemas/subscription.py` | `SubscribeRequest`, `SubscriptionOut`, `ItemOut`, `ItemsOut`, `DeleteSubscriptionOut` |
| `app/schemas/run.py` | `RunFailureItem`, `RunOut`, `RunListOut` |
| `app/schemas/error.py` | `ErrorDetail`, `ErrorResponse` |
| `app/repositories/user_repo.py` | `UserRepository` |
| `app/repositories/product_repo.py` | `ProductRepository` |
| `app/repositories/subscription_repo.py` | `SubscriptionRepository` |
| `app/repositories/price_history_repo.py` | `PriceHistoryRepository` |
| `app/repositories/scheduler_run_repo.py` | `SchedulerRunRepository` |
| `app/repositories/notification_log_repo.py` | `NotificationLogRepository` |
| `app/services/url_validator.py` | `URLValidator`, `ValidatedURL` |
| `app/services/preview_cache.py` | `ProductSnapshot`, `PreviewCache`, `preview_cache` |
| `app/services/product_sync.py` | `ProductSyncService`, `SyncResult` |
| `app/services/subscription_service.py` | `SubscriptionService`, `UnsubscribeResult` |
| `app/scrapers/base.py` | `BaseScraper`, `ScrapeResult` |
| `app/scrapers/amazon.py` | `AmazonScraper` |
| `app/scrapers/flipkart.py` | `FlipkartScraper` |
| `app/scrapers/scraperapi_fallback.py` | `ScraperAPIFallback` |
| `app/workers/scraper_worker.py` | `ScrapeJob`, `NotificationJob`, `ScraperWorker` |
| `app/workers/worker_manager.py` | `WorkerManager` |
| `app/workers/email_worker.py` | `EmailWorker` |
| `app/scheduler/run_manager.py` | `RunManager` |
| `app/notifications/email_sender.py` | `EmailSender` |
| `app/api/dependencies.py` | `verify_internal_token()` |
| `app/api/v1/products.py` | `preview_product()`, `get_product()` |
| `app/api/v1/subscriptions.py` | `subscribe()`, `unsubscribe()` |
| `app/api/v1/items.py` | `get_items()` |
| `app/api/v1/runs.py` | `list_runs()`, `get_run()` |
| `app/api/v1/health.py` | `health_check()` |
| `app/main.py` | `create_app()`, `lifespan()` |
| `app/utils/logging.py` | `JSONFormatter`, `configure_logging()`, `get_logger()` |
| `app/utils/price.py` | `format_inr()`, `calculate_drop()` |
| `scraper_entrypoint.py` | `main()` |

---

*PriceWatch — Low-Level Design — v1.0 — July 2026*
*Status: Draft — MVP*
