import os
import re
from datetime import datetime
from typing import Optional
import streamlit as st


def _render_html(html: str) -> None:
    """Strip newlines and render HTML via st.markdown."""
    clean = re.sub(r'\s+', ' ', html).strip()
    st.markdown(clean, unsafe_allow_html=True)

def _load_html(filename: str) -> str:
    path = os.path.join(
        os.path.dirname(__file__), "..", "static", "html", filename
    )
    with open(path, "r") as f:
        return f.read()


def _format_price(price: Optional[float]) -> str:
    if price is None:
        return "N/A"
    try:
        return f"₹{float(price):,.0f}"
    except (ValueError, TypeError):
        return "N/A"


def _format_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(
            iso.replace("Z", "+00:00")
        ).strftime("%b %Y")
    except Exception:
        return iso


def render_preview_card(preview: dict) -> None:
    live = preview["live_data"]
    catalog = preview.get("catalog_data")

    # Image
    image_url = live.get("image_url")
    if image_url:
        image_block = (
            f'<img src="{image_url}" '
            f'style="width:120px;height:120px;object-fit:contain;" />'
        )
    else:
        image_block = (
            '<div style="width:100px;height:100px;background:#f3f4f6;'
            'text-align:center;line-height:100px;font-size:36px;'
            'border-radius:6px;">📦</div>'
        )

    # Platform
    platform = live.get("platform", "amazon")
    platform_label = "Amazon India" if platform == "amazon" else "Flipkart"
    platform_icon = "🛒" if platform == "amazon" else "🛍️"

    # Availability
    availability = live.get("availability")
    avail_color = "#15803d" if availability else "#b91c1c"
    avail_text = "✅ In Stock" if availability else "❌ Out of Stock"

    # Brand
    brand = live.get("brand")
    brand_html = (
        f'<div style="font-size:12px;color:#6b7280;margin:2px 0;">Brand: {brand}</div>'
        if brand else ""
    )

    # Live price
    live_price = live.get("current_price")
    live_price_fmt = _format_price(live_price)

    # Price change
    price_change_html = ""
    if catalog and catalog.get("last_tracked_price") and live_price:
        indicator = catalog.get("price_change_indicator")
        change_amt = catalog.get("price_change_amount", 0)
        last = catalog.get("last_tracked_price")
        if indicator == "down":
            price_change_html = (
                f'<div style="color:#15803d;font-size:13px;font-weight:500;">'
                f'🟢 ₹{float(change_amt):,.0f} less than last tracked price '
                f'(₹{float(last):,.0f})</div>'
            )
        elif indicator == "up":
            price_change_html = (
                f'<div style="color:#b91c1c;font-size:13px;font-weight:500;">'
                f'🔴 ₹{float(change_amt):,.0f} more than last tracked price '
                f'(₹{float(last):,.0f})</div>'
            )
        else:
            price_change_html = (
                f'<div style="font-size:12px;color:#6b7280;">'
                f'Same as last tracked price (₹{float(last):,.0f})</div>'
            )

    # Rating and seller
    rating = live.get("rating")
    review_count = live.get("review_count")
    meta_parts = []
    if rating:
        meta_parts.append(f"⭐ {rating}")
    if review_count:
        meta_parts.append(f"{int(review_count):,} reviews")
    rating_html = (
        f'<div style="font-size:12px;color:#6b7280;margin:2px 0;">'
        f'{"  ·  ".join(meta_parts)}</div>'
        if meta_parts else ""
    )

    seller = live.get("seller")
    seller_html = (
        f'<div style="font-size:12px;color:#6b7280;margin:2px 0;">'
        f'Sold by: {seller}</div>'
        if seller else ""
    )

    # Catalog section
    if catalog:
        watcher_count = catalog.get("watcher_count", 0)
        stats = catalog.get("price_stats")
        drop_count = stats["drop_count"] if stats else 0
        all_time_low = _format_price(stats["all_time_low"]) if stats else "N/A"
        all_time_high = _format_price(stats["all_time_high"]) if stats else "N/A"
        first_tracked = _format_date(stats["first_tracked_at"]) if stats else "N/A"

        catalog_html = f"""
        <div style="border-top:1px solid #e5e7eb;margin-top:16px;padding-top:16px;">
            <div style="display:flex;gap:12px;margin-bottom:8px;">
                <div style="flex:1;background:#f3f4f6;border-radius:6px;
                            padding:10px;text-align:center;">
                    <div style="font-size:18px;font-weight:700;">👥 {watcher_count}</div>
                    <div style="font-size:11px;color:#6b7280;text-transform:uppercase;">Watchers</div>
                </div>
                <div style="flex:1;background:#f3f4f6;border-radius:6px;
                            padding:10px;text-align:center;">
                    <div style="font-size:18px;font-weight:700;">📉 {drop_count}</div>
                    <div style="font-size:11px;color:#6b7280;text-transform:uppercase;">Price Drops</div>
                </div>
                <div style="flex:1;background:#f3f4f6;border-radius:6px;
                            padding:10px;text-align:center;">
                    <div style="font-size:18px;font-weight:700;">{all_time_low}</div>
                    <div style="font-size:11px;color:#6b7280;text-transform:uppercase;">All-Time Low</div>
                </div>
            </div>
            <div style="font-size:12px;color:#6b7280;">
                Highest ever: {all_time_high} &nbsp;·&nbsp; Tracked since: {first_tracked}
            </div>
        </div>
        """
    else:
        catalog_html = """
        <div style="border-top:1px solid #e5e7eb;margin-top:16px;padding-top:16px;">
            <div style="font-size:13px;color:#6b7280;">✨ Be the first to track this product!</div>
        </div>
        """

    html = f"""
    <div style="border:1px solid #e5e7eb;border-radius:8px;padding:20px;background:#f9fafb;">
        <div style="display:flex;align-items:flex-start;gap:16px;">
            <div style="flex-shrink:0;">{image_block}</div>
            <div style="flex:1;">
                <div style="font-size:16px;font-weight:600;color:#111827;
                            margin:0 0 4px;">{live.get("name", "")}</div>
                {brand_html}
                <div style="margin:6px 0;">
                    <span style="background:#e5e7eb;color:#374151;padding:3px 10px;
                                 border-radius:999px;font-size:12px;">
                        {platform_icon} {platform_label}
                    </span>
                    &nbsp;
                    <span style="color:{avail_color};font-size:12px;font-weight:500;">
                        {avail_text}
                    </span>
                </div>
                <div style="font-size:28px;font-weight:700;color:#16a34a;margin:8px 0 2px;">
                    {live_price_fmt}
                </div>
                <div style="font-size:12px;color:#6b7280;">Live price from marketplace</div>
                {price_change_html}
                {rating_html}
                {seller_html}
            </div>
        </div>
        {catalog_html}
    </div>
    """

    _render_html(html)