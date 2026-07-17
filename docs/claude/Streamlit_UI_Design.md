# PriceWatch — Streamlit UI Design

| Field      | Value                            |
|------------|----------------------------------|
| Version    | 3.0                              |
| Status     | Draft — MVP                      |
| Date       | July 2026                        |
| Depends on | SAD v1.0, API Specification v3.0 |
| Supersedes | Streamlit UI Design v2.0         |
| Change     | Preview card now displays catalog_data: last tracked price with change indicator, watcher count, price trend stats |

---

## Table of Contents

1. [Overview](#1-overview)
2. [App Structure](#2-app-structure)
3. [Session State](#3-session-state)
4. [API Client](#4-api-client)
5. [Page: Dashboard](#5-page-dashboard)
6. [Page: Track New Item](#6-page-track-new-item)
7. [Page: Product Details](#7-page-product-details)
8. [Page: Settings Placeholder](#8-page-settings-placeholder)
9. [Shared Components](#9-shared-components)
10. [Error Handling](#10-error-handling)
11. [File Structure](#11-file-structure)
12. [Configuration](#12-configuration)

---

## 1. Overview

The Streamlit UI is a thin client — all data operations go through the FastAPI backend.
The track page is a three-state machine: URL entry → preview confirmation → success.
The preview step now surfaces both live scraped data and existing catalog context
(last tracked price, price change indicator, watcher count, price stats) where available.

---

## 2. App Structure

```
streamlit_app/
├── app.py
├── pages/
│   ├── dashboard.py
│   ├── track.py
│   ├── product.py
│   └── settings.py
├── components/
│   ├── product_card.py
│   ├── preview_card.py
│   └── empty_state.py
├── api_client.py
└── config.py
```

### app.py

```python
import streamlit as st
from api_client import get_health

st.set_page_config(
    page_title="PriceWatch",
    page_icon="👁️",
    layout="centered",
    initial_sidebar_state="expanded",
)

health = get_health()
if not health.ok:
    st.warning("⚠️ PriceWatch is experiencing issues. Some features may not work.")

dashboard = st.Page("pages/dashboard.py", title="My Items",       icon="📋", default=True)
track     = st.Page("pages/track.py",     title="Track New Item", icon="➕")
product   = st.Page("pages/product.py",   title="Product Details",icon="📦")
settings  = st.Page("pages/settings.py",  title="Settings",       icon="⚙️")

pg = st.navigation([dashboard, track, settings, product])
pg.run()
```

---

## 3. Session State

| Key                | Type           | Set by         | Used by                                        |
|--------------------|----------------|----------------|------------------------------------------------|
| `user_email`       | `str \| None`  | Dashboard, Track| Dashboard, Track pre-fill                     |
| `track_step`       | `str`          | Track page     | Track page state machine                       |
| `preview_result`   | `dict \| None` | Track page     | preview_card component                         |
| `delete_confirm`   | `dict \| None` | Product card   | Dashboard delete dialog                        |
| `view_product_id`  | `str \| None`  | Track confirm  | Product details page                           |

### track_step values

| Value      | Meaning                                              |
|------------|------------------------------------------------------|
| `"input"`  | URL entry form                                       |
| `"preview"`| Preview loaded, awaiting confirmation                |
| `"success"`| Subscription confirmed                               |

### Initialisation

```python
def init_session_state():
    defaults = {
        "user_email": None,
        "track_step": "input",
        "preview_result": None,
        "delete_confirm": None,
        "view_product_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
```

---

## 4. API Client

```python
# api_client.py

import requests
from dataclasses import dataclass
from config import settings


@dataclass
class APIResponse:
    ok: bool
    data: dict | None
    error_code: str | None
    error_message: str | None


def _call(method: str, path: str, **kwargs) -> APIResponse:
    try:
        response = requests.request(
            method,
            f"{settings.api_base_url}{path}",
            timeout=30,
            **kwargs,
        )
        if response.ok:
            return APIResponse(ok=True, data=response.json(),
                               error_code=None, error_message=None)
        body = response.json()
        error = body.get("error", {})
        return APIResponse(ok=False, data=None,
                           error_code=error.get("code", "UNKNOWN_ERROR"),
                           error_message=error.get("message", "Something went wrong."))
    except requests.exceptions.ConnectionError:
        return APIResponse(ok=False, data=None, error_code="CONNECTION_ERROR",
                           error_message="Cannot reach the PriceWatch server.")
    except requests.exceptions.Timeout:
        return APIResponse(ok=False, data=None, error_code="TIMEOUT",
                           error_message="The request timed out. Please try again.")


def preview_product(url: str) -> APIResponse:
    return _call("POST", "/v1/products/preview", json={"url": url})

def confirm_subscription(preview_id: str, email: str) -> APIResponse:
    return _call("POST", "/v1/subscriptions",
                 json={"preview_id": preview_id, "email": email})

def get_items(email: str) -> APIResponse:
    return _call("GET", "/v1/items", params={"email": email})

def get_product(product_id: str) -> APIResponse:
    return _call("GET", f"/v1/products/{product_id}")

def delete_subscription(subscription_id: str, email: str) -> APIResponse:
    return _call("DELETE", f"/v1/subscriptions/{subscription_id}",
                 params={"email": email})

def get_health() -> APIResponse:
    return _call("GET", "/v1/health")
```

---

## 5. Page: Dashboard

### Layout

```
┌──────────────────────────────────────────────────┐
│  👁️  PriceWatch                     [sidebar nav]│
├──────────────────────────────────────────────────┤
│  📋 My Tracked Items                             │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │ [user@example.com           ] [ View → ] │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  Showing 2 items for user@example.com            │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │ [img]  Apple iPhone 15 (128GB) - Black   │    │
│  │        🛒 Amazon India  ✅ In Stock       │    │
│  │        ₹67,999  ⭐ 4.5 (12,483)         │    │
│  │        Last checked: 2 hours ago         │    │
│  │                           [🗑️ Remove]    │    │
│  └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

### Code Sketch

```python
# pages/dashboard.py

import streamlit as st
from api_client import get_items, delete_subscription
from components.product_card import render_product_card
from components.empty_state import render_empty_state

st.title("📋 My Tracked Items")

with st.container(border=True):
    col1, col2 = st.columns([4, 1])
    with col1:
        email_input = st.text_input(
            "Email", value=st.session_state.user_email or "",
            placeholder="you@example.com", label_visibility="collapsed",
        )
    with col2:
        view_clicked = st.button("View →", use_container_width=True, type="primary")

if view_clicked and email_input:
    st.session_state.user_email = email_input.strip().lower()

if not st.session_state.user_email:
    st.info("Enter your email above to see your tracked products.")
    st.stop()

with st.spinner("Loading your items..."):
    result = get_items(st.session_state.user_email)

if not result.ok:
    st.error(f"Could not load items: {result.error_message}")
    st.stop()

items = result.data["items"]
count = result.data["count"]
st.caption(f"Showing {count} item{'s' if count != 1 else ''} "
           f"for **{st.session_state.user_email}**")

if count == 0:
    render_empty_state()
    st.stop()

if st.session_state.delete_confirm:
    pending = st.session_state.delete_confirm
    with st.dialog("Remove product?"):
        st.write(f"Remove **{pending['name']}** from your tracking list?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, remove", type="primary", use_container_width=True):
                res = delete_subscription(
                    pending["subscription_id"], st.session_state.user_email)
                st.session_state.delete_confirm = None
                st.success("Product removed.") if res.ok else st.error(res.error_message)
                st.rerun()
        with col2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.delete_confirm = None
                st.rerun()

for item in items:
    render_product_card(item)
```

---

## 6. Page: Track New Item

Three-state machine: `input` → `preview` → `success`.

### State: input

```
┌──────────────────────────────────────────────────┐
│  ➕ Track New Item                               │
│                                                  │
│  Paste a product URL and we'll fetch the details │
│  before you start tracking.                      │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │ https://www.amazon.in/...                │    │
│  │         [ Fetch Product Details ]        │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  ✅ Supported: Amazon India · Flipkart           │
└──────────────────────────────────────────────────┘
```

### State: preview — existing product in catalog

```
┌──────────────────────────────────────────────────┐
│  ➕ Track New Item                               │
│                                                  │
│  Is this the right product?                      │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │ [img]  Apple iPhone 15 (128GB) - Black   │    │
│  │        Brand: Apple                      │    │
│  │        🛒 Amazon India  ✅ In Stock       │    │
│  │                                          │    │
│  │        ₹67,999          LIVE PRICE       │    │
│  │        ₹69,999 → ₹67,999  ▼ ₹2,000 less │    │
│  │        than last tracked price           │    │
│  │                                          │    │
│  │        ⭐ 4.5 · 12,483 reviews           │    │
│  │        Sold by: Appario Retail           │    │
│  │                                          │    │
│  │  ── Already tracked ──────────────────   │    │
│  │  👥 12 people watching                   │    │
│  │  📉 Price has dropped 5 times            │    │
│  │  📊 Range: ₹62,999 – ₹79,999            │    │
│  │  📅 Tracked since: May 2026              │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  📧 [you@example.com                         ]  │
│                                                  │
│  [← Try different URL]  [✅ Yes, track it]      │
│                                                  │
│  Preview valid for ~10 minutes                   │
└──────────────────────────────────────────────────┘
```

### State: preview — new product (no catalog_data)

```
┌──────────────────────────────────────────────────┐
│  ┌──────────────────────────────────────────┐    │
│  │ [img]  Apple iPhone 15 (128GB) - Black   │    │
│  │        Brand: Apple                      │    │
│  │        🛒 Amazon India  ✅ In Stock       │    │
│  │        ₹67,999                           │    │
│  │        ⭐ 4.5 · 12,483 reviews           │    │
│  │        Sold by: Appario Retail           │    │
│  │                                          │    │
│  │  ✨ Be the first to track this product!  │    │
│  └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

### Code Sketch

```python
# pages/track.py

import streamlit as st
from api_client import preview_product, confirm_subscription
from components.preview_card import render_preview_card

st.title("➕ Track New Item")

# ══════════════════════════════════════════════════
# STATE: input
# ══════════════════════════════════════════════════

if st.session_state.track_step == "input":
    st.write(
        "Paste a product URL from Amazon India or Flipkart and we'll "
        "show you the details before you start tracking."
    )
    with st.form("url_form", border=True):
        url = st.text_input(
            "Product URL",
            placeholder="https://www.amazon.in/... or https://www.flipkart.com/...",
        )
        submitted = st.form_submit_button(
            "Fetch Product Details", type="primary", use_container_width=True)

    st.caption("✅ Supported: Amazon India (amazon.in) · Flipkart (flipkart.com)")

    if submitted:
        if not url.strip():
            st.error("Please enter a product URL.")
            st.stop()
        with st.spinner("Fetching live product details from marketplace..."):
            result = preview_product(url.strip())
        if result.ok:
            st.session_state.preview_result = result.data
            st.session_state.track_step = "preview"
            st.rerun()
        else:
            _show_preview_error(result.error_code, result.error_message)

# ══════════════════════════════════════════════════
# STATE: preview
# ══════════════════════════════════════════════════

elif st.session_state.track_step == "preview":
    preview = st.session_state.preview_result
    if not preview:
        st.session_state.track_step = "input"
        st.rerun()

    st.subheader("Is this the right product?")
    render_preview_card(preview)

    st.caption(f"Preview valid until **{preview['expires_at']}** UTC · "
               f"Live price fetched at {preview['live_data']['scraped_at']}")

    email = st.text_input(
        "📧 Your email — we'll notify you here when the price drops",
        value=st.session_state.user_email or "",
        placeholder="you@example.com",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Try a different URL", use_container_width=True):
            st.session_state.track_step = "input"
            st.session_state.preview_result = None
            st.rerun()
    with col2:
        if st.button("✅ Yes, track it", type="primary", use_container_width=True):
            if not email.strip() or "@" not in email:
                st.error("Please enter a valid email address.")
                st.stop()
            with st.spinner("Setting up tracking..."):
                result = confirm_subscription(
                    preview["preview_id"], email.strip().lower())
            if result.ok:
                st.session_state.user_email = email.strip().lower()
                st.session_state.view_product_id = result.data["product"]["product_id"]
                st.session_state.track_step = "success"
                st.session_state.preview_result = None
                st.rerun()
            else:
                _show_confirm_error(result.error_code, result.error_message)

# ══════════════════════════════════════════════════
# STATE: success
# ══════════════════════════════════════════════════

elif st.session_state.track_step == "success":
    with st.container(border=True):
        st.success("You're now tracking this product!")
        st.write(f"We'll email **{st.session_state.user_email}** when the price drops.")
        if st.button("View Product Details →", type="primary", use_container_width=True):
            st.session_state.track_step = "input"
            st.switch_page("pages/product.py")


def _show_preview_error(code: str, message: str) -> None:
    if code == "INVALID_URL":
        st.error("That URL doesn't look like a product page. "
                 "Please use a direct product URL from Amazon India or Flipkart.")
    elif code == "UNSUPPORTED_PLATFORM":
        st.error("Only Amazon India and Flipkart are supported right now.")
    elif code in ("SCRAPE_BLOCKED", "SCRAPE_FAILED"):
        st.warning("We couldn't fetch that product right now. "
                   "Please try again in a few minutes.")
    else:
        st.error(f"Something went wrong: {message}")


def _show_confirm_error(code: str, message: str) -> None:
    if code == "PREVIEW_NOT_FOUND":
        st.warning("Your preview expired. Please search for the product again.")
        st.session_state.track_step = "input"
        st.session_state.preview_result = None
        st.rerun()
    else:
        st.error(f"Could not complete subscription: {message}")
```

---

## 7. Page: Product Details

```python
# pages/product.py

import streamlit as st
from api_client import get_product

st.title("📦 Product Details")

product_id = st.session_state.get("view_product_id")
if not product_id:
    st.info("No product selected.")
    st.stop()

with st.spinner("Loading product..."):
    result = get_product(product_id)

if not result.ok:
    st.error(f"Could not load product: {result.error_message}")
    st.stop()

p = result.data

col_img, col_info = st.columns([1, 3])

with col_img:
    if p.get("image_url"):
        st.image(p["image_url"], width=140)
    else:
        st.markdown("📦")

with col_info:
    st.markdown(f"## {p['name']}")
    if p.get("brand"):
        st.caption(f"Brand: {p['brand']}")

    platform_label = "🛒 Amazon India" if p["platform"] == "amazon" else "🛍️ Flipkart"
    avail = "✅ In Stock" if p.get("availability") else "❌ Out of Stock"
    st.caption(f"{platform_label}  ·  {avail}")

    if p.get("current_price"):
        st.markdown(f"### ₹{p['current_price']:,.0f}")

    meta = []
    if p.get("rating"):      meta.append(f"⭐ {p['rating']}")
    if p.get("review_count"): meta.append(f"{p['review_count']:,} reviews")
    if meta: st.caption("  ·  ".join(meta))

    if p.get("seller"):
        st.caption(f"Sold by: {p['seller']}")

    if p.get("last_checked_at"):
        st.caption(f"Last checked: {p['last_checked_at']}")

    st.link_button(
        f"View on {'Amazon India' if p['platform'] == 'amazon' else 'Flipkart'} →",
        url=p["url"], type="primary",
    )

# ── Price stats ───────────────────────────────────────────────────────────────

stats = p.get("price_stats")
if stats:
    st.divider()
    st.subheader("Price History")
    col1, col2, col3 = st.columns(3)
    col1.metric("All-Time Low",  f"₹{stats['all_time_low']:,.0f}")
    col2.metric("All-Time High", f"₹{stats['all_time_high']:,.0f}")
    col3.metric("Price Drops",   stats["drop_count"])
    st.caption(f"Tracked since {stats['first_tracked_at'][:10]}")

if p.get("watcher_count"):
    st.caption(f"👥 {p['watcher_count']} people watching this product")

st.divider()
if st.button("← Back to My Items"):
    st.switch_page("pages/dashboard.py")
```

---

## 8. Page: Settings Placeholder

```python
# pages/settings.py

import streamlit as st

st.title("⚙️ Settings")
st.info("Notification settings are coming in a future release.")

with st.container(border=True):
    st.subheader("Coming in Phase 3")
    st.markdown("""
    - **Minimum drop %** — only notify when price drops by at least X%
    - **Alert cooldown** — maximum one email per product per 24 hours
    - **Target price** — notify when price falls below a specific amount
    """)
```

---

## 9. Shared Components

### components/preview_card.py

Handles all display logic for the preview step, including the `catalog_data` section
when the product already exists in the catalog.

```python
# components/preview_card.py

import streamlit as st
from datetime import datetime


def _format_date(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%b %Y")


def render_preview_card(preview: dict) -> None:
    """
    Renders the full preview card including live_data and catalog_data.
    preview: the full response dict from POST /products/preview
    """
    live = preview["live_data"]
    catalog = preview.get("catalog_data")

    with st.container(border=True):

        # ── Product image + core info ─────────────────────────────────────────
        col_img, col_info = st.columns([1, 3])

        with col_img:
            if live.get("image_url"):
                st.image(live["image_url"], width=120)
            else:
                st.markdown("📦")

        with col_info:
            st.markdown(f"**{live['name']}**")
            if live.get("brand"):
                st.caption(f"Brand: {live['brand']}")

            platform_label = (
                "🛒 Amazon India" if live["platform"] == "amazon" else "🛍️ Flipkart"
            )
            avail = "✅ In Stock" if live.get("availability") else "❌ Out of Stock"
            st.caption(f"{platform_label}  ·  {avail}")

            # ── Price display ─────────────────────────────────────────────────
            live_price = live.get("current_price")
            if live_price:
                st.markdown(f"### ₹{live_price:,.0f}")
                st.caption("Live price from marketplace")

            # Price change indicator — only when catalog data exists with a prior price
            if catalog and catalog.get("last_tracked_price") and live_price:
                last = catalog["last_tracked_price"]
                indicator = catalog.get("price_change_indicator")
                change_amt = catalog.get("price_change_amount", 0)

                if indicator == "down":
                    st.markdown(
                        f"🟢 **₹{change_amt:,.0f} less** than last tracked price "
                        f"(₹{last:,.0f})"
                    )
                elif indicator == "up":
                    st.markdown(
                        f"🔴 **₹{change_amt:,.0f} more** than last tracked price "
                        f"(₹{last:,.0f})"
                    )
                else:
                    st.caption(f"Same as last tracked price (₹{last:,.0f})")

            # ── Ratings + seller ──────────────────────────────────────────────
            meta = []
            if live.get("rating"):       meta.append(f"⭐ {live['rating']}")
            if live.get("review_count"): meta.append(f"{live['review_count']:,} reviews")
            if meta: st.caption("  ·  ".join(meta))
            if live.get("seller"): st.caption(f"Sold by: {live['seller']}")

        # ── Catalog context section ───────────────────────────────────────────
        if catalog:
            st.divider()

            col1, col2, col3 = st.columns(3)

            with col1:
                watcher_count = catalog.get("watcher_count", 0)
                st.metric("👥 Watchers", watcher_count)

            with col2:
                stats = catalog.get("price_stats")
                drop_count = stats["drop_count"] if stats else 0
                st.metric("📉 Price Drops", drop_count)

            with col3:
                if stats:
                    st.metric("📊 All-Time Low", f"₹{stats['all_time_low']:,.0f}")

            if stats:
                col_a, col_b = st.columns(2)
                col_a.caption(f"Highest ever: ₹{stats['all_time_high']:,.0f}")
                col_b.caption(f"Tracked since: {_format_date(stats['first_tracked_at'])}")

        else:
            st.divider()
            st.caption("✨ Be the first to track this product!")
```

### components/product_card.py

```python
# components/product_card.py

import streamlit as st
from datetime import datetime, timezone


def _format_last_checked(ts: str | None) -> str:
    if ts is None:
        return "Not yet checked"
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    diff = datetime.now(timezone.utc) - dt
    minutes = int(diff.total_seconds() / 60)
    if minutes < 60:   return f"{minutes}m ago"
    if minutes < 1440: return f"{minutes // 60}h ago"
    return f"{minutes // 1440}d ago"


def render_product_card(item: dict) -> None:
    product = item["product"]
    subscription_id = item["subscription_id"]

    with st.container(border=True):
        col_img, col_info, col_action = st.columns([1, 4, 1])

        with col_img:
            if product.get("image_url"):
                st.image(product["image_url"], width=72)
            else:
                st.markdown("📦")

        with col_info:
            st.markdown(f"**{product.get('name', 'Loading...')}**")

            platform_label = (
                "🛒 Amazon India" if product["platform"] == "amazon" else "🛍️ Flipkart"
            )
            avail = "✅ In Stock" if product.get("availability") else "❌ Out of Stock"
            st.caption(f"{platform_label}  ·  {avail}")

            if product.get("current_price"):
                price_line = f"₹{product['current_price']:,.0f}"
                meta = []
                if product.get("rating"):       meta.append(f"⭐ {product['rating']}")
                if product.get("review_count"): meta.append(f"{product['review_count']:,}")
                if meta: price_line += f"  ·  {'  ·  '.join(meta)}"
                st.markdown(f"**{price_line}**")

            st.caption(f"Last checked: {_format_last_checked(product.get('last_checked_at'))}")

        with col_action:
            if st.button("🗑️", key=f"remove_{subscription_id}", help="Remove"):
                st.session_state.delete_confirm = {
                    "subscription_id": subscription_id,
                    "name": product.get("name", "this product"),
                }
                st.rerun()
```

### components/empty_state.py

```python
# components/empty_state.py

import streamlit as st


def render_empty_state() -> None:
    st.markdown(
        """
        <div style="text-align:center; padding:3rem 1rem;">
            <div style="font-size:4rem;">📭</div>
            <h3>No tracked items yet</h3>
            <p>Start tracking a product and we'll alert you when the price drops.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("➕ Track Your First Item", use_container_width=True, type="primary"):
            st.switch_page("pages/track.py")
```

---

## 10. Error Handling

```python
USER_FACING_ERRORS = {
    "INVALID_URL":           "That URL doesn't look like a product page.",
    "UNSUPPORTED_PLATFORM":  "Only Amazon India and Flipkart are supported right now.",
    "INVALID_EMAIL":         "Please enter a valid email address.",
    "SCRAPE_BLOCKED":        "The marketplace blocked our request. Try again in a few minutes.",
    "SCRAPE_FAILED":         "Couldn't fetch product details. Please check the URL.",
    "PREVIEW_NOT_FOUND":     "Your preview expired. Please search for the product again.",
    "SUBSCRIPTION_NOT_FOUND":"That item wasn't found in your list.",
    "CONNECTION_ERROR":      "Cannot reach the server. Check your connection.",
    "TIMEOUT":               "The request timed out. Please try again.",
}
```

**Note on timeout:** `requests` timeout is set to **30 seconds** throughout — the
preview endpoint runs a live Playwright scrape which can take 10–15 seconds.

---

## 11. File Structure

```
streamlit_app/
├── app.py
├── config.py
├── api_client.py
├── components/
│   ├── __init__.py
│   ├── product_card.py
│   ├── preview_card.py
│   └── empty_state.py
└── pages/
    ├── dashboard.py
    ├── track.py
    ├── product.py
    └── settings.py
```

---

## 12. Configuration

```python
# config.py

import os
from dataclasses import dataclass


@dataclass
class Config:
    api_base_url: str


settings = Config(
    api_base_url=os.environ.get("API_BASE_URL", "http://localhost:8000")
)
```

Streamlit Community Cloud secrets (TOML):

```toml
API_BASE_URL = "https://api.pricewatch.app"
```
