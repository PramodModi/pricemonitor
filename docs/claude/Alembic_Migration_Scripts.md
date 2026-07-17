# PriceWatch — Alembic Migration Scripts

| Field      | Value                          |
|------------|--------------------------------|
| Version    | 2.0                            |
| Status     | Draft — MVP                    |
| Date       | July 2026                      |
| Depends on | SAD v1.0, LLD v1.0             |
| Supersedes | Alembic Migration Scripts v1.0 |
| Note       | No schema changes in v3.0 — catalog lookup uses existing tables |
| Change     | products table extended with marketplace_product_id, brand, rating, review_count, seller fields |

---

## Table of Contents

1. [Setup and Configuration](#1-setup-and-configuration)
2. [Migration File Naming Convention](#2-migration-file-naming-convention)
3. [Migration 001 — Create users](#3-migration-001--create-users)
4. [Migration 002 — Create products](#4-migration-002--create-products)
5. [Migration 003 — Create subscriptions](#5-migration-003--create-subscriptions)
6. [Migration 004 — Create price_history](#6-migration-004--create-price_history)
7. [Migration 005 — Create scheduler_runs](#7-migration-005--create-scheduler_runs)
8. [Migration 006 — Create notification_log](#8-migration-006--create-notification_log)
9. [Running Migrations](#9-running-migrations)
10. [Rollback Procedure](#10-rollback-procedure)
11. [Adding Future Migrations](#11-adding-future-migrations)

---

## 1. Setup and Configuration

### Directory Structure

```
pricewatch/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_create_users.py
│       ├── 002_create_products.py
│       ├── 003_create_subscriptions.py
│       ├── 004_create_price_history.py
│       ├── 005_create_scheduler_runs.py
│       └── 006_create_notification_log.py
├── alembic.ini
└── app/
    └── core/
        └── models.py
```

### alembic.ini

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### alembic/env.py

```python
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.models import Base

config = context.config

database_url = os.environ["DATABASE_URL"]
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

> `NullPool` prevents Alembic from holding open connections after migrations complete.
> Important when running from GitHub Actions where the process exits immediately after.

---

## 2. Migration File Naming Convention

```
{NNN}_{description}.py
```

- `NNN` — zero-padded sequence number starting at `001`
- Each file has a `revision` ID and a `down_revision` pointing to the previous migration
- The first migration has `down_revision = None`

---

## 3. Migration 001 — Create users

```python
# alembic/versions/001_create_users.py

"""create users table

Revision ID: 001
Revises: None
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_index("idx_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_index("idx_users_email", table_name="users")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_table("users")
```

---

## 4. Migration 002 — Create products

The products table now includes `marketplace_product_id` as the deduplication key
(ASIN for Amazon, PID for Flipkart), plus the richer metadata fields captured during
the preview scrape: `brand`, `rating`, `review_count`, `seller`.

```python
# alembic/versions/002_create_products.py

"""create products table

Revision ID: 002
Revises: 001
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Canonical URL — tracking params stripped before insert
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        # Marketplace-native product ID — ASIN for Amazon, PID for Flipkart
        # Primary deduplication key alongside platform
        sa.Column("marketplace_product_id", sa.String(100), nullable=False),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("brand", sa.String(255), nullable=True),
        sa.Column("image_url", sa.Text, nullable=True),
        # NULL until first successful scrape — set at subscription time
        sa.Column("current_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("availability", sa.Boolean, nullable=True),
        sa.Column("rating", sa.Numeric(3, 1), nullable=True),
        sa.Column("review_count", sa.Integer, nullable=True),
        sa.Column("seller", sa.String(255), nullable=True),
        sa.Column("last_checked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Canonical URL uniqueness — secondary deduplication guard
    op.create_unique_constraint("uq_products_url", "products", ["url"])

    # Primary deduplication key: platform + marketplace_product_id
    # Prevents two rows for the same Amazon ASIN submitted with different URL forms
    op.create_unique_constraint(
        "uq_products_platform_marketplace_id",
        "products",
        ["platform", "marketplace_product_id"],
    )

    op.create_index("idx_products_url", "products", ["url"])
    op.create_index("idx_products_platform", "products", ["platform"])
    op.create_index(
        "idx_products_platform_marketplace_id",
        "products",
        ["platform", "marketplace_product_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_products_platform_marketplace_id", table_name="products")
    op.drop_index("idx_products_platform", table_name="products")
    op.drop_index("idx_products_url", table_name="products")
    op.drop_constraint("uq_products_platform_marketplace_id", "products", type_="unique")
    op.drop_constraint("uq_products_url", "products", type_="unique")
    op.drop_table("products")
```

> **Why two deduplication constraints?**
> The URL constraint (`uq_products_url`) catches identical URLs. The platform +
> marketplace_product_id constraint (`uq_products_platform_marketplace_id`) catches
> the same product submitted via different URL forms — for example
> `amazon.in/dp/B0CHX1W1XY` and `amazon.in/SomeProduct/dp/B0CHX1W1XY` resolve to
> the same ASIN `B0CHX1W1XY`. Having both constraints ensures deduplication is
> robust regardless of which URL form the user submits.

---

## 5. Migration 003 — Create subscriptions

```python
# alembic/versions/003_create_subscriptions.py

"""create subscriptions table

Revision ID: 003
Revises: 002
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column(
            "subscription_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_foreign_key(
        "fk_subscriptions_user_id",
        "subscriptions", "users",
        ["user_id"], ["user_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_subscriptions_product_id",
        "subscriptions", "products",
        ["product_id"], ["product_id"],
        # RESTRICT — product deletion is handled explicitly in application logic
        # after checking subscriber count (SubscriptionService.unsubscribe)
        ondelete="RESTRICT",
    )

    # Prevent duplicate subscriptions
    op.create_unique_constraint(
        "uq_subscriptions_user_product",
        "subscriptions",
        ["user_id", "product_id"],
    )

    # Supports fan-out query: all subscribers for a product
    op.create_index("idx_subscriptions_product_id", "subscriptions", ["product_id"])


def downgrade() -> None:
    op.drop_index("idx_subscriptions_product_id", table_name="subscriptions")
    op.drop_constraint("uq_subscriptions_user_product", "subscriptions", type_="unique")
    op.drop_constraint("fk_subscriptions_product_id", "subscriptions", type_="foreignkey")
    op.drop_constraint("fk_subscriptions_user_id", "subscriptions", type_="foreignkey")
    op.drop_table("subscriptions")
```

---

## 6. Migration 004 — Create price_history

```python
# alembic/versions/004_create_price_history.py

"""create price_history table

Revision ID: 004
Revises: 003
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_history",
        sa.Column(
            "history_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("product_id", UUID(as_uuid=True), nullable=False),
        # run_id is nullable — price_history rows created at subscription time
        # have no associated scheduler run
        sa.Column("run_id", UUID(as_uuid=True), nullable=True),
        # NULL when scrape_status != 'success'
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        # 'success' | 'failed' | 'blocked'
        sa.Column("scrape_status", sa.String(20), nullable=False),
        sa.Column(
            "checked_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # CASCADE — price history is deleted when product is deleted
    op.create_foreign_key(
        "fk_price_history_product_id",
        "price_history", "products",
        ["product_id"], ["product_id"],
        ondelete="CASCADE",
    )

    # FK to scheduler_runs added in migration 005 after that table is created
    # run_id is nullable so rows inserted at subscription time (no run) are valid

    op.create_index("idx_price_history_product_id", "price_history", ["product_id"])
    op.create_index("idx_price_history_run_id", "price_history", ["run_id"])


def downgrade() -> None:
    op.drop_index("idx_price_history_run_id", table_name="price_history")
    op.drop_index("idx_price_history_product_id", table_name="price_history")
    op.drop_constraint("fk_price_history_product_id", "price_history", type_="foreignkey")
    op.drop_table("price_history")
```

> **run_id is now nullable.** When a user subscribes, the backend writes a
> `price_history` row using the preview scrape data. This row has no associated
> `scheduler_run` — it was not produced by the scheduler. Making `run_id` nullable
> accommodates both sources of price history rows: subscription-time writes and
> scheduler-run writes.

---

## 7. Migration 005 — Create scheduler_runs

```python
# alembic/versions/005_create_scheduler_runs.py

"""create scheduler_runs table and complete price_history FK

Revision ID: 005
Revises: 004
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduler_runs",
        sa.Column(
            "run_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # 'running' | 'completed' | 'partial' | 'failed'
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("products_total", sa.Integer, nullable=True),
        sa.Column("products_scraped", sa.Integer, nullable=True),
        sa.Column("products_failed", sa.Integer, nullable=True),
        sa.Column("price_drops_found", sa.Integer, nullable=True),
        sa.Column("emails_sent", sa.Integer, nullable=True),
    )

    # Now that scheduler_runs exists, complete the FK from price_history
    # Only applies to rows where run_id IS NOT NULL
    op.create_foreign_key(
        "fk_price_history_run_id",
        "price_history", "scheduler_runs",
        ["run_id"], ["run_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_price_history_run_id", "price_history", type_="foreignkey")
    op.drop_table("scheduler_runs")
```

---

## 8. Migration 006 — Create notification_log

```python
# alembic/versions/006_create_notification_log.py

"""create notification_log table

Revision ID: 006
Revises: 005
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_log",
        sa.Column(
            "notification_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("old_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("new_price", sa.Numeric(10, 2), nullable=False),
        # 'sent' | 'failed' | 'skipped'
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "sent_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_foreign_key(
        "fk_notification_log_user_id",
        "notification_log", "users",
        ["user_id"], ["user_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_notification_log_product_id",
        "notification_log", "products",
        ["product_id"], ["product_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_notification_log_run_id",
        "notification_log", "scheduler_runs",
        ["run_id"], ["run_id"],
        ondelete="RESTRICT",
    )

    # Composite index — supports Phase 3 cooldown check
    op.create_index(
        "idx_notification_log_user_product_sent",
        "notification_log",
        ["user_id", "product_id", "sent_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_notification_log_user_product_sent", table_name="notification_log")
    op.drop_constraint("fk_notification_log_run_id", "notification_log", type_="foreignkey")
    op.drop_constraint("fk_notification_log_product_id", "notification_log", type_="foreignkey")
    op.drop_constraint("fk_notification_log_user_id", "notification_log", type_="foreignkey")
    op.drop_table("notification_log")
```

---

## 9. Running Migrations

### Local Development

```bash
alembic upgrade head     # Apply all pending migrations
alembic current          # Check current state
alembic history --verbose
```

### On Railway (Production)

Migrations run automatically on every deployment via the Railway start command:

```
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

A failed migration exits with a non-zero code, aborting deployment before the new
FastAPI version starts serving traffic.

### From GitHub Actions (Scraper)

The scraper does not run migrations. Migration is the responsibility of the API
deployment only.

---

## 10. Rollback Procedure

```bash
alembic downgrade -1        # Roll back one migration
alembic downgrade 003       # Roll back to a specific revision
alembic downgrade base      # Roll back everything
```

> **Warning:** Rolling back migrations 003 or later in production causes data loss.
> Always take a Supabase snapshot before rolling back on production.

---

## 11. Adding Future Migrations

**Phase 3 example — add target_price to subscriptions:**

```python
# alembic/versions/007_add_target_price_to_subscriptions.py

"""add target_price to subscriptions

Revision ID: 007
Revises: 006
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("target_price", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "target_price")
```

**Rule:** Always commit the migration file alongside the code change that depends on it.
Never commit application code that assumes a schema change without the migration.
