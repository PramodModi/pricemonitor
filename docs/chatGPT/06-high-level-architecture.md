# Chapter 6 -- High-Level Architecture

**Document Version:** 1.0\
**Project:** Price Drop Notification System\
**Document Type:** Software Architecture Document (SAD)

------------------------------------------------------------------------

# 1. Purpose

This chapter describes the overall architecture of the Price Drop
Notification System. It explains how the major components interact, how
requests flow through the system, and the rationale behind the chosen
architecture.

The objective is to provide a clear system-wide view before diving into
detailed component and database design.

------------------------------------------------------------------------

# 2. Architectural Objectives

The high-level architecture has been designed to achieve the following
objectives:

-   Simple MVP architecture
-   Low operational cost
-   Modular design
-   Independent background processing
-   High maintainability
-   Easy extensibility
-   Shared product catalog
-   Efficient scraping
-   Reliable notifications

------------------------------------------------------------------------

# 3. Architecture Style

The application follows a **Modular Monolith** architecture.

Characteristics:

-   Single deployable application
-   Well-defined internal modules
-   Shared PostgreSQL database
-   REST-based APIs
-   Background worker processing
-   Clear separation of concerns

This approach minimizes deployment complexity while allowing future
migration to microservices if required.

------------------------------------------------------------------------

# 4. High-Level Architecture Diagram

``` mermaid
flowchart LR

U[User]

subgraph Presentation
S[Streamlit UI]
end

subgraph Application
A[FastAPI]
SC[Scheduler Controller]
WM[Worker Manager]
EW[Email Worker]
end

subgraph Processing
PW[Playwright Workers]
end

subgraph Data
DB[(Supabase PostgreSQL)]
end

subgraph External
GH[GitHub Actions]
AMZ[Amazon]
SMTP[Gmail SMTP]
end

U --> S
S --> A

GH --> SC
SC --> WM
WM --> PW

PW --> AMZ
PW --> DB

A --> DB

DB --> EW
EW --> SMTP
```

------------------------------------------------------------------------

# 5. Major Components

  Component              Responsibility
  ---------------------- ------------------------------------
  Streamlit              User interface
  FastAPI                Business APIs
  Scheduler Controller   Creates scrape jobs
  Worker Manager         Manages scraper workers
  Playwright Workers     Extract latest product information
  PostgreSQL             Persistent storage
  Email Worker           Sends notifications
  GitHub Actions         Periodically triggers scheduler

------------------------------------------------------------------------

# 6. End-to-End Workflow

## Step 1

User submits a product URL.

## Step 2

FastAPI validates the request.

## Step 3

Product is created or reused.

## Step 4

Subscription is created.

## Step 5

GitHub Actions invokes the scheduler.

## Step 6

Scheduler creates scraping jobs.

## Step 7

Worker Manager distributes jobs.

## Step 8

Playwright workers scrape product pages.

## Step 9

Database is updated.

## Step 10

Price history is stored.

## Step 11

Notification records are created.

## Step 12

Email Worker sends notifications.

------------------------------------------------------------------------

# 7. Sequence Diagram

``` mermaid
sequenceDiagram

participant User
participant UI
participant API
participant DB
participant Scheduler
participant Worker
participant Amazon
participant Email

User->>UI: Add Product URL
UI->>API: POST /track-product
API->>DB: Save Product & Subscription

Scheduler->>Worker: Create Jobs
Worker->>Amazon: Scrape Product
Amazon-->>Worker: Latest Price
Worker->>DB: Update Price

DB->>Email: Queue Notification
Email-->>User: Price Drop Email
```

------------------------------------------------------------------------

# 8. Data Flow

``` mermaid
flowchart TD

A[User Input]
-->B[FastAPI]

B-->C[(Product)]
B-->D[(Subscription)]

E[Scheduler]
-->F[Scraper]

F-->G[(Price History)]

G-->H[Notification Queue]

H-->I[Email Worker]

I-->J[User]
```

------------------------------------------------------------------------

# 9. Architectural Decisions

  Decision                 Rationale
  ------------------------ --------------------------------
  Modular Monolith         Simplifies deployment
  Shared Product Catalog   Avoid duplicate scraping
  GitHub Actions           Eliminates always-on scheduler
  Playwright               Reliable dynamic page scraping
  SQLAlchemy               Database abstraction
  Streamlit                Rapid MVP UI development

------------------------------------------------------------------------

# 10. Failure Handling

Potential failure scenarios include:

-   Amazon page unavailable
-   Product removed
-   Temporary network failure
-   Email delivery failure
-   Scheduler execution failure

Mitigation strategies:

-   Retry transient operations
-   Log failures
-   Continue processing remaining jobs
-   Preserve historical data
-   Avoid duplicate notifications

------------------------------------------------------------------------

# 11. Scalability Considerations

The architecture supports future growth by:

-   Increasing worker count
-   Running multiple application instances
-   Migrating queue tables to Redis/RabbitMQ
-   Replacing Gmail SMTP with Amazon SES
-   Supporting multiple marketplaces through additional scraper
    implementations

No major architectural redesign is expected for these enhancements.

------------------------------------------------------------------------

# 12. Advantages

-   Simple deployment
-   Cost-effective
-   Easy to understand
-   Modular
-   Supports background processing
-   Easy future expansion

------------------------------------------------------------------------

# 13. Limitations

-   Single deployable application
-   Database-backed queue for MVP
-   Scheduler frequency depends on GitHub Actions
-   Streamlit suited to lightweight dashboards

These limitations are acceptable for the MVP and have clear upgrade
paths.

------------------------------------------------------------------------

# 14. Chapter Summary

The High-Level Architecture establishes a modular monolithic system with
clear separation between presentation, application, processing,
persistence, and external integrations. The design emphasizes
simplicity, low cost, and maintainability while supporting future
evolution through modular components and asynchronous worker processing.

------------------------------------------------------------------------

## Next Chapter

**Chapter 7 -- Component Architecture**
