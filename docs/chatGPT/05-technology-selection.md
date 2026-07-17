# Chapter 5 -- Technology Selection

**Document Version:** 1.0\
**Project:** Price Drop Notification System

------------------------------------------------------------------------

# 1. Purpose

This chapter documents the technology stack selected for the MVP, the
alternatives evaluated, the rationale behind each decision, and future
replacement strategies. The goal is to choose technologies that minimize
cost while maximizing simplicity, reliability, and maintainability.

------------------------------------------------------------------------

# 2. Technology Selection Principles

The following criteria guided every technology decision:

-   Simplicity over feature richness
-   Low infrastructure cost
-   Strong community support
-   Python ecosystem compatibility
-   Ease of deployment
-   Scalability for future growth
-   Open-source preference where practical

------------------------------------------------------------------------

# 3. Final Technology Stack

  Layer       Selected Technology     Purpose
  ----------- ----------------------- -----------------------------
  UI          Streamlit               Lightweight dashboard
  Backend     FastAPI                 REST APIs
  ORM         SQLAlchemy              Database abstraction
  Database    Supabase PostgreSQL     Managed relational database
  Scraper     Playwright              Browser automation
  Scheduler   GitHub Actions (Cron)   Periodic execution
  Charts      Plotly                  Price history visualization
  Email       Gmail SMTP              Email notifications
  Hosting     Railway                 Application hosting

------------------------------------------------------------------------

# 4. Technology Evaluation

## 4.1 Backend Framework

  ------------------------------------------------------------------------
  Option                       Pros                  Cons
  ---------------------------- --------------------- ---------------------
  FastAPI ✅                   Async support,        Learning curve for
                               automatic OpenAPI,    async
                               high performance      

  Flask                        Very simple           Limited built-in API
                                                     support

  Django                       Batteries included    Heavy for MVP
  ------------------------------------------------------------------------

**Decision:** FastAPI provides the best balance of performance,
productivity, and future scalability.

------------------------------------------------------------------------

## 4.2 Frontend

  ------------------------------------------------------------------------
  Option                       Pros                  Cons
  ---------------------------- --------------------- ---------------------
  Streamlit ✅                 Rapid development,    Limited UI
                               Python only           customization

  React                        Rich UI               Separate frontend
                                                     project

  Angular                      Enterprise features   Higher complexity
  ------------------------------------------------------------------------

**Decision:** Streamlit aligns with the MVP goal of rapid delivery.

------------------------------------------------------------------------

## 4.3 Database

  ------------------------------------------------------------------------
  Option                       Pros                  Cons
  ---------------------------- --------------------- ---------------------
  Supabase PostgreSQL ✅       Managed PostgreSQL,   Depends on managed
                               web console, backups  service

  Self-hosted PostgreSQL       Full control          Operational overhead

  MySQL                        Popular               Less aligned with
                                                     PostgreSQL ecosystem
  ------------------------------------------------------------------------

**Decision:** Treat Supabase purely as managed PostgreSQL using
SQLAlchemy.

------------------------------------------------------------------------

## 4.4 Scraping

  ------------------------------------------------------------------------
  Option                       Pros                  Cons
  ---------------------------- --------------------- ---------------------
  Playwright ✅                Reliable, modern      Higher resource usage
                               browser automation    

  BeautifulSoup                Lightweight           Cannot handle dynamic
                                                     pages

  Selenium                     Mature                Slower and heavier
                                                     than Playwright
  ------------------------------------------------------------------------

------------------------------------------------------------------------

## 4.5 Scheduler

  ------------------------------------------------------------------------
  Option                       Pros                  Cons
  ---------------------------- --------------------- ---------------------
  GitHub Actions ✅            Free/low-cost, no     Limited scheduling
                               always-on scheduler   frequency

  APScheduler                  Simple                Requires continuously
                                                     running app

  Cron Server                  Flexible              Additional
                                                     infrastructure
  ------------------------------------------------------------------------

**Decision:** GitHub Actions periodically invokes an internal FastAPI
endpoint.

------------------------------------------------------------------------

## 4.6 Hosting

  ------------------------------------------------------------------------
  Option                       Pros                  Cons
  ---------------------------- --------------------- ---------------------
  Railway ✅                   Simple deployment,    Resource limits on
                               affordable            lower tiers

  Render                       Easy deployment       Cold starts on free
                                                     plans

  AWS                          Highly scalable       Operational
                                                     complexity
  ------------------------------------------------------------------------

------------------------------------------------------------------------

# 5. Technology Interaction

``` mermaid
flowchart LR
A[Streamlit] --> B[FastAPI]
B --> C[SQLAlchemy]
C --> D[(Supabase PostgreSQL)]
B --> E[Playwright]
B --> F[Gmail SMTP]
G[GitHub Actions] --> B
```

------------------------------------------------------------------------

# 6. Version Recommendations

  Component    Recommended Version
  ------------ ---------------------
  Python       3.12+
  FastAPI      Latest Stable
  SQLAlchemy   2.x
  Playwright   Latest Stable
  Streamlit    Latest Stable
  PostgreSQL   15+

------------------------------------------------------------------------

# 7. Future Evolution

As the platform grows:

-   Gmail SMTP → Amazon SES
-   GitHub Actions → Dedicated scheduler
-   PostgreSQL queue tables → Redis/RabbitMQ
-   Streamlit → React (if richer UI required)

These replacements can occur without major architectural redesign
because of the modular architecture.

------------------------------------------------------------------------

# 8. Summary

The selected technology stack emphasizes simplicity, low cost,
maintainability, and future scalability. Every component has been chosen
to deliver the MVP quickly while leaving a clear upgrade path as usage
and feature requirements increase.

------------------------------------------------------------------------

## Next Chapter

**Chapter 6 -- High-Level Architecture**
