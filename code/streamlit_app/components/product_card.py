from datetime import datetime
from typing import Optional
import streamlit as st


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


def _format_price(price: Optional[float]) -> str:
    if price is None:
        return "Price unavailable"
    try:
        return f"₹{float(price):,.0f}"
    except (ValueError, TypeError):
        return "Price unavailable"


def render_product_card(item: dict) -> None:
    product         = item["product"]
    subscription_id = item["subscription_id"]
    product_id      = str(product.get("product_id", ""))

    PLATFORM_DISPLAY = {
        "amazon":   ("Amazon India", "🛒"),
        "flipkart": ("Flipkart",     "🛍️"),
        "myntra":   ("Myntra",       "👗"),
    }

    platform                   = product.get("platform", "amazon")
    platform_label, platform_icon = PLATFORM_DISPLAY.get(platform, (platform.title(), "🛒"))
    availability               = product.get("availability")
    avail_text                 = "✅ In Stock" if availability else "❌ Out of Stock"
    price                      = product.get("current_price")
    rating                     = product.get("rating")
    review_count               = product.get("review_count")
    product_url                = product.get("url", "")
    last_fetched               = _format_last_fetched(product.get("last_checked_at"))

    with st.container(border=True):
        # ── Row: image | info | buttons ──────────────────────────────────────
        col_img, col_info, col_btns = st.columns([1, 6, 2])

        # ── Image ─────────────────────────────────────────────────────────────
        with col_img:
            image_url = product.get("image_url")
            if image_url:
                st.image(image_url, width=72)
            else:
                st.markdown(
                    '<div style="width:72px;height:72px;background:#f3f4f6;'
                    'display:flex;align-items:center;justify-content:center;'
                    'font-size:28px;border-radius:6px;">📦</div>',
                    unsafe_allow_html=True,
                )

        # ── Info ──────────────────────────────────────────────────────────────
        with col_info:
            st.markdown(f"**{product.get('name', 'Loading...')}**")

            # Platform badge + availability
            platform_link = (
                f'<a href="{product_url}" target="_blank" '
                f'style="text-decoration:none;color:inherit;">'
                f'{platform_icon} {platform_label} ↗</a>'
                if product_url
                else f"{platform_icon} {platform_label}"
            )
            st.markdown(
                f'<span style="background:#e5e7eb;color:#374151;padding:2px 8px;'
                f'border-radius:999px;font-size:12px;">{platform_link}</span>'
                f'&nbsp;&nbsp;'
                f'<span style="font-size:12px;">{avail_text}</span>',
                unsafe_allow_html=True,
            )

            # Price
            st.markdown(
                f'<div style="font-size:22px;font-weight:700;color:#16a34a;'
                f'margin:4px 0 2px;">{_format_price(price)}</div>',
                unsafe_allow_html=True,
            )

            # Rating + review count
            meta_parts = []
            if rating:
                meta_parts.append(f"⭐ {rating}")
            if review_count:
                meta_parts.append(f"{review_count:,}")
            if meta_parts:
                st.caption("  ·  ".join(meta_parts))

            # Last fetched
            st.caption(f"Last fetched: {last_fetched}")

        # ── Buttons ───────────────────────────────────────────────────────────
        with col_btns:
            if st.button(
                "🔍 View",
                key=f"view_{subscription_id}",
                use_container_width=True,
            ):
                st.session_state.view_product_id     = product.get("product_id")
                st.session_state.navigate_to_product = True
                st.rerun()

            if st.button(
                "🔄 Refresh",
                key=f"refresh_{subscription_id}",
                use_container_width=True,
                help="Refresh from database",
            ):
                from api_client import get_product
                fresh = get_product(product_id)
                if fresh.ok:
                    st.session_state.force_items_reload = True
                    st.rerun()
                else:
                    st.toast("Could not refresh. Try again.", icon="⚠️")

            if st.button(
                "🗑️ Remove",
                key=f"remove_{subscription_id}",
                use_container_width=True,
            ):
                st.session_state.delete_confirm = {
                    "subscription_id": subscription_id,
                    "name": product.get("name", "this product"),
                }
                st.rerun()
