# Software Architecture Document (SAD)

**Project:** Price Drop Notification System\
**Version:** 1.0 (MVP)

> This document captures the agreed high-level architecture for the MVP.

# 1. Objective

Build a low-cost, scalable web application that tracks Amazon product
prices and emails subscribers whenever a price drops.

## MVP Features

-   Track product by URL
-   Shared product catalog
-   Price history
-   Dashboard
-   Scheduled scraping
-   Email notifications
-   Delete subscription

Future phases include authentication, multiple marketplaces, target
price alerts, AI recommendations, and browser extension support.

# 2. Architecture Principles

-   One Product → Many Subscribers
-   Scrape Once Per Product
-   Stateless Scheduler
-   Queue-Based Processing
-   Managed Services First
-   Low Operational Cost
-   Cloud Agnostic

# 3. Technology Stack

  Layer         Technology
  ------------- -------------------------------
  UI            Streamlit
  Backend       FastAPI
  Database      Supabase PostgreSQL
  ORM           SQLAlchemy
  Scraper       Playwright
  Scheduler     GitHub Actions (Cron)
  Queue         Python queue.Queue
  Worker Pool   Custom Worker Manager
  Charts        Plotly
  Email         Gmail SMTP (Amazon SES later)
  Hosting       Railway
  CI/CD         GitHub Actions

# 4. High Level Architecture

``` mermaid
flowchart TB
    GH[GitHub Repository] -->|Push| RY[Railway Deployment]

    GHA[GitHub Actions Cron]
    GHA -->|POST /internal/run-scheduler| API

    subgraph Railway
        UI[Streamlit UI]
        API[FastAPI]
        WM[Worker Manager]
        SQ[Scrape Queue]
        NQ[Notification Queue]
        EW[Email Worker]
        UI --> API
        API --> SQ
        SQ --> WM
        WM --> W1[Scraper Worker 1]
        WM --> W2[Scraper Worker 2]
        WM --> W3[Scraper Worker 3]
        W1 --> PW
        W2 --> PW
        W3 --> PW
        PW[Playwright]
        PW --> Amazon[Amazon]
        W1 --> DB
        W2 --> DB
        W3 --> DB
        W1 --> NQ
        W2 --> NQ
        W3 --> NQ
        NQ --> EW
        EW --> Gmail[Gmail SMTP]
    end

    DB[(Supabase PostgreSQL)]
```

# 5. Component Responsibilities

## Streamlit

-   Product tracking UI
-   Dashboard
-   Price history visualization
-   Subscription management

## FastAPI

-   REST APIs
-   Business logic
-   Scheduler endpoint
-   Validation

## Worker Manager

-   Creates worker pool
-   Monitors workers
-   Graceful shutdown

## Scraper Workers

-   Consume scrape jobs
-   Reuse Playwright browser
-   Update product and price history
-   Queue notifications

## Email Worker

-   Consume notification queue
-   Send email
-   Persist notification log

# 6. Scheduler Flow

``` mermaid
sequenceDiagram
GitHub Actions->>FastAPI: POST /internal/run-scheduler
FastAPI->>DB: Load Products
FastAPI->>Scrape Queue: Create Jobs
Worker Manager->>Scrape Queue: Fetch Job
Worker Manager->>Playwright: Scrape Product
Playwright->>Amazon: Read Price
Worker Manager->>DB: Update Product & History
alt Price Dropped
Worker Manager->>Notification Queue: Queue Email
Notification Queue->>Email Worker: Consume
Email Worker->>Gmail SMTP: Send Email
end
```

# 7. Database Model

## AppUser

-   user_id (PK)
-   email (Unique)
-   created_at

## Product

-   product_id (PK)
-   platform
-   platform_product_id
-   canonical_url
-   title
-   brand
-   image_url
-   current_price
-   currency
-   availability
-   last_scraped
-   created_at
-   updated_at

Unique Index: (platform, platform_product_id)

## Subscription

-   subscription_id (PK)
-   product_id (FK)
-   user_id (FK)
-   active
-   created_at

## PriceHistory

-   history_id (PK)
-   product_id (FK)
-   price
-   availability
-   scraped_at

## NotificationLog

-   notification_id (PK)
-   subscription_id (FK)
-   history_id (FK)
-   status
-   sent_at
-   error_message

## SchedulerRun

-   run_id (PK)
-   started_at
-   completed_at
-   status
-   products_processed
-   notifications_sent
-   error_message

# 8. ER Diagram

``` mermaid
erDiagram
APPUSER ||--o{ SUBSCRIPTION : owns
PRODUCT ||--o{ SUBSCRIPTION : tracked_by
PRODUCT ||--o{ PRICEHISTORY : has
SUBSCRIPTION ||--o{ NOTIFICATIONLOG : generates

APPUSER {
uuid user_id PK
string email
}

PRODUCT {
uuid product_id PK
string platform
string platform_product_id
decimal current_price
}

SUBSCRIPTION {
uuid subscription_id PK
uuid user_id FK
uuid product_id FK
}

PRICEHISTORY {
uuid history_id PK
uuid product_id FK
decimal price
datetime scraped_at
}

NOTIFICATIONLOG {
uuid notification_id PK
uuid subscription_id FK
string status
}
```

# 9. Deployment

-   GitHub hosts source code.
-   Railway hosts FastAPI and Streamlit.
-   Supabase hosts PostgreSQL.
-   GitHub Actions schedules scraping.
-   Gmail SMTP sends notifications.

# 10. Future Roadmap

-   Authentication (Supabase Auth)
-   Multiple marketplaces
-   Target price alerts
-   Coupons
-   Push/WhatsApp notifications
-   AI recommendations
-   Browser extension
-   Mobile app

# 11. Key Design Decisions

  Decision                 Rationale
  ------------------------ ---------------------------------------
  Railway                  Low operational overhead
  Supabase                 Managed PostgreSQL with future Auth
  GitHub Actions           Eliminates always-on scheduler
  Playwright               Reliable JS rendering
  Worker Manager           Controlled parallelism
  In-memory Queues         Simple MVP with future migration path
  Shared Product Catalog   Scrape once for all subscribers
