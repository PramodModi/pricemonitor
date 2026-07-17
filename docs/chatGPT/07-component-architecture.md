# Chapter 7 -- Component Architecture

**Document Version:** 1.0\
**Project:** Price Drop Notification System\
**Document Type:** Software Architecture Document (SAD)

------------------------------------------------------------------------

# 1. Purpose

This chapter describes the internal components of the Price Drop
Notification System, their responsibilities, interactions, boundaries,
and dependencies. While the system is deployed as a **Modular
Monolith**, each module has a clearly defined responsibility and can
evolve independently.

------------------------------------------------------------------------

# 2. Design Goals

The component architecture is designed to:

-   Promote separation of concerns
-   Reduce coupling between modules
-   Maximize code reuse
-   Simplify testing
-   Support future extensibility
-   Enable independent evolution of business modules

------------------------------------------------------------------------

# 3. Component Overview

``` mermaid
flowchart TB

UI[Streamlit UI]

API[FastAPI API Layer]

PM[Product Module]
SM[Subscription Module]
SCH[Scheduler Module]
SCR[Scraper Module]
NOTIF[Notification Module]
REP[Reporting Module]

DB[(Supabase PostgreSQL)]

UI --> API

API --> PM
API --> SM
API --> REP

SCH --> SCR
SCR --> PM
SCR --> NOTIF

PM --> DB
SM --> DB
REP --> DB
SCR --> DB
NOTIF --> DB
```

------------------------------------------------------------------------

# 4. Component Responsibilities

  Component             Responsibility
  --------------------- ------------------------------------
  Streamlit UI          Dashboard and user interactions
  API Layer             Request validation and routing
  Product Module        Product lifecycle management
  Subscription Module   Manage user subscriptions
  Scheduler Module      Identify products due for scraping
  Scraper Module        Retrieve latest product data
  Notification Module   Queue and send emails
  Reporting Module      Dashboard and price history
  Database              Persistent storage

------------------------------------------------------------------------

# 5. Component Details

## 5.1 Streamlit UI

Responsibilities:

-   Add product
-   Delete tracking
-   View dashboard
-   View price history

The UI contains no business logic and communicates only with FastAPI.

------------------------------------------------------------------------

## 5.2 API Layer

Responsibilities:

-   Validate requests
-   Route requests
-   Return responses
-   Invoke business services

The API layer should remain thin and delegate business rules to domain
modules.

------------------------------------------------------------------------

## 5.3 Product Module

Responsibilities:

-   Create product
-   Update product metadata
-   Maintain current price
-   Prevent duplicate products

Primary tables:

-   Product
-   PriceHistory

------------------------------------------------------------------------

## 5.4 Subscription Module

Responsibilities:

-   Create subscription
-   Delete subscription
-   Retrieve subscriber list

Business Rule:

A product may have many subscribers.

------------------------------------------------------------------------

## 5.5 Scheduler Module

Responsibilities:

-   Periodically identify products requiring refresh
-   Create scrape jobs
-   Avoid duplicate jobs

Scheduler is triggered externally by GitHub Actions.

------------------------------------------------------------------------

## 5.6 Scraper Module

Responsibilities:

-   Launch Playwright
-   Navigate product pages
-   Extract product data
-   Validate extracted values
-   Return scrape result

Supported marketplace:

-   Amazon India (MVP)

------------------------------------------------------------------------

## 5.7 Notification Module

Responsibilities:

-   Detect price drops
-   Build email payload
-   Send notifications
-   Record notification status

Future enhancements:

-   SMS
-   WhatsApp
-   Push notifications

------------------------------------------------------------------------

## 5.8 Reporting Module

Responsibilities:

-   Dashboard queries
-   Product details
-   Price history
-   Chart data

The reporting module performs read-only operations.

------------------------------------------------------------------------

# 6. Component Interaction

``` mermaid
sequenceDiagram

participant UI
participant API
participant Product
participant Subscription
participant Scheduler
participant Scraper
participant Notification
participant DB

UI->>API: Track Product
API->>Product: Save Product
Product->>DB: Persist Product
API->>Subscription: Create Subscription
Subscription->>DB: Save Subscription

Scheduler->>Scraper: Scrape Product
Scraper->>Product: Update Price
Product->>DB: Save Price

Product->>Notification: Price Drop
Notification->>DB: Read Subscribers
Notification-->>User: Email
```

------------------------------------------------------------------------

# 7. Component Dependencies

``` mermaid
flowchart LR

UI --> API

API --> Product
API --> Subscription
API --> Reporting

Scheduler --> Scraper

Scraper --> Product

Product --> Notification

Product --> DB
Subscription --> DB
Reporting --> DB
Notification --> DB
```

Dependency rules:

-   UI never accesses the database.
-   Business modules communicate through service interfaces.
-   Database access is encapsulated within modules.
-   Reporting modules do not modify business data.

------------------------------------------------------------------------

# 8. Design Principles

-   Single Responsibility Principle
-   Loose Coupling
-   High Cohesion
-   Dependency Inversion
-   Stateless API Layer
-   Shared Product Catalog
-   Asynchronous background processing

------------------------------------------------------------------------

# 9. Error Handling Responsibilities

  Module         Error Handling
  -------------- -----------------------------------
  API            Validation errors
  Scheduler      Retry failed scheduling
  Scraper        Retry transient scraping failures
  Product        Reject invalid updates
  Notification   Retry email delivery
  Reporting      Return graceful empty responses

------------------------------------------------------------------------

# 10. Future Evolution

The modular architecture allows individual components to evolve into
separate services if required.

Possible future decomposition:

-   Product Service
-   Subscription Service
-   Scraper Service
-   Notification Service
-   Reporting Service

No major redesign of business logic is expected.

------------------------------------------------------------------------

# 11. Advantages

-   Clear separation of concerns
-   Easier maintenance
-   Better testability
-   Supports incremental development
-   Scalable architecture
-   Reusable business logic

------------------------------------------------------------------------

# 12. Chapter Summary

The component architecture divides the application into cohesive modules
with clearly defined responsibilities and interactions. This modular
approach supports the MVP's simplicity while laying the groundwork for
future scalability and independent service evolution.

------------------------------------------------------------------------

## Next Chapter

**Chapter 8 -- Database Design**
