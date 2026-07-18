import os
from datetime import datetime, timezone
from typing import Optional
import streamlit as st


def _load_html(filename: str) -> str:
    path = os.path.join(
        os.path.dirname(__file__), "..", "static", "html", filename
    )
    with open(path, "r") as f:
        return f.read()


def _format_last_checked(ts: Optional[str]) -> str:
    if ts is None:
        return "Not yet checked"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - dt
        minutes = int(diff.total_seconds() / 60)
        if minutes < 60:
            return f"{minutes}m ago"
        if minutes < 1440:
            return f"{minutes // 60}h ago"
        return f"{minutes // 1440}d ago"
    except Exception:
        return "Unknown"


def _format_price(price: Optional[float]) -> str:
    if price is None:
        return "Price unavailable"
    try:
        return f"₹{float(price):,.0f}"
    except (ValueError, TypeError):
        return "Price unavailable"


def render_product_card(item: dict) -> None:
    product = item["product"]
    subscription_id = item["subscription_id"]

    template = _load_html("product_card.html")

    # Image block
    image_url = product.get("image_url")
    if image_url:
        image_block = (
            f'<img src="{image_url}" '
            f'style="width:72px;height:72px;object-fit:contain;" />'
        )
    else:
        image_block = (
            '<div style="width:72px;height:72px;background:#f3f4f6;'
            'display:flex;align-items:center;justify-content:center;'
            'font-size:28px;border-radius:6px;">📦</div>'
        )

    # Platform
    platform = product.get("platform", "amazon")
    platform_label = "Amazon India" if platform == "amazon" else "Flipkart"
    platform_icon = "🛒" if platform == "amazon" else "🛍️"

    # Availability
    availability = product.get("availability")
    if availability:
        availability_class = "availability-in"
        availability_text = "✅ In Stock"
    else:
        availability_class = "availability-out"
        availability_text = "❌ Out of Stock"

    # Price block
    price = product.get("current_price")
    rating = product.get("rating")
    review_count = product.get("review_count")
    meta_parts = []
    if rating:
        meta_parts.append(f"⭐ {rating}")
    if review_count:
        meta_parts.append(f"{review_count:,}")
    meta_str = "  ·  ".join(meta_parts)

    price_block = f'<div class="product-price">{_format_price(price)}</div>'
    if meta_str:
        price_block += f'<div class="product-meta">{meta_str}</div>'

    html = template
    html = html.replace("{image_block}", image_block)
    html = html.replace("{product_name}", product.get("name", "Loading..."))
    html = html.replace("{platform_icon}", platform_icon)
    html = html.replace("{platform_label}", platform_label)
    html = html.replace("{availability_class}", availability_class)
    html = html.replace("{availability_text}", availability_text)
    html = html.replace("{price_block}", price_block)
    html = html.replace("{last_checked}", _format_last_checked(product.get("last_checked_at")))

    col1, col2 = st.columns([10, 1])
    with col1:
        st.markdown(html, unsafe_allow_html=True)
    with col2:
        if st.button("🗑️", key=f"remove_{subscription_id}", help="Remove"):
            st.session_state.delete_confirm = {
                "subscription_id": subscription_id,
                "name": product.get("name", "this product"),
            }
            st.rerun()