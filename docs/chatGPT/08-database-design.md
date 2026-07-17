# Chapter 8 -- Database Design

**Project:** Price Drop Notification System\
**Version:** 1.0

# 1. Purpose

This chapter defines the database architecture for the MVP. The schema
is designed around the principle of **one product, many subscribers**,
ensuring a product is scraped only once while supporting multiple users.

# 2. Design Goals

-   Normalized schema
-   Shared product catalog
-   Complete price history
-   Reliable notification tracking
-   Extensible for future marketplaces
-   Optimized for read-heavy dashboard queries

# 3. Database Technology

  Item        Choice
  ----------- ---------------------
  Database    Supabase PostgreSQL
  ORM         SQLAlchemy
  Migration   Alembic
  IDs         UUID
  Timezone    UTC

# 4. Database Architecture

``` mermaid
flowchart LR
User-->Subscription
Subscription-->Product
Scheduler-->ScrapeJob
ScrapeJob-->Product
Product-->PriceHistory
Product-->NotificationQueue
NotificationQueue-->NotificationHistory
```

# 5. Entity Relationship Diagram

``` mermaid
erDiagram

APP_USER ||--o{ SUBSCRIPTION : subscribes
PRODUCT ||--o{ SUBSCRIPTION : tracked
PRODUCT ||--o{ PRICE_HISTORY : has
PRODUCT ||--o{ SCRAPE_JOB : scraped
PRODUCT ||--o{ NOTIFICATION_QUEUE : generates
NOTIFICATION_QUEUE ||--o{ NOTIFICATION_HISTORY : logs
APP_USER ||--o{ NOTIFICATION_HISTORY : receives
```

# 6. Core Entities

  Entity                 Purpose
  ---------------------- ------------------------
  app_user               Subscriber email
  product                Master product catalog
  subscription           User-product mapping
  scrape_job             Scraping work items
  price_history          Historical prices
  notification_queue     Pending notifications
  notification_history   Delivery audit

# 7. Table Summary

## app_user

-   id (UUID)
-   email (UNIQUE)
-   created_at

## product

-   id
-   platform
-   platform_product_id
-   name
-   brand
-   image_url
-   product_url
-   current_price
-   currency
-   available
-   last_scraped_at
-   created_at
-   updated_at

Unique(platform, platform_product_id)

## subscription

-   id
-   user_id
-   product_id
-   active
-   created_at

Unique(user_id, product_id)

## scrape_job

-   id
-   product_id
-   status
-   retry_count
-   scheduled_at
-   started_at
-   completed_at
-   error_message

## price_history

-   id
-   product_id
-   old_price
-   new_price
-   changed_at

## notification_queue

-   id
-   product_id
-   user_id
-   old_price
-   new_price
-   status
-   created_at

## notification_history

-   id
-   queue_id
-   sent_at
-   status
-   provider
-   error_message

# 8. Relationships

-   One User → Many Subscriptions
-   One Product → Many Subscriptions
-   One Product → Many Price History records
-   One Product → Many Scrape Jobs
-   One Product → Many Notification Queue records
-   One Queue Record → Many Delivery Attempts

# 9. Index Strategy

  Table                  Index
  ---------------------- -------------------------------
  app_user               email
  product                platform, platform_product_id
  product                last_scraped_at
  subscription           user_id, product_id
  scrape_job             status, scheduled_at
  price_history          product_id, changed_at
  notification_queue     status
  notification_history   queue_id

# 10. Data Lifecycle

``` mermaid
flowchart TD
A[Track Product]-->B[Product]
B-->C[Subscription]
D[Scheduler]-->E[Scrape Job]
E-->F[Scraper]
F-->G[Update Product]
G-->H[Price History]
H-->I[Notification Queue]
I-->J[Email Worker]
J-->K[Notification History]
```

# 11. Design Decisions

-   Shared product catalog minimizes scraping.
-   Queue tables decouple background work.
-   UUIDs simplify distributed growth.
-   History is immutable.
-   SQLAlchemy isolates application from database implementation.

# 12. Future Evolution

Future schema additions:

-   Marketplace
-   Wishlist
-   Target Price
-   Coupons
-   Authentication
-   Push Notifications
-   AI Recommendations

# 13. Summary

The database design follows a normalized, extensible architecture
centered on a shared product catalog. It supports efficient scraping,
reliable notifications, historical price analysis, and future expansion
without requiring fundamental schema redesign.
