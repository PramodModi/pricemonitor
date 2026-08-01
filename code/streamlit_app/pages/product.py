import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime
from typing import Optional
import streamlit as st
from api_client import get_product


def _format_last_fetched(ts: Optional[str]) -> str:
    """
    Format a UTC ISO timestamp as an absolute date+time string.
    e.g. "2026-07-30T06:00:00Z" → "30 Jul, 6:00 AM"
    Returns "Never fetched" when ts is None.
    """
    if not ts:
        return "Never fetched"
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.strftime("%-d %b, %-I:%M %p")
    except Exception:
        return str(ts)


# ── Page setup ────────────────────────────────────────────────────────────────

st.title("📦 Product Details")

product_id = st.session_state.get("view_product_id")
if not product_id:
    st.info("No product selected.")
    st.stop()

if st.button("← Back to My Items"):
    st.session_state.view_product_id    = None
    st.session_state.product_detail_data = None
    st.switch_page("pages/dashboard.py")

# ── Load product — from session cache if available, else fetch from API ───────
# product_detail_data is populated on first load and updated by the 🔄 button.
# Clear it when navigating to a different product.
cached = st.session_state.get("product_detail_data")
if cached and str(cached.get("product_id")) != str(product_id):
    # stale cache from a previous product — discard
    st.session_state.product_detail_data = None
    cached = None

if cached:
    p = cached
else:
    with st.spinner("Loading product..."):
        result = get_product(product_id)
    if not result.ok:
        st.error(f"Could not load product: {result.error_message}")
        st.stop()
    p = result.data
    st.session_state.product_detail_data = p

# ── Product header ────────────────────────────────────────────────────────────

col_img, col_info = st.columns([1, 3])

with col_img:
    if p.get("image_url"):
        st.image(p["image_url"], width=140)
    else:
        st.markdown(
            '<div style="font-size:48px;text-align:center;">📦</div>',
            unsafe_allow_html=True,
        )

with col_info:
    st.markdown(f"## {p.get('name', 'Product')}")

    if p.get("brand"):
        st.caption(f"Brand: {p['brand']}")

    platform = p.get("platform", "amazon")
    PLATFORM_DISPLAY = {
        "amazon":   "🛒 Amazon India",
        "flipkart": "🛍️ Flipkart",
        "myntra":   "👗 Myntra",
    }
    platform_label = PLATFORM_DISPLAY.get(platform, platform.title())
    avail = "✅ In Stock" if p.get("availability") else "❌ Out of Stock"
    st.caption(f"{platform_label}  ·  {avail}")

    if p.get("current_price"):
        st.markdown(f"### ₹{float(p['current_price']):,.0f}")

    meta = []
    if p.get("rating"):
        meta.append(f"⭐ {p['rating']}")
    if p.get("review_count"):
        meta.append(f"{p['review_count']:,} reviews")
    if meta:
        st.caption("  ·  ".join(meta))

    if p.get("seller"):
        st.caption(f"Sold by: {p['seller']}")

    # ── Last fetched timestamp + 🔄 button ────────────────────────────────────
    # Rendered as plain HTML caption so the button sits directly inline with
    # the timestamp text rather than in a separate Streamlit column that
    # Streamlit would push to the far right of the page.
    st.markdown(
        f'<p style="font-size:14px;color:#6b7280;margin:0 0 6px;">'
        f'Last fetched: {_format_last_fetched(p.get("last_checked_at"))}'
        f'</p>',
        unsafe_allow_html=True,
    )
    if st.button("🔄 Refresh", key="product_detail_refresh", help="Refresh from database"):
        fresh = get_product(str(product_id))
        if fresh.ok:
            st.session_state.product_detail_data = fresh.data
            st.rerun()
        else:
            st.toast("Could not refresh. Try again.", icon="⚠️")

    st.link_button(
        f"View on {PLATFORM_DISPLAY.get(platform, platform.title()).split(' ', 1)[-1].strip()} →",
        url=p["url"],
        type="primary",
    )

# ── Price stats + history chart ───────────────────────────────────────────────

stats = p.get("price_stats")
if stats:
    st.divider()
    st.subheader("Price History")
    col1, col2, col3 = st.columns(3)
    col1.metric("All-Time Low",  f"₹{float(stats['all_time_low']):,.0f}")
    col2.metric("All-Time High", f"₹{float(stats['all_time_high']):,.0f}")
    col3.metric("Price Checks",  stats["drop_count"])
    if stats.get("first_tracked_at"):
        st.caption(f"Tracked since {stats['first_tracked_at'][:10]}")

    history = p.get("price_history", [])
    if len(history) >= 2:
        import pandas as pd
        with st.spinner("Loading price chart..."):
            df = pd.DataFrame(history)
            df["checked_at"] = pd.to_datetime(df["checked_at"])
            df["price"]      = df["price"].astype(float)
            df["date"]       = df["checked_at"].dt.strftime("%-d %b")

        st.line_chart(df, x="date", y="price", y_label="Price (₹)", x_label="Date")
    elif len(history) == 1:
        st.caption(
            "Only one data point so far — chart will appear after the next scrape run."
        )

if p.get("watcher_count"):
    st.caption(f"👥 {p['watcher_count']} people watching this product")
