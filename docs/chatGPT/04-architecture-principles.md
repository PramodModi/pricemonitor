# Chapter 4 -- Architecture Principles

**Document Version:** 1.0\
**Project:** Price Drop Notification System\
**Document Type:** Software Architecture Document (SAD)

------------------------------------------------------------------------

# 1. Purpose

This chapter defines the architectural principles that guide the design
and implementation of the Price Drop Notification System. These
principles ensure that the system remains simple, maintainable,
scalable, cost-effective, and extensible while meeting the objectives of
the MVP.

------------------------------------------------------------------------

# 2. Architectural Goals

The architecture has been designed with the following goals:

-   Simplicity over unnecessary complexity
-   Low operational cost
-   High maintainability
-   Reliable price monitoring
-   Easy extensibility
-   Modular design
-   Technology independence where practical
-   Cloud-native deployment

------------------------------------------------------------------------

# 3. Guiding Principles

## 3.1 Keep the MVP Simple

The MVP should solve one problem exceptionally well---tracking product
prices and notifying users of price drops.

Avoid introducing unnecessary complexity such as microservices,
distributed messaging platforms, or authentication until justified by
business needs.

------------------------------------------------------------------------

## 3.2 Shared Product Catalog

A product shall be stored only once, regardless of the number of users
tracking it.

### Benefits

-   One scrape per product
-   Lower infrastructure cost
-   Reduced storage
-   Consistent product information
-   Faster scheduler execution

``` mermaid
flowchart LR
U1[User A]
U2[User B]
U3[User C]

U1 --> P[Shared Product]
U2 --> P
U3 --> P
```

------------------------------------------------------------------------

## 3.3 Loose Coupling

Major components shall communicate through clearly defined interfaces
and database-backed queues where appropriate.

This minimizes dependencies between modules and simplifies future
enhancements.

------------------------------------------------------------------------

## 3.4 Separation of Responsibilities

Each component shall have a single, well-defined responsibility.

  Component             Responsibility
  --------------------- -----------------------------
  Streamlit             User Interface
  FastAPI               REST APIs
  Scheduler             Create scrape jobs
  Worker Manager        Manage scraper workers
  Scraper               Extract product information
  Notification Worker   Send emails
  Database              Persist data

------------------------------------------------------------------------

## 3.5 Worker-Based Processing

Long-running tasks such as scraping and email delivery shall execute
asynchronously using workers rather than blocking API requests.

Benefits:

-   Better responsiveness
-   Parallel execution
-   Improved scalability
-   Simplified retries

------------------------------------------------------------------------

## 3.6 Cost Optimization

The solution prioritizes minimizing operational cost.

Key decisions include:

-   GitHub Actions for scheduling
-   Railway hosting
-   Supabase PostgreSQL
-   Gmail SMTP for email
-   Shared product catalog
-   Scrape once per product

------------------------------------------------------------------------

## 3.7 Modularity

The system shall be organized into logical modules.

``` text
Application
├── Product Module
├── Subscription Module
├── Scheduler
├── Scraper
├── Notification
├── Dashboard
└── Infrastructure
```

This structure simplifies testing, maintenance, and future evolution.

------------------------------------------------------------------------

## 3.8 Scalability

Although the MVP targets a modest workload, the architecture should
scale by:

-   Increasing worker count
-   Running multiple application instances
-   Migrating queues to Redis or RabbitMQ
-   Replacing Gmail SMTP with Amazon SES

No major redesign should be required.

------------------------------------------------------------------------

## 3.9 Reliability

The system shall:

-   Avoid duplicate notifications
-   Preserve price history
-   Log failures
-   Support retries for transient failures

------------------------------------------------------------------------

## 3.10 Extensibility

Future features such as multiple marketplaces, authentication, and
AI-based recommendations should integrate without changing the core
architecture.

------------------------------------------------------------------------

# 4. Architectural Trade-offs

  ------------------------------------------------------------------------
  Decision                Benefit               Trade-off
  ----------------------- --------------------- --------------------------
  Streamlit UI            Rapid development     Limited UI customization

  FastAPI                 High performance      Requires Python expertise

  GitHub Actions          Low cost              Not suitable for near
  Scheduler                                     real-time polling

  Shared Product Catalog  Reduced scraping      Slightly more complex
                                                subscription model

  Gmail SMTP              Free and simple       Limited sending quota
  ------------------------------------------------------------------------

------------------------------------------------------------------------

# 5. Architecture Principles in Practice

``` mermaid
flowchart TD

A[Simple UI] --> B[FastAPI]
B --> C[Scheduler]
C --> D[Worker Manager]
D --> E[Playwright Workers]
E --> F[(PostgreSQL)]
F --> G[Notification Queue]
G --> H[Email Worker]
```

The architecture emphasizes modularity, loose coupling, and asynchronous
processing while keeping operational complexity low.

------------------------------------------------------------------------

# 6. Summary

These architecture principles provide the foundation for all subsequent
design decisions. They ensure that the MVP remains easy to build,
economical to operate, and capable of evolving into a larger platform as
new business requirements emerge.

------------------------------------------------------------------------

## Next Chapter

**Chapter 5 -- Technology Selection**
