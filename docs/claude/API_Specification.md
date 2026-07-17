# PriceWatch — API Specification

| Field      | Value                           |
|------------|---------------------------------|
| Version    | 3.0                             |
| Base URL   | `https://api.pricewatch.app/v1` |
| Status     | Draft — MVP                     |
| Date       | July 2026                       |
| Supersedes | API Specification v2.0          |
| Change     | Preview response now includes DB lookup — watcher count, price trend, last tracked price. ProductSnapshot split into live_data + catalog_data sections. |

---

## Table of Contents

1. [Conventions](#1-conventions)
2. [Authentication](#2-authentication)
3. [Error Format](#3-error-format)
4. [Error Code Reference](#4-error-code-reference)
5. [Endpoints](#5-endpoints)
   - [POST /products/preview](#51-post-productspreview)
   - [POST /subscriptions](#52-post-subscriptions)
   - [GET /items](#53-get-items)
   - [DELETE /subscriptions/{subscription_id}](#54-delete-subscriptionssubscription_id)
   - [GET /products/{product_id}](#55-get-productsproduct_id)
   - [GET /health](#56-get-health)
   - [GET /runs](#57-get-runs)
   - [GET /runs/{run_id}](#58-get-runsrun_id)
   - [POST /internal/trigger-run](#59-post-internaltrigger-run)
6. [Shared Schema Definitions](#6-shared-schema-definitions)
7. [Two-Step Flow Sequence](#7-two-step-flow-sequence)
8. [HTTP Status Code Summary](#8-http-status-code-summary)

---

## 1. Conventions

- All request and response bodies are `application/json`
- All timestamps are ISO 8601 UTC — `2026-07-14T10:30:00Z`
- All IDs are UUID v4 strings
- All prices are decimal numbers in INR — `69999.00`
- Field names use `snake_case`
- Absent optional fields are omitted from responses unless noted
- Fields that are genuinely `null` are returned as `null`, not omitted

---

## 2. Authentication

**MVP:** No authentication. User-scoped endpoints identify the user by email address.

**Internal endpoints** (`/internal/*`) require:
```
Authorization: Bearer <SECRET_KEY>
```

---

## 3. Error Format

```json
{
  "error": {
    "code": "INVALID_URL",
    "message": "The submitted URL is not a supported product page.",
    "detail": "Supported platforms: Amazon India (amazon.in), Flipkart (flipkart.com)"
  }
}
```

| Field     | Type   | Always present | Description                      |
|-----------|--------|----------------|----------------------------------|
| `code`    | string | Yes            | Machine-readable error code      |
| `message` | string | Yes            | Human-readable summary           |
| `detail`  | string | No             | Additional context when helpful  |

---

## 4. Error Code Reference

| Code                     | HTTP Status | Meaning                                                           |
|--------------------------|-------------|-------------------------------------------------------------------|
| `INVALID_URL`            | 400         | URL does not match any supported platform or product page pattern |
| `UNSUPPORTED_PLATFORM`   | 400         | Domain recognised but not yet supported                           |
| `INVALID_EMAIL`          | 400         | Email address fails format validation                             |
| `SCRAPE_FAILED`          | 502         | Live scrape attempted but product details could not be extracted  |
| `SCRAPE_BLOCKED`         | 502         | Scraper was blocked by bot detection on the marketplace           |
| `PREVIEW_NOT_FOUND`      | 404         | `preview_id` does not exist, was already used, or never created   |
| `SUBSCRIPTION_NOT_FOUND` | 404         | Subscription ID does not exist or does not belong to this user    |
| `PRODUCT_NOT_FOUND`      | 404         | Product ID does not exist                                         |
| `RUN_NOT_FOUND`          | 404         | Scheduler run ID does not exist                                   |
| `UNAUTHORIZED`           | 401         | Missing or invalid Bearer token on an internal endpoint           |
| `VALIDATION_ERROR`       | 422         | Request body fails schema validation                              |
| `INTERNAL_ERROR`         | 500         | Unhandled server error                                            |
| `SERVICE_UNAVAILABLE`    | 503         | Database unreachable                                              |

---

## 5. Endpoints

---

### 5.1 POST /products/preview

Validates the submitted URL, performs a live scrape, looks up any existing product
record in the database (read-only), and returns a combined preview. **No database
writes occur at this step.**

The scraped result and DB lookup are cached together as a `ProductSnapshot` for 10
minutes, keyed by `preview_id`. This token is passed to `POST /subscriptions` to
complete the flow without re-scraping.

**Steps executed (all read-only):**
1. Validate URL and detect platform
2. Live scrape via Playwright — extract all product fields
3. Extract `marketplace_product_id` (ASIN / PID) from scrape result
4. DB lookup: find existing product by `platform` + `marketplace_product_id`
5. If found: read `current_price`, `watcher_count`, and `price_history` stats
6. Assemble and cache `ProductSnapshot`
7. Return preview response

**Request**

```
POST /v1/products/preview
Content-Type: application/json
```

```json
{
  "url": "https://www.amazon.in/Apple-iPhone-15-128GB-Black/dp/B0CHX1W1XY"
}
```

| Field | Type   | Required | Constraints                                              |
|-------|--------|----------|----------------------------------------------------------|
| `url` | string | Yes      | Must be a valid Amazon India or Flipkart product page URL|

---

**Response — 200 OK (product exists in catalog)**

```json
{
  "preview_id": "f8b9d2a1-4c3e-4f2d-9b1a-8e7f6d5c4b3a",
  "expires_at": "2026-07-14T10:40:00Z",
  "is_new_product": false,
  "live_data": {
    "marketplace_product_id": "B0CHX1W1XY",
    "url": "https://www.amazon.in/Apple-iPhone-15-128GB-Black/dp/B0CHX1W1XY",
    "platform": "amazon",
    "name": "Apple iPhone 15 (128 GB) - Black",
    "brand": "Apple",
    "image_url": "https://m.media-amazon.com/images/I/example.jpg",
    "current_price": 67999.00,
    "currency": "INR",
    "availability": true,
    "rating": 4.5,
    "review_count": 12483,
    "seller": "Appario Retail Private Ltd",
    "scraped_at": "2026-07-14T10:30:00Z"
  },
  "catalog_data": {
    "product_id": "f1e2d3c4-b5a6-7890-fedc-ba9876543210",
    "last_tracked_price": 69999.00,
    "price_change_indicator": "down",
    "price_change_amount": 2000.00,
    "last_checked_at": "2026-07-14T06:00:00Z",
    "watcher_count": 12,
    "price_stats": {
      "all_time_low": 62999.00,
      "all_time_high": 79999.00,
      "drop_count": 5,
      "first_tracked_at": "2026-05-01T00:00:00Z"
    }
  }
}
```

**Response — 200 OK (product not yet in catalog)**

```json
{
  "preview_id": "a1b2c3d4-5e6f-7890-abcd-ef1234567890",
  "expires_at": "2026-07-14T10:40:00Z",
  "is_new_product": true,
  "live_data": {
    "marketplace_product_id": "B0CHX1W1XY",
    "url": "https://www.amazon.in/Apple-iPhone-15-128GB-Black/dp/B0CHX1W1XY",
    "platform": "amazon",
    "name": "Apple iPhone 15 (128 GB) - Black",
    "brand": "Apple",
    "image_url": "https://m.media-amazon.com/images/I/example.jpg",
    "current_price": 67999.00,
    "currency": "INR",
    "availability": true,
    "rating": 4.5,
    "review_count": 12483,
    "seller": "Appario Retail Private Ltd",
    "scraped_at": "2026-07-14T10:30:00Z"
  },
  "catalog_data": null
}
```

---

**Response Fields**

| Field                               | Type    | Nullable | Description                                                          |
|-------------------------------------|---------|----------|----------------------------------------------------------------------|
| `preview_id`                        | UUID    | No       | Token passed to `POST /subscriptions`                                |
| `expires_at`                        | string  | No       | ISO 8601 UTC — 10 minutes from scrape time                           |
| `is_new_product`                    | boolean | No       | `true` if no existing DB record found for this marketplace product ID|
| `live_data`                         | object  | No       | Always present — from live scrape                                    |
| `live_data.marketplace_product_id`  | string  | No       | ASIN for Amazon, PID for Flipkart                                    |
| `live_data.url`                     | string  | No       | Canonical URL (tracking params stripped)                             |
| `live_data.platform`                | string  | No       | `"amazon"` or `"flipkart"`                                           |
| `live_data.name`                    | string  | No       | Full product title as scraped                                        |
| `live_data.brand`                   | string  | Yes      | `null` if not found on page                                          |
| `live_data.image_url`               | string  | Yes      | Primary product image URL                                            |
| `live_data.current_price`           | number  | No       | Live price in INR at scrape time                                     |
| `live_data.currency`                | string  | No       | Always `"INR"` in MVP                                                |
| `live_data.availability`            | boolean | No       | `true` = in stock                                                    |
| `live_data.rating`                  | number  | Yes      | Star rating — `null` if not on page                                  |
| `live_data.review_count`            | integer | Yes      | Number of reviews — `null` if not on page                            |
| `live_data.seller`                  | string  | Yes      | Seller name — `null` if not on page                                  |
| `live_data.scraped_at`              | string  | No       | ISO 8601 UTC timestamp of scrape                                     |
| `catalog_data`                      | object  | Yes      | `null` if `is_new_product = true`                                    |
| `catalog_data.product_id`           | UUID    | No       | Existing DB product ID                                               |
| `catalog_data.last_tracked_price`   | number  | Yes      | `current_price` from DB — `null` if never scraped by scheduler       |
| `catalog_data.price_change_indicator`| string | Yes     | `"up"`, `"down"`, or `"unchanged"` — compares live vs last tracked   |
| `catalog_data.price_change_amount`  | number  | Yes      | Absolute difference — `null` if no prior price                       |
| `catalog_data.last_checked_at`      | string  | Yes      | When scheduler last checked this product                             |
| `catalog_data.watcher_count`        | integer | No       | Number of active subscribers                                         |
| `catalog_data.price_stats`          | object  | Yes      | `null` if no price history exists yet                                |
| `catalog_data.price_stats.all_time_low`  | number | No  | Lowest price ever recorded in `price_history`                        |
| `catalog_data.price_stats.all_time_high` | number | No  | Highest price ever recorded in `price_history`                       |
| `catalog_data.price_stats.drop_count`    | integer| No  | Number of price drop events recorded                                 |
| `catalog_data.price_stats.first_tracked_at` | string| No | When this product was first added to the catalog                   |

---

**`price_change_indicator` logic**

| Condition                                           | Value         |
|-----------------------------------------------------|---------------|
| `live_price < last_tracked_price`                   | `"down"`      |
| `live_price > last_tracked_price`                   | `"up"`        |
| `live_price == last_tracked_price`                  | `"unchanged"` |
| `last_tracked_price` is null (never scraped by scheduler) | `null`  |

---

**Error Responses**

| Scenario                        | Status | Code                   | Message                                                    |
|---------------------------------|--------|------------------------|------------------------------------------------------------|
| URL fails pattern validation    | 400    | `INVALID_URL`          | "The submitted URL is not a supported product page."       |
| Domain not in supported list    | 400    | `UNSUPPORTED_PLATFORM` | "croma.com is not a supported platform."                   |
| Missing url field               | 422    | `VALIDATION_ERROR`     | "Field 'url' is required."                                 |
| Scraper blocked by marketplace  | 502    | `SCRAPE_BLOCKED`       | "The marketplace blocked our request. Please try again."   |
| Scraper failed to extract price | 502    | `SCRAPE_FAILED`        | "Could not extract product details. Please check the URL." |
| Database unavailable            | 503    | `SERVICE_UNAVAILABLE`  | "Service temporarily unavailable. Try again shortly."      |

> **Note:** A database failure during the lookup step (step 4) does not fail the entire
> preview. The scrape result is still returned with `catalog_data: null` and
> `is_new_product: true`. The lookup is best-effort — the scrape is the critical path.

---

### 5.2 POST /subscriptions

Retrieves the cached `ProductSnapshot`, runs `ProductSyncService` to upsert the product
and synchronise price, then creates the subscription.

If the cache has expired, the backend re-scrapes and re-runs the DB lookup transparently.
The user waits slightly longer but sees no error.

If the user is already subscribed, the endpoint silently succeeds and returns the
existing subscription.

**Request**

```
POST /v1/subscriptions
Content-Type: application/json
```

```json
{
  "preview_id": "f8b9d2a1-4c3e-4f2d-9b1a-8e7f6d5c4b3a",
  "email": "user@example.com"
}
```

| Field        | Type   | Required | Constraints                               |
|--------------|--------|----------|-------------------------------------------|
| `preview_id` | UUID   | Yes      | Must reference a cached `ProductSnapshot` |
| `email`      | string | Yes      | Valid email format. Stored lowercase.     |

---

**ProductSyncService logic (executed in order):**

1. Retrieve `ProductSnapshot` from cache by `preview_id`
2. If expired → re-scrape + re-lookup, create new snapshot, proceed
3. Get or create `User` by email
4. Find existing `Product` by `platform` + `marketplace_product_id`
5. If not found → create `Product` using `live_data` fields
6. If found → update all fields from `live_data` (`name`, `brand`, `image_url`,
   `availability`, `rating`, `review_count`, `seller`, `last_checked_at`)
7. Compare `live_data.current_price` with `products.current_price`:
   - If different → update `products.current_price`, insert `price_history` row
   - If same → insert `price_history` row with `scrape_status = 'success'`
   - Note: `run_id` is `null` for these rows — they are subscription-time writes
8. Get or create `Subscription` for (`user_id`, `product_id`) — silent on duplicate
9. Discard cache entry
10. Return subscription + full synced product

---

**Response — 201 Created**

```json
{
  "subscription_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "is_new_subscription": true,
  "re_scraped": false,
  "product": {
    "product_id": "f1e2d3c4-b5a6-7890-fedc-ba9876543210",
    "marketplace_product_id": "B0CHX1W1XY",
    "url": "https://www.amazon.in/Apple-iPhone-15-128GB-Black/dp/B0CHX1W1XY",
    "platform": "amazon",
    "name": "Apple iPhone 15 (128 GB) - Black",
    "brand": "Apple",
    "image_url": "https://m.media-amazon.com/images/I/example.jpg",
    "current_price": 67999.00,
    "currency": "INR",
    "availability": true,
    "rating": 4.5,
    "review_count": 12483,
    "seller": "Appario Retail Private Ltd",
    "last_checked_at": "2026-07-14T10:30:00Z",
    "created_at": "2026-07-14T10:30:00Z"
  }
}
```

| Field                 | Type    | Nullable | Description                                                       |
|-----------------------|---------|----------|-------------------------------------------------------------------|
| `subscription_id`     | UUID    | No       | New or existing subscription ID                                   |
| `is_new_subscription` | boolean | No       | `false` if user was already subscribed — silently succeeded       |
| `re_scraped`          | boolean | No       | `true` if preview had expired and a fresh scrape was performed    |
| `product`             | object  | No       | Full product record as now stored in DB — use `product_id` for `GET /products/{id}` |

---

**Error Responses**

| Scenario                         | Status | Code                | Message                                              |
|----------------------------------|--------|---------------------|------------------------------------------------------|
| `preview_id` not found           | 404    | `PREVIEW_NOT_FOUND` | "Preview not found. Please search again."            |
| Email format invalid             | 400    | `INVALID_EMAIL`     | "Please provide a valid email address."              |
| Re-scrape failed (expired cache) | 502    | `SCRAPE_FAILED`     | "Could not refresh product data. Please preview again."|
| Missing required field           | 422    | `VALIDATION_ERROR`  | "Field 'email' is required."                         |
| Database unavailable             | 503    | `SERVICE_UNAVAILABLE`| "Service temporarily unavailable."                  |

---

### 5.3 GET /items

Retrieve all products tracked by a given email address.

**Request**

```
GET /v1/items?email=user@example.com
```

**Response — 200 OK**

```json
{
  "email": "user@example.com",
  "count": 1,
  "items": [
    {
      "subscription_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "subscribed_at": "2026-07-01T08:00:00Z",
      "product": {
        "product_id": "f1e2d3c4-b5a6-7890-fedc-ba9876543210",
        "marketplace_product_id": "B0CHX1W1XY",
        "url": "https://www.amazon.in/Apple-iPhone-15-128GB-Black/dp/B0CHX1W1XY",
        "platform": "amazon",
        "name": "Apple iPhone 15 (128 GB) - Black",
        "brand": "Apple",
        "image_url": "https://m.media-amazon.com/images/I/example.jpg",
        "current_price": 67999.00,
        "currency": "INR",
        "availability": true,
        "rating": 4.5,
        "review_count": 12483,
        "seller": "Appario Retail Private Ltd",
        "last_checked_at": "2026-07-14T06:00:00Z"
      }
    }
  ]
}
```

**Response — 200 OK (no items)**

```json
{ "email": "newuser@example.com", "count": 0, "items": [] }
```

**Error Responses**

| Scenario            | Status | Code               | Message                                  |
|---------------------|--------|--------------------|------------------------------------------|
| Email param missing | 422    | `VALIDATION_ERROR` | "Query parameter 'email' is required."   |
| Email format invalid| 400    | `INVALID_EMAIL`    | "Please provide a valid email address."  |

---

### 5.4 DELETE /subscriptions/{subscription_id}

Remove a tracked product. If this is the last subscription for that product, the
product record and all associated price history are cascade-deleted.

**Request**

```
DELETE /v1/subscriptions/{subscription_id}?email=user@example.com
```

**Response — 200 OK**

```json
{
  "subscription_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "product_deleted": false,
  "message": "Product removed from your tracking list."
}
```

**Response — 200 OK (last subscriber)**

```json
{
  "subscription_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "product_deleted": true,
  "message": "Product removed and deleted from catalog (no remaining watchers)."
}
```

**Error Responses**

| Scenario                    | Status | Code                     | Message                                  |
|-----------------------------|--------|--------------------------|------------------------------------------|
| Subscription not found      | 404    | `SUBSCRIPTION_NOT_FOUND` | "Subscription not found."                |
| Email does not match owner  | 404    | `SUBSCRIPTION_NOT_FOUND` | "Subscription not found."                |
| Email param missing         | 422    | `VALIDATION_ERROR`       | "Query parameter 'email' is required."   |

> Email mismatch intentionally returns `404` not `403` — avoids confirming that
> a subscription ID exists but belongs to someone else.

---

### 5.5 GET /products/{product_id}

Full product detail including price stats. Used by the product details page after subscription.

**Request**

```
GET /v1/products/{product_id}
```

**Response — 200 OK**

```json
{
  "product_id": "f1e2d3c4-b5a6-7890-fedc-ba9876543210",
  "marketplace_product_id": "B0CHX1W1XY",
  "url": "https://www.amazon.in/Apple-iPhone-15-128GB-Black/dp/B0CHX1W1XY",
  "platform": "amazon",
  "name": "Apple iPhone 15 (128 GB) - Black",
  "brand": "Apple",
  "image_url": "https://m.media-amazon.com/images/I/example.jpg",
  "current_price": 67999.00,
  "currency": "INR",
  "availability": true,
  "rating": 4.5,
  "review_count": 12483,
  "seller": "Appario Retail Private Ltd",
  "last_checked_at": "2026-07-14T10:30:00Z",
  "created_at": "2026-07-01T08:00:00Z",
  "watcher_count": 13,
  "price_stats": {
    "all_time_low": 62999.00,
    "all_time_high": 79999.00,
    "drop_count": 6,
    "first_tracked_at": "2026-05-01T00:00:00Z"
  }
}
```

**Error Responses**

| Scenario             | Status | Code                | Message               |
|----------------------|--------|---------------------|-----------------------|
| Product ID not found | 404    | `PRODUCT_NOT_FOUND` | "Product not found."  |

---

### 5.6 GET /health

```
GET /v1/health
```

**Response — 200 OK**

```json
{
  "status": "ok",
  "database": "ok",
  "timestamp": "2026-07-14T10:30:00Z",
  "version": "1.0.0"
}
```

**Response — 503**

```json
{
  "status": "degraded",
  "database": "unreachable",
  "timestamp": "2026-07-14T10:30:00Z",
  "version": "1.0.0"
}
```

---

### 5.7 GET /runs

List recent scheduler runs. Requires Bearer token.

```
GET /v1/runs?limit=10&offset=0
Authorization: Bearer <SECRET_KEY>
```

**Response — 200 OK**

```json
{
  "total": 42,
  "limit": 10,
  "offset": 0,
  "runs": [
    {
      "run_id": "c3d4e5f6-a7b8-9012-cdef-012345678901",
      "started_at": "2026-07-14T10:00:00Z",
      "completed_at": "2026-07-14T10:08:23Z",
      "status": "completed",
      "products_total": 87,
      "products_scraped": 87,
      "products_failed": 0,
      "price_drops_found": 3,
      "emails_sent": 7
    }
  ]
}
```

---

### 5.8 GET /runs/{run_id}

```
GET /v1/runs/{run_id}
Authorization: Bearer <SECRET_KEY>
```

**Response — 200 OK**

```json
{
  "run_id": "c3d4e5f6-a7b8-9012-cdef-012345678901",
  "started_at": "2026-07-14T10:00:00Z",
  "completed_at": "2026-07-14T10:08:23Z",
  "status": "partial",
  "products_total": 87,
  "products_scraped": 84,
  "products_failed": 3,
  "price_drops_found": 3,
  "emails_sent": 7,
  "failures": [
    {
      "product_id": "f1e2d3c4-b5a6-7890-fedc-ba9876543210",
      "product_name": "Apple iPhone 15 (128 GB) - Black",
      "url": "https://www.amazon.in/Apple-iPhone-15-128GB-Black/dp/B0CHX1W1XY",
      "scrape_status": "blocked",
      "checked_at": "2026-07-14T10:04:11Z"
    }
  ]
}
```

---

### 5.9 POST /internal/trigger-run

```
POST /v1/internal/trigger-run
Authorization: Bearer <SECRET_KEY>
```

**Response — 202 Accepted**

```json
{
  "run_id": "c3d4e5f6-a7b8-9012-cdef-012345678901",
  "message": "Scrape run initiated.",
  "started_at": "2026-07-14T10:00:00Z"
}
```

---

## 6. Shared Schema Definitions

### ProductSnapshot (cache object — never persisted)

The in-memory cache entry created by `POST /products/preview` and consumed by
`POST /subscriptions`. Combines live scrape data with DB lookup results.

```json
{
  "preview_id": "f8b9d2a1-4c3e-4f2d-9b1a-8e7f6d5c4b3a",
  "expires_at": "2026-07-14T10:40:00Z",
  "is_new_product": false,
  "live_data": {
    "marketplace_product_id": "B0CHX1W1XY",
    "url": "https://www.amazon.in/.../dp/B0CHX1W1XY",
    "platform": "amazon",
    "name": "Apple iPhone 15 (128 GB) - Black",
    "brand": "Apple",
    "image_url": "https://...",
    "current_price": 67999.00,
    "currency": "INR",
    "availability": true,
    "rating": 4.5,
    "review_count": 12483,
    "seller": "Appario Retail Private Ltd",
    "scraped_at": "2026-07-14T10:30:00Z"
  },
  "catalog_data": {
    "product_id": "f1e2d3c4-b5a6-7890-fedc-ba9876543210",
    "last_tracked_price": 69999.00,
    "price_change_indicator": "down",
    "price_change_amount": 2000.00,
    "last_checked_at": "2026-07-14T06:00:00Z",
    "watcher_count": 12,
    "price_stats": {
      "all_time_low": 62999.00,
      "all_time_high": 79999.00,
      "drop_count": 5,
      "first_tracked_at": "2026-05-01T00:00:00Z"
    }
  }
}
```

### price_change_indicator

| Condition                                             | Value         |
|-------------------------------------------------------|---------------|
| `live_price < last_tracked_price`                     | `"down"`      |
| `live_price > last_tracked_price`                     | `"up"`        |
| `live_price == last_tracked_price`                    | `"unchanged"` |
| `last_tracked_price` is null (product never scheduled)| `null`        |

### Platform Enum

| Value        | Description  |
|--------------|--------------|
| `"amazon"`   | Amazon India |
| `"flipkart"` | Flipkart     |

### Run Status Enum

| Value         | Description                                     |
|---------------|-------------------------------------------------|
| `"running"`   | Run currently in progress                       |
| `"completed"` | All products scraped successfully               |
| `"partial"`   | One or more products failed after max retries   |
| `"failed"`    | Run could not start                             |

### Scrape Status Enum

| Value       | Description                                             |
|-------------|---------------------------------------------------------|
| `"success"` | Price extracted successfully                            |
| `"failed"`  | Price extraction failed after all retries               |
| `"blocked"` | Bot detection triggered — routed to ScraperAPI fallback |

---

## 7. Two-Step Flow Sequence

```
User enters URL
      │
      ▼
POST /products/preview
      │
      ├─ Validate URL
      ├─ Live scrape (Playwright)
      ├─ Extract marketplace_product_id
      ├─ DB lookup (read-only)
      │    ├─ Found → read price, watcher_count, price_stats
      │    └─ Not found → catalog_data = null
      ├─ Assemble ProductSnapshot
      ├─ Cache snapshot (TTL: 10 min)
      └─ Return preview_id + live_data + catalog_data
                   │
                   ▼
         User reviews preview:
         - Live price (primary)
         - Last tracked price + change indicator (if exists)
         - Watcher count + price trend (if exists)
                   │
                   ▼
          POST /subscriptions
          { preview_id, email }
                   │
                   ├─ Retrieve cache
                   │    └─ If expired → re-scrape + re-lookup transparently
                   │
                   └─ ProductSyncService
                        ├─ Create/Update Product (live_data)
                        ├─ Insert price_history (if price changed)
                        ├─ Get or create Subscription (silent on duplicate)
                        └─ Return subscription_id + product_id
                                    │
                                    ▼
                         Redirect → GET /products/{product_id}
```

---

## 8. HTTP Status Code Summary

| Status | Used for                                                         |
|--------|------------------------------------------------------------------|
| 200    | Successful GET, successful DELETE, successful POST /products/preview |
| 201    | Successful POST /subscriptions                                   |
| 202    | POST /internal/trigger-run (async)                               |
| 400    | Invalid URL, unsupported platform, invalid email                 |
| 401    | Missing or invalid Bearer token                                  |
| 404    | Resource not found (preview, subscription, product, run)         |
| 409    | Run already in progress                                          |
| 422    | Request body or query param fails schema validation              |
| 500    | Unhandled server error                                           |
| 502    | Scrape failed or blocked                                         |
| 503    | Database unreachable                                             |
