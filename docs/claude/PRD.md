# PriceWatch — Product Requirements Document

> Last updated: July 2026
> Status: Requirements finalised. MVP ready to build.

---

## 1. What is PriceWatch

A web application that monitors product prices from e-commerce platforms and notifies users when prices drop. Multiple users can track the same product — scraping happens once, notifications go to all subscribers.

---

## 2. What We Are Building Now (MVP)

### Core Features
- User submits a product URL and their email
- System scrapes and stores product details
- Price is checked on a schedule
- If price drops, email notification goes to all users watching that URL
- User can view their tracked items with current price
- User can delete a tracked item

### Supported Platforms
- Amazon India
- Flipkart

### Notification Channel
- Email only

---

## 3. Functional Requirements (MVP)

### FR-1 Add Product
User provides:
- Product URL
- Email address

System does:
- Validates URL (supported platform, valid product page)
- Checks if product already exists in database
  - If yes → create new subscription only
  - If no → scrape product details, create product, create subscription
- Scrapes and stores:
  - Product name
  - Product image
  - Current price
  - Availability (in stock / out of stock)
  - Platform (Amazon / Flipkart)

### FR-2 URL Validation
- Must be a supported platform (Amazon India / Flipkart)
- Must be a valid product page
- Amazon URL patterns supported: `/dp/`, `/gp/product/`, `amzn.in` short URLs
- Show clear error if unsupported or invalid

### FR-3 Duplicate URL Handling
- If same URL is submitted by multiple users:
  - One product record in database
  - Multiple subscription records — one per user
  - Scraping runs once per product
  - Price drop email goes to all subscribers

### FR-4 Delete Product
- User removes their subscription only
- Product record remains if other users are still subscribed
- Product record is deleted only if no subscribers remain

### FR-5 Dashboard
Display per tracked item:
- Product image
- Product name
- Current price
- Availability
- Platform
- Last checked time

Actions:
- Delete tracking

### FR-6 Price Drop Detection
- Scraper fetches current price from product page
- Compares with `current_price` in `products` table
- If scraped price < current price → price dropped
- On price drop:
  - Send email to all subscribers
  - Update `current_price` in `products` table
  - Insert new row in `price_history`
- If same or higher:
  - Insert new row in `price_history`
  - No email

**Edge case:** First scrape for a new product — `current_price` is null → save price, no email sent

### FR-7 Email Notification
Email contains:
- Product name
- Product image
- Old price
- New price
- Drop amount and percentage
- Direct link to product

### FR-8 Price Check Schedule
- Every 4 hours for all products

### FR-9 Manual Refresh
- Not in MVP (pipeline)

---

## 4. Database Schema

### users
| Column     | Type         | Notes              |
|------------|--------------|--------------------|
| user_id    | UUID         | Primary key        |
| email      | VARCHAR(255) | Unique, not null   |
| phone      | VARCHAR(20)  | Nullable           |
| created_at | TIMESTAMP    | Default now()      |

### products
| Column          | Type          | Notes                        |
|-----------------|---------------|------------------------------|
| product_id      | UUID          | Primary key                  |
| url             | TEXT          | Unique, not null             |
| platform        | VARCHAR(50)   | 'amazon' / 'flipkart'        |
| name            | TEXT          | Scraped                      |
| image_url       | TEXT          | Scraped                      |
| current_price   | DECIMAL(10,2) | Scraped, null on first add   |
| currency        | VARCHAR(10)   | Default 'INR'                |
| availability    | BOOLEAN       | In stock or not              |
| last_checked_at | TIMESTAMP     | Updated every scrape         |
| created_at      | TIMESTAMP     | Default now()                |

### subscriptions
| Column          | Type      | Notes                               |
|-----------------|-----------|-------------------------------------|
| subscription_id | UUID      | Primary key                         |
| user_id         | UUID      | FK → users                          |
| product_id      | UUID      | FK → products                       |
| created_at      | TIMESTAMP | Default now()                       |
| UNIQUE          | —         | (user_id, product_id) — no duplicates |

### price_history
| Column     | Type          | Notes         |
|------------|---------------|---------------|
| history_id | UUID          | Primary key   |
| product_id | UUID          | FK → products |
| price      | DECIMAL(10,2) | Not null      |
| checked_at | TIMESTAMP     | Default now() |

---

## 5. Price Drop Logic (Pseudocode)

```
for each product in products:
    scraped_price = scrape(product.url)

    if product.current_price is null:
        # First scrape — no notification
        save scraped_price to price_history
        update products.current_price = scraped_price
        continue

    if scraped_price < product.current_price:
        # Price dropped — notify all subscribers
        notify all subscribers via email
        update products.current_price = scraped_price

    insert scraped_price into price_history
```

---

## 6. Tech Stack (To Be Finalised)

| Layer       | Options                              |
|-------------|--------------------------------------|
| Backend     | Python (FastAPI or Django)           |
| Database    | PostgreSQL                           |
| Scraping    | BeautifulSoup / Playwright           |
| Scheduler   | Celery + Redis / APScheduler         |
| Email       | SendGrid / Gmail SMTP                |
| Frontend    | React or simple HTML/CSS to start    |

---

## 7. Build Sequence (MVP)

1. **Scraper** — get price reliably for Amazon and Flipkart
2. **Database** — set up 4 tables
3. **Scheduler** — run scraper every 4 hours
4. **Price drop detection** — compare and notify
5. **Email notification** — send formatted email
6. **Frontend** — dashboard to add / view / delete tracked items

> Start with the scraper. Everything else depends on it working reliably.

---

## 8. Anti-Bot & Scraping Resilience (To Address Before Production)

- Rotating proxies or paid scraping service (ScraperAPI / Oxylabs)
- Retry policy on scrape failure
- CAPTCHA handling strategy
- Schema change detection (alert if scraper stops finding price)
- Scrape failure logging and alerting

---

## 9. Pipeline (Future Releases)

### Phase 2 — Better Tracking
- Price history chart (line chart, daily / weekly / monthly view)
- All time low badge
- Highest price ever recorded
- Manual refresh with rate limiting
- Search, sort, filter on dashboard

### Phase 3 — Smarter Alerts
- Target price alert (notify when price hits ₹X)
- Percentage drop alert (notify only if drops by 5% / 10% / 20%)
- Notification cooldown (max one email per 24 hours per product per user)
- Lowest ever price alert

### Phase 4 — Offers & Discounts
- Card discount scraping and storage
  - Raw text stored as scraped
  - Parsed into structured fields (card name, discount type, amount, cap)
- Coupon codes
- Cashback offers
- EMI options

### Phase 5 — More Platforms
- Croma
- Reliance Digital
- Myntra
- Apple Store India
- Samsung Store India

### Phase 6 — More Notification Channels
- SMS (Twilio)
- WhatsApp
- Telegram
- Push notifications (mobile / browser)

### Phase 7 — Advanced Features
- User registration and login
- Admin role
- Sale prediction ("Buy now" vs "Wait")
- Price prediction using historical trends
- Cross-platform price comparison
- Wishlist / product tags / notes
- Shareable watchlist link
- Export price history (CSV / Excel / PDF)
- Browser extension
- Mobile app (Android / iOS)
- REST API for third-party integrations
- Daily / weekly price digest emails
- Price anomaly detection
- AI recommendation engine
