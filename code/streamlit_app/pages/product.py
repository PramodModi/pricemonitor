import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime
from typing import Optional
import streamlit as st
from api_client import get_product


def _format_last_fetched(ts: Optional[str]) -> str:
    """
    Format a UTC ISO timestamp as an absolute date+time string in IST (UTC+5:30).
    e.g. "2026-07-30T06:00:00Z" → "30 Jul, 11:30 AM"
    Returns "Never fetched" when ts is None.
    """
    if ts is None:
        return "Never fetched"
    try:
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        dt_ist = dt.astimezone(IST)
        return dt_ist.strftime("%-d %b, %-I:%M %p")
    except Exception:
        return str(ts)


# ── Page setup ────────────────────────────────────────────────────────────────

st.title("📦 Product Details")

product_id = st.session_state.get("view_product_id")
if not product_id:
    st.info("No product selected.")
    st.stop()

if st.button("← Back to My Items"):
    st.session_state.view_product_id     = None
    st.session_state.product_detail_data = None
    st.switch_page("pages/dashboard.py")

# ── Load product ──────────────────────────────────────────────────────────────
cached = st.session_state.get("product_detail_data")
if cached and str(cached.get("product_id")) != str(product_id):
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

    # ── Pricing block ─────────────────────────────────────────────────────────
    # current_price is always shown.
    # mrp shown only when present AND different from current_price
    #   (same price = no real discount to display).
    # special_price shown only when present AND lower than current_price.
    # discount_pct shown alongside mrp when present.
    # All three are None for Amazon / Myntra / browser-scraped results — those
    # sections stay completely invisible.

    current_price = p.get("current_price")
    mrp           = p.get("mrp")
    special_price = p.get("special_price")
    discount_pct  = p.get("discount_pct")

    if current_price:
        price_parts = [f"₹{float(current_price):,.0f}"]

        # Show MRP with strikethrough only when it differs from selling price
        if mrp and float(mrp) != float(current_price):
            price_parts.append(
                f"<span style='text-decoration:line-through;color:#9ca3af;font-size:0.8em;'>"
                f"₹{float(mrp):,.0f}</span>"
            )

        # Discount badge
        if discount_pct and discount_pct > 0:
            price_parts.append(
                f"<span style='background:#dcfce7;color:#16a34a;"
                f"border-radius:4px;padding:2px 7px;font-size:0.75em;"
                f"font-weight:600;'>{discount_pct:.0f}% off</span>"
            )

        st.markdown(
            f"<div style='font-size:1.8em;font-weight:700;margin:4px 0;'>"
            + " &nbsp;".join(price_parts)
            + "</div>",
            unsafe_allow_html=True,
        )

        # Special price row — only when lower than selling price
        if special_price and float(special_price) < float(current_price):
            st.markdown(
                
                f"<p style='font-size:18px;font-weight:700;color:#2563EB;margin:0 0 4px;'>"
                f"💰 Offer price: <strong>₹{float(special_price):,.0f}</strong>"
                f"</p>",
                unsafe_allow_html=True,
            )

    meta = []
    if p.get("rating"):
        meta.append(f"⭐ {p['rating']}")
    if p.get("review_count"):
        meta.append(f"{p['review_count']:,} reviews")
    if meta:
        st.caption("  ·  ".join(meta))

    if p.get("seller"):
        st.caption(f"Sold by: {p['seller']}")

    # ── Last fetched + refresh ─────────────────────────────────────────────────
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

# ── Bank offers — only when present (Flipkart affiliate API) ──────────────────
# offers is [] for Amazon, Myntra, and browser-scraped results — section hidden.
offers = p.get("offers") or []
if offers:
    st.divider()
    with st.expander(f"🏦 Bank & Card Offers ({len(offers)} available)", expanded=False):
        for offer in offers:
            offer_text = offer.strip()
            if offer_text:
                st.markdown(f"• {offer_text}")

# ── Product metadata (description, features, specs, sizes) ──────────────────
# Populated for all portals when scraper or affiliate API extracts enrichment.
# Each section is hidden when the relevant key is absent — no empty sections.

meta_data = p.get("product_metadata") or {}

if meta_data:
    st.divider()

    # ── Description ───────────────────────────────────────────────────────────
    description = meta_data.get("description")
    if description:
        with st.expander("📄 Product Description", expanded=False):
            st.markdown(description)

    # ── Features / highlights ─────────────────────────────────────────────────
    features = meta_data.get("features") or []
    if features:
        with st.expander(f"✨ Key Features ({len(features)})", expanded=True):
            for feat in features:
                st.markdown(f"• {feat}")

    # ── Sizes available (Myntra) ───────────────────────────────────────────────
    sizes = meta_data.get("sizes_available") or []
    if sizes:
        st.markdown("**Sizes Available**")
        cols = st.columns(min(len(sizes), 8))
        for i, size in enumerate(sizes):
            with cols[i % len(cols)]:
                st.markdown(
                    f'<div style="border:1px solid #d1d5db;border-radius:6px;'
                    f'padding:4px 10px;text-align:center;font-size:13px;'
                    f'font-weight:600;margin:2px;">{size}</div>',
                    unsafe_allow_html=True,
                )

    # ── Specs table ───────────────────────────────────────────────────────────
    specs = meta_data.get("specs") or {}
    if specs:
        with st.expander(f"🔧 Specifications ({len(specs)} items)", expanded=False):
            import pandas as pd
            specs_df = pd.DataFrame(
                list(specs.items()), columns=["Specification", "Value"]
            )
            st.dataframe(
                specs_df,
                use_container_width=True,
                hide_index=True,
            )

    # ── Additional material / fit info (Myntra) ───────────────────────────────
    material_parts = []
    if meta_data.get("material"):
        material_parts.append(f"**Material:** {meta_data['material']}")
    if meta_data.get("fit"):
        material_parts.append(f"**Fit:** {meta_data['fit']}")
    if meta_data.get("style_notes"):
        material_parts.append(f"**Style:** {meta_data['style_notes']}")
    if material_parts:
        st.caption("  ·  ".join(material_parts))

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
        import altair as alt
        with st.spinner("Loading price chart..."):
            df = pd.DataFrame(history)
            df["checked_at"] = pd.to_datetime(df["checked_at"], utc=True)
            df["price"]      = df["price"].astype(float)
            df = df.sort_values("checked_at")

        chart = (
            alt.Chart(df)
            .mark_line(point=True, color="#2563eb")
            .encode(
                x=alt.X(
                    "checked_at:T",
                    title="Date",
                    axis=alt.Axis(format="%d %b", labelAngle=-45),
                ),
                y=alt.Y(
                    "price:Q",
                    title="Price (₹)",
                    scale=alt.Scale(zero=False),
                ),
                tooltip=[
                    alt.Tooltip("checked_at:T", title="Date", format="%d %b %Y, %I:%M %p"),
                    alt.Tooltip("price:Q",      title="Price (₹)", format=",.0f"),
                ],
            )
            .properties(width="container", height=350)
        )
        st.altair_chart(chart, use_container_width=True)
    elif len(history) == 1:
        st.caption(
            "Only one data point so far — chart will appear after the next monitoring run."
        )

if p.get("watcher_count"):
    st.caption(f"👥 {p['watcher_count']} people watching this product")
