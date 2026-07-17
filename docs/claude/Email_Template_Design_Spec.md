# PriceWatch — HTML Email Template Design Specification

| Field      | Value                              |
|------------|------------------------------------|
| Version    | 1.0                                |
| Status     | Draft — MVP                        |
| Date       | July 2026                          |
| Depends on | SAD v1.0, API Specification v1.0   |
| Used by    | `notifications/email_sender.py`    |

---

## Table of Contents

1. [Overview](#1-overview)
2. [Email Metadata](#2-email-metadata)
3. [Content Blocks](#3-content-blocks)
4. [Visual Design](#4-visual-design)
5. [Typography](#5-typography)
6. [Colour Palette](#6-colour-palette)
7. [Layout Specification](#7-layout-specification)
8. [Dynamic Fields](#8-dynamic-fields)
9. [Conditional Display Rules](#9-conditional-display-rules)
10. [Mobile Rendering](#10-mobile-rendering)
11. [Plain-Text Fallback](#11-plain-text-fallback)
12. [SendGrid Integration Notes](#12-sendgrid-integration-notes)
13. [Template Variables Reference](#13-template-variables-reference)

---

## 1. Overview

PriceWatch sends exactly one type of transactional email in the MVP: the **price drop notification**. This document specifies the structure, visual design, content, and dynamic fields for that email.

The email is built as a single HTML file and sent via the SendGrid Python SDK. It uses inline CSS throughout — no external stylesheets, no web fonts beyond system fallbacks — for maximum compatibility across email clients (Gmail, Outlook, Apple Mail, mobile clients).

**Design goal:** The email should feel informative and clean, not promotional. The recipient already opted in to track this product — the email's job is to deliver the price drop information clearly and get them to the product page quickly.

---

## 2. Email Metadata

| Field       | Value                                                                 |
|-------------|-----------------------------------------------------------------------|
| From name   | PriceWatch                                                            |
| From address| `alerts@pricewatch.app` (SendGrid verified sender)                    |
| Reply-to    | `no-reply@pricewatch.app`                                             |
| Subject     | `Price drop: {product_name} is now ₹{new_price:,.0f}`                |
| Preheader   | `Down from ₹{old_price:,.0f} — save ₹{drop_amount:,.0f} ({drop_pct:.0f}% off)` |

### Subject Line Examples

```
Price drop: Apple iPhone 15 (128GB) - Black is now ₹69,999
Price drop: Samsung Galaxy S24 5G is now ₹74,999
Price drop: Sony WH-1000XM5 Headphones is now ₹24,990
```

### Preheader Examples

The preheader is hidden text that appears in inbox preview below the subject line in most email clients. It should not appear visually in the rendered email body.

```
Down from ₹79,999 — save ₹10,000 (13% off)
Down from ₹82,999 — save ₹8,000 (10% off)
```

---

## 3. Content Blocks

The email is composed of five sequential content blocks, top to bottom:

```
┌──────────────────────────────────────┐
│  BLOCK 1: Header / Branding          │
├──────────────────────────────────────┤
│  BLOCK 2: Price Drop Hero            │
├──────────────────────────────────────┤
│  BLOCK 3: Product Details            │
├──────────────────────────────────────┤
│  BLOCK 4: Call to Action             │
├──────────────────────────────────────┤
│  BLOCK 5: Footer                     │
└──────────────────────────────────────┘
```

---

### Block 1: Header / Branding

**Purpose:** Identifies the sender. Minimal — not a navigation bar.

**Content:**
- PriceWatch wordmark / logo (text-based for email client compatibility)
- Tagline: "Price drop alert"

**Styling:**
- Background: Brand primary (`#1a1a2e`)
- Text: White (`#ffffff`)
- Padding: 24px top/bottom, 32px left/right
- Logo font: 22px bold, letter-spacing 1px
- Tagline: 12px, uppercase, letter-spacing 2px, muted (`#a0a0c0`)
- Alignment: Left-aligned

**Visual:**
```
┌──────────────────────────────────────┐
│                                      │
│  👁️  PRICEWATCH                      │
│  PRICE DROP ALERT                    │
│                                      │
└──────────────────────────────────────┘
```

---

### Block 2: Price Drop Hero

**Purpose:** The most important block. The user should immediately see how much the price dropped.

**Content:**
- Headline: "Price just dropped"
- Old price (struck through)
- New price (large, prominent)
- Drop amount and percentage

**Styling:**
- Background: White (`#ffffff`)
- Padding: 32px top, 32px left/right, 16px bottom
- Headline: 15px, uppercase, letter-spacing 2px, muted grey (`#6b7280`)
- Old price: 18px, struck through (`text-decoration: line-through`), muted (`#9ca3af`)
- New price: 36px bold, brand accent green (`#16a34a`)
- Drop badge: Pill shape, green background (`#dcfce7`), green text (`#15803d`), 13px, bold
  - Content: `▼ ₹{drop_amount:,.0f} off · {drop_pct:.0f}% drop`
- Layout: Prices left-aligned, badge below new price

**Visual:**
```
┌──────────────────────────────────────┐
│                                      │
│  PRICE JUST DROPPED                  │
│                                      │
│  ~~₹79,999~~                         │
│                                      │
│  ₹69,999                             │
│  [ ▼ ₹10,000 off · 13% drop ]       │
│                                      │
└──────────────────────────────────────┘
```

---

### Block 3: Product Details

**Purpose:** Reminds the user which product this alert is for. Includes product image, name, and platform.

**Content:**
- Product image (from `image_url`)
- Product name
- Platform badge (Amazon India / Flipkart)
- Availability status

**Styling:**
- Background: Light grey (`#f9fafb`)
- Padding: 24px all sides
- Border-top: 1px solid `#e5e7eb`
- Image: Max width 120px, max height 120px, `object-fit: contain`, centered vertically
- Product name: 16px, semi-bold (`font-weight: 600`), dark (`#111827`)
- Platform badge: 12px, rounded pill, grey background (`#e5e7eb`), dark text (`#374151`)
  - Amazon: `🛒 Amazon India`
  - Flipkart: `🛍️ Flipkart`
- Availability: 13px
  - In stock: `✅ In Stock` in `#15803d`
  - Out of stock: `❌ Out of Stock` in `#b91c1c`
- Layout: Two-column — image left (fixed ~120px), product info right

**Image fallback:** If `image_url` is null or the image fails to load, display a grey placeholder box with a shopping bag icon (using text/emoji fallback). Always set `alt` text to the product name.

**Visual:**
```
┌──────────────────────────────────────┐
│                                      │
│  [img]  Apple iPhone 15 (128GB)      │
│  120px  - Black                      │
│         [ 🛒 Amazon India ]          │
│         ✅ In Stock                  │
│                                      │
└──────────────────────────────────────┘
```

---

### Block 4: Call to Action

**Purpose:** Single, clear action — take the user to the product page before the price changes again. Creates mild urgency without being manipulative.

**Content:**
- Button: "View on Amazon India" or "View on Flipkart" (platform-specific)
- Sub-copy: "Prices can change at any time."

**Styling:**
- Background: White
- Padding: 24px all sides
- Button:
  - Background: `#1d4ed8` (brand blue)
  - Text: White, 16px, bold
  - Padding: 14px 32px
  - Border-radius: 6px
  - Full width on mobile, max 280px on desktop
  - `text-decoration: none` — rendered as `<a>` tag styled as a button
- Sub-copy: 12px, muted grey (`#6b7280`), centered, 12px margin-top

**Important:** The button must be an `<a>` tag, not a `<button>`. Email clients do not support interactive elements. The href is the canonical product URL.

**Visual:**
```
┌──────────────────────────────────────┐
│                                      │
│     [ View on Amazon India → ]       │
│                                      │
│      Prices can change at any time.  │
│                                      │
└──────────────────────────────────────┘
```

---

### Block 5: Footer

**Purpose:** Legal/informational. Tells the user why they received this email and how to stop receiving alerts.

**Content:**
- "You're receiving this because you're tracking [product name] on PriceWatch."
- "To stop tracking this product, visit PriceWatch and remove it from your list."
- Link to PriceWatch dashboard
- Muted separator line above

**Styling:**
- Background: `#f3f4f6`
- Padding: 24px all sides
- Font size: 12px
- Text colour: `#6b7280` (muted grey)
- Link colour: `#4b5563`
- Text-align: center
- Border-top: 1px solid `#e5e7eb`

**Visual:**
```
┌──────────────────────────────────────┐
│                                      │
│  You're receiving this because you   │
│  track Apple iPhone 15 on            │
│  PriceWatch.                         │
│                                      │
│  To stop tracking, visit your        │
│  dashboard and remove the item.      │
│                                      │
│  pricewatch.app/dashboard            │
│                                      │
└──────────────────────────────────────┘
```

> **MVP note:** There is no one-click unsubscribe link in the MVP because there is no authentication. The footer links to the PriceWatch dashboard where the user can remove the item manually. Phase 7 will add JWT-based unsubscribe links.

---

## 4. Visual Design

### Overall Email Container

- Max width: **600px** — standard for email clients
- Background behind container: `#f3f4f6` (light grey page background)
- Container background: `#ffffff`
- Border-radius: 8px (clipped by some email clients — acceptable)
- Box-shadow: none (not supported in most email clients)
- Centred horizontally using table-based layout (not CSS flexbox/grid — email clients require table layout)

### Spacing System

| Usage             | Value   |
|-------------------|---------|
| Block padding     | 24–32px |
| Element gap       | 12–16px |
| Button padding    | 14px 32px |
| Footer padding    | 24px    |

---

## 5. Typography

All font stacks use system fonts only — no Google Fonts, no web fonts. Web fonts are unreliable in email clients.

| Usage         | Font stack                                              | Size | Weight |
|---------------|---------------------------------------------------------|------|--------|
| Body          | `-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif` | 14px | 400 |
| Product name  | Same                                                    | 16px | 600    |
| New price     | Same                                                    | 36px | 700    |
| Old price     | Same                                                    | 18px | 400    |
| Button        | Same                                                    | 16px | 700    |
| Labels/badges | Same                                                    | 12px | 400    |
| Footer        | Same                                                    | 12px | 400    |

Line-height: 1.5 throughout.

---

## 6. Colour Palette

| Purpose               | Hex       | Usage                                      |
|-----------------------|-----------|--------------------------------------------|
| Brand primary         | `#1a1a2e` | Header background                          |
| Brand blue            | `#1d4ed8` | CTA button background                      |
| Price green           | `#16a34a` | New price text                             |
| Price green light     | `#dcfce7` | Drop badge background                      |
| Price green dark      | `#15803d` | Drop badge text, availability text         |
| Page background       | `#f3f4f6` | Behind email container, footer block       |
| Product block bg      | `#f9fafb` | Product details block                      |
| Body text             | `#111827` | Product name, primary content              |
| Secondary text        | `#374151` | Platform badge                             |
| Muted text            | `#6b7280` | Labels, footer, sub-copy                   |
| Very muted            | `#9ca3af` | Old price, struck-through                  |
| White                 | `#ffffff` | Main container, button text                |
| Border                | `#e5e7eb` | Dividers between blocks                    |
| Out of stock red      | `#b91c1c` | Out of stock text                          |

---

## 7. Layout Specification

Email clients do not reliably support CSS flexbox or grid. All multi-column layouts use `<table>` elements with inline styles.

### Full Email Structure (HTML outline)

```html
<!-- Outer wrapper — full-width page background -->
<table width="100%" bgcolor="#f3f4f6" cellpadding="0" cellspacing="0">
  <tr>
    <td align="center" style="padding: 24px 16px;">

      <!-- Inner container — 600px max -->
      <table width="600" style="max-width:600px; background:#ffffff; border-radius:8px; overflow:hidden;">

        <!-- Block 1: Header -->
        <tr><td bgcolor="#1a1a2e" style="padding:24px 32px;">
          ...header content...
        </td></tr>

        <!-- Block 2: Price drop hero -->
        <tr><td bgcolor="#ffffff" style="padding:32px 32px 16px 32px;">
          ...price content...
        </td></tr>

        <!-- Block 3: Product details -->
        <tr><td bgcolor="#f9fafb" style="padding:24px 32px; border-top:1px solid #e5e7eb;">
          <!-- Two-column table for image + info -->
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td width="120" valign="top">...image...</td>
              <td style="padding-left:16px;" valign="top">...info...</td>
            </tr>
          </table>
        </td></tr>

        <!-- Block 4: Call to action -->
        <tr><td bgcolor="#ffffff" style="padding:24px 32px; text-align:center;">
          ...button...
        </td></tr>

        <!-- Block 5: Footer -->
        <tr><td bgcolor="#f3f4f6" style="padding:24px 32px; border-top:1px solid #e5e7eb;">
          ...footer text...
        </td></tr>

      </table>
    </td>
  </tr>
</table>
```

---

## 8. Dynamic Fields

All dynamic fields are injected by `email_sender.py` using Python string formatting before sending. No templating engine (Jinja2, etc.) is required at MVP scale — the HTML string is built in code.

| Placeholder          | Source                         | Format                            |
|----------------------|--------------------------------|-----------------------------------|
| `{product_name}`     | `products.name`                | Raw string, HTML-escaped          |
| `{product_image_url}`| `products.image_url`           | URL string                        |
| `{product_url}`      | `products.url`                 | URL string (canonical)            |
| `{platform_label}`   | Derived from `products.platform`| `"Amazon India"` or `"Flipkart"` |
| `{platform_icon}`    | Derived from `products.platform`| `"🛒"` or `"🛍️"`               |
| `{old_price}`        | `notification_log.old_price`   | `₹79,999` (formatted)            |
| `{new_price}`        | `notification_log.new_price`   | `₹69,999` (formatted)            |
| `{drop_amount}`      | `old_price - new_price`        | `₹10,000` (formatted)            |
| `{drop_pct}`         | `(drop_amount / old_price) * 100` | `13%` (rounded, no decimal)   |
| `{availability_text}`| `products.availability`        | `"✅ In Stock"` or `"❌ Out of Stock"` |
| `{dashboard_url}`    | Config                         | `https://pricewatch.app/dashboard`|

### Price Formatting in Python

```python
def format_inr(amount: Decimal) -> str:
    """Format a price in Indian number system (e.g. ₹79,999 or ₹1,29,999)."""
    # For MVP, standard comma formatting is acceptable
    return f"₹{amount:,.0f}"

def calculate_drop(old_price: Decimal, new_price: Decimal) -> tuple[Decimal, float]:
    drop_amount = old_price - new_price
    drop_pct = (drop_amount / old_price) * 100
    return drop_amount, drop_pct
```

---

## 9. Conditional Display Rules

| Condition                         | Behaviour                                                                  |
|-----------------------------------|----------------------------------------------------------------------------|
| `image_url` is None               | Show grey placeholder box (80×80px, `#e5e7eb` background) with `📦` text |
| `availability` is None            | Omit availability line entirely                                            |
| `availability` is `False`         | Show "❌ Out of Stock" in red — CTA button still shown                    |
| `drop_pct` >= 50%                 | Add "🔥 Major price drop!" label above the new price                      |
| Product name longer than 80 chars | Truncate with ellipsis in subject line only; show full name in email body  |

---

## 10. Mobile Rendering

Email clients on mobile (Gmail app, Apple Mail) render emails in a constrained viewport. The following rules ensure the email is readable on small screens:

- **Container width:** `width="600"` on the table, `max-width:600px` in inline style. On mobile, the email scales down naturally.
- **Font sizes:** Minimum 14px body, 13px for captions. Never below 12px — iOS mail auto-zooms below 13px which breaks layout.
- **CTA button:** `width:100%; max-width:280px` — expands to full width on narrow screens.
- **Product image:** `max-width:80px; max-height:80px` on mobile (via `@media` query if the email client supports it — table fallback otherwise).
- **Two-column product block:** On mobile viewports below 480px, the image and text stack vertically. Achieved via a single-column fallback: image above, text below, both full width.
- **Touch targets:** CTA button minimum height 44px — comfortable tap target on mobile.

---

## 11. Plain-Text Fallback

SendGrid sends both HTML and plain-text parts in a multipart MIME email. The plain-text version is sent alongside the HTML and displayed by clients that cannot render HTML.

**Plain-text template:**

```
PRICEWATCH — PRICE DROP ALERT
==============================

{product_name} just dropped in price!

OLD PRICE: {old_price}
NEW PRICE: {new_price}
SAVING:    {drop_amount} ({drop_pct}% off)

Platform:     {platform_label}
Availability: {availability_text}

View the product:
{product_url}

---
You're receiving this because you're tracking this product on PriceWatch.
To stop tracking, visit your dashboard: {dashboard_url}
```

---

## 12. SendGrid Integration Notes

### Sending via Python SDK

```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, MimeType

def send_price_drop_email(
    to_email: str,
    html_content: str,
    plain_text_content: str,
    subject: str,
) -> bool:
    message = Mail(
        from_email=("alerts@pricewatch.app", "PriceWatch"),
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
        plain_text_content=plain_text_content,
    )
    message.reply_to = "no-reply@pricewatch.app"

    try:
        sg = SendGridAPIClient(settings.sendgrid_api_key)
        response = sg.send(message)
        return response.status_code == 202
    except Exception as e:
        logger.error("SendGrid error", error=str(e), to_email=to_email)
        return False
```

### SendGrid Settings to Configure

| Setting                    | Value                          |
|----------------------------|--------------------------------|
| Verified sender identity   | `alerts@pricewatch.app`        |
| Unsubscribe group          | Not used in MVP (no auth)      |
| Click tracking             | Disabled (not needed in MVP)   |
| Open tracking              | Optional (privacy-conscious — disable by default) |
| Bounce handling            | Enabled (automatic via SendGrid) |

### Rate Limits

- SendGrid free tier: 100 emails/day
- At MVP scale: one email per subscriber per price drop event
- If a product with 10 subscribers drops in price, that is 10 emails — well within the free tier

---

## 13. Template Variables Reference

Quick reference for the developer implementing `email_sender.py`:

| Variable           | Type      | Example value                                          | Notes                             |
|--------------------|-----------|--------------------------------------------------------|-----------------------------------|
| `product_name`     | `str`     | `Apple iPhone 15 (128GB) - Black`                     | HTML-escape before injecting      |
| `product_image_url`| `str\|None`| `https://m.media-amazon.com/images/I/...`            | Use placeholder if None           |
| `product_url`      | `str`     | `https://www.amazon.in/.../dp/B0CHX1W1XY`             |                                   |
| `platform`         | `str`     | `"amazon"` or `"flipkart"`                            | Derive label and icon from this   |
| `old_price`        | `Decimal` | `79999.00`                                             | Format as `₹79,999`              |
| `new_price`        | `Decimal` | `69999.00`                                             | Format as `₹69,999`              |
| `drop_amount`      | `Decimal` | `10000.00` (calculated)                               | `old_price - new_price`           |
| `drop_pct`         | `float`   | `12.5` (calculated)                                   | Round to 0 decimal places         |
| `availability`     | `bool\|None`| `True`                                              | May be None — see Section 9      |
| `dashboard_url`    | `str`     | `https://pricewatch.app/dashboard`                     | From config                       |

---

## 14. Change Log

| Version | Date      | Change                                                                 |
|---------|-----------|------------------------------------------------------------------------|
| 1.0     | July 2026 | Initial release                                                        |
| 2.0     | July 2026 | Added `brand`, `rating`, `review_count`, `seller` to dynamic fields and template variables; updated Block 3 product details to display richer metadata |

### v2.0 — Block 3 additions

The product details block now displays the additional fields captured during the
preview scrape:

| Field          | Display format                        | Nullable behaviour              |
|----------------|---------------------------------------|---------------------------------|
| `brand`        | `Brand: Apple` below product name     | Omit line if null               |
| `rating`       | `⭐ 4.5` inline with review count     | Omit if null                    |
| `review_count` | `(12,483 reviews)` next to rating     | Omit if null                    |
| `seller`       | `Sold by: Appario Retail Private Ltd` | Omit line if null               |

Updated Block 3 visual:

```
┌──────────────────────────────────────┐
│                                      │
│  [img]  Apple iPhone 15 (128GB)      │
│  120px  Black                        │
│         Brand: Apple                 │
│         [ 🛒 Amazon India ]          │
│         ✅ In Stock                  │
│         ⭐ 4.5 · 12,483 reviews      │
│         Sold by: Appario Retail      │
│                                      │
└──────────────────────────────────────┘
```

Updated template variables for `email_sender.py`:

| Variable         | Type       | Example value                   | Notes                     |
|------------------|------------|---------------------------------|---------------------------|
| `brand`          | `str\|None`| `Apple`                         | Omit line if None         |
| `rating`         | `float\|None`| `4.5`                         | Format as `⭐ 4.5`        |
| `review_count`   | `int\|None`| `12483`                         | Format as `12,483 reviews`|
| `seller`         | `str\|None`| `Appario Retail Private Ltd`    | Omit line if None         |
