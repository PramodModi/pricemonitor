# Chapter 3 -- Functional Requirements

**Document Version:** 1.0\
**Project:** Price Drop Notification System\
**Document Type:** Software Architecture Document (SAD)

------------------------------------------------------------------------

# 1. Purpose

This chapter defines the functional capabilities of the MVP. Functional
requirements describe what the system shall do and serve as the basis
for the architecture, API design, database design, implementation, and
testing.

------------------------------------------------------------------------

# 2. Functional Overview

The MVP provides the following core capabilities:

  ID      Capability
  ------- -----------------------------------
  FR-01   Track product by Amazon URL
  FR-02   Validate supported URLs
  FR-03   Extract and store product details
  FR-04   Maintain a shared product catalog
  FR-05   Manage subscriptions
  FR-06   Schedule price checks
  FR-07   Scrape product prices
  FR-08   Detect price changes
  FR-09   Maintain price history
  FR-10   Send email notifications
  FR-11   Display dashboard
  FR-12   Display price history

------------------------------------------------------------------------

# 3. Detailed Functional Requirements

## FR-01 Track Product

**Description**

Users shall be able to submit an Amazon product URL together with an
email address.

**Inputs**

-   Product URL
-   Email Address

**Expected Behaviour**

-   Validate URL
-   Extract product identifier
-   Create or reuse Product record
-   Create Subscription
-   Return success response

------------------------------------------------------------------------

## FR-02 Validate URL

The system shall:

-   Accept supported Amazon India URLs.
-   Reject malformed URLs.
-   Reject unsupported marketplaces.

------------------------------------------------------------------------

## FR-03 Store Product Information

The system shall maintain:

-   Product Name
-   Platform
-   Product ID
-   URL
-   Image
-   Brand
-   Price
-   Currency
-   Availability
-   Last Updated Timestamp

------------------------------------------------------------------------

## FR-04 Shared Product Catalog

One product shall exist only once in the database regardless of the
number of subscribers.

Benefits:

-   Reduced scraping
-   Lower infrastructure cost
-   Consistent history
-   Better scalability

------------------------------------------------------------------------

## FR-05 Subscription Management

Users shall be able to:

-   Subscribe to a product
-   Unsubscribe from a product
-   Re-subscribe later

Deleting a subscription must not delete the shared product if other
subscribers still exist.

------------------------------------------------------------------------

## FR-06 Scheduled Price Monitoring

The scheduler shall periodically identify products due for refresh and
create scrape jobs.

------------------------------------------------------------------------

## FR-07 Price Scraping

Scraper workers shall:

1.  Open product page.
2.  Extract latest price.
3.  Validate extraction.
4.  Return result.

------------------------------------------------------------------------

## FR-08 Price Change Detection

After scraping, the system shall compare the latest price with the
stored price.

If unchanged:

-   Update last checked timestamp.

If changed:

-   Update product record.
-   Insert price history.

If price decreased:

-   Queue email notifications.

------------------------------------------------------------------------

## FR-09 Price History

Every detected price change shall be stored with:

-   Product ID
-   Previous Price
-   Current Price
-   Timestamp

------------------------------------------------------------------------

## FR-10 Email Notification

Subscribers shall receive an email containing:

-   Product Name
-   Previous Price
-   Current Price
-   Savings
-   Product Link

Notifications are sent only for price drops.

------------------------------------------------------------------------

## FR-11 Dashboard

The dashboard shall display:

-   Product Image
-   Product Name
-   Current Price
-   Previous Price
-   Last Updated

------------------------------------------------------------------------

## FR-12 Price History Chart

Users shall be able to view historical price changes using an
interactive Plotly chart.

------------------------------------------------------------------------

# 4. Functional Workflow

``` mermaid
flowchart LR
A[User Adds Product] --> B[Validate URL]
B --> C[Create Product or Reuse Existing]
C --> D[Create Subscription]
D --> E[Scheduler]
E --> F[Scraper]
F --> G[Compare Price]
G -->|Price Drop| H[Save History]
H --> I[Queue Email]
I --> J[Notify Users]
```

# 5. Summary

These functional requirements define the expected behaviour of the MVP
and provide the foundation for the component architecture, API
contracts, database schema, and implementation roadmap.

------------------------------------------------------------------------

## Next Chapter

**Chapter 4 -- Architecture Principles**
