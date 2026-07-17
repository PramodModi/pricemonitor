# Price Drop Notification System - Requirements (MVP + Future Roadmap)

## 1. Project Objective

Build a web application that allows users to track the price of products
from e-commerce websites and receive an email notification whenever the
price drops.

The initial goal is to keep the application simple, reliable, and
scalable.

## 2. Scope

### Phase 1 (MVP)

-   Amazon India support
-   Email notification
-   Track product using URL + email
-   Shared product catalog (one scrape, many subscribers)
-   Store product details
-   Store price history
-   Dashboard
-   Price history chart
-   Scheduled scraping
-   Price-drop detection
-   Delete tracking

### Phase 2 (Pipeline)

-   SMS / WhatsApp / Push notifications
-   Target price alerts
-   Card discounts, coupons, cashback
-   Multiple marketplaces
-   Authentication
-   Wishlist
-   Search & filters
-   Product specs, ratings, seller info
-   AI recommendations and price prediction
-   Mobile apps and browser extension

## 3. MVP Functional Requirements

1.  Add product by URL and email.
2.  Validate supported URL.
3.  Scrape and store:
    -   Product name
    -   Platform
    -   Platform product ID
    -   URL
    -   Image
    -   Brand (if available)
    -   Current price
    -   Currency
    -   Availability
4.  Keep one product record for duplicate URLs.
5.  Allow multiple subscriptions per product.
6.  Dashboard showing image, name, current price, previous price, last
    updated.
7.  Price history page with chart.
8.  Delete subscription.
9.  Scheduler periodically scrapes prices.
10. On price drop:
    -   Update product
    -   Insert price history
    -   Notify all subscribers by email.

## 4. Database

-   Product
-   AppUser
-   Subscription
-   PriceHistory

## 5. Background Flow

Scheduler -\> Scrape -\> Compare -\> Update Product -\> Save History -\>
Queue Notification -\> Email Worker

## 6. APIs

-   POST /track-product
-   DELETE /track-product/{id}
-   GET /products
-   GET /products/{id}
-   GET /products/{id}/history

## 7. Technology

-   FastAPI
-   Streamlit
-   PostgreSQL
-   APScheduler
-   Playwright
-   Gmail SMTP/API
-   Plotly

## 8. Design Principles

-   One product, many subscribers.
-   Scrape once per product.
-   Maintain complete price history.
-   Decouple scraping from notifications.
-   Keep architecture extensible.

## 9. MVP Success Criteria

-   Track Amazon product.
-   Store product details.
-   Maintain price history.
-   Detect price drops.
-   Notify all subscribed users.
-   Display dashboard and price chart.
