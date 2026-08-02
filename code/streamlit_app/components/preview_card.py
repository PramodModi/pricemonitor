from datetime import datetime
from typing import Optional
import streamlit as st


def _format_price(price: Optional[float]) -> str:
    if price is None:
        return "N/A"
    try:
        return f"₹{float(price):,.0f}"
    except (ValueError, TypeError):
        return "N/A"

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


def _format_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(
            iso.replace("Z", "+00:00")
        ).strftime("%b %Y")
    except Exception:
        return iso


def render_preview_card(preview: dict) -> None:
    live    = preview["live_data"]
    catalog = preview.get("catalog_data")

    # ── DEBUG: log all live_data fields received in Streamlit ─────────────────
    import logging
    _log = logging.getLogger(__name__)
    _log.info(
        f"[PREVIEW_CARD][debug] live_data keys={list(live.keys())} "
        f"current_price={live.get('current_price')} "
        f"mrp={live.get('mrp')} "
        f"special_price={live.get('special_price')} "
        f"discount_pct={live.get('discount_pct')} "
        f"offers_count={len(live.get('offers') or [])} "
        f"offers_preview={list(live.get('offers') or [])[:2]}"
    )

    # Enrichment fields — present for Flipkart affiliate API, None otherwise
    mrp          = live.get("mrp")
    special_price = live.get("special_price")
    discount_pct  = live.get("discount_pct")
    offers        = live.get("offers") or []

    PLATFORM_DISPLAY = {
        "amazon":   ("Amazon India", "🛒"),
        "flipkart": ("Flipkart",     "🛍️"),
        "myntra":   ("Myntra",       "👗"),
    }

    platform                      = live.get("platform", "amazon")
    platform_label, platform_icon = PLATFORM_DISPLAY.get(platform, (platform.title(), "🛒"))
    availability                  = live.get("availability")
    avail_color                   = "#15803d" if availability else "#b91c1c"
    avail_text                    = "✅ In Stock" if availability else "❌ Out of Stock"
    live_price                    = live.get("current_price")
    last_fetched                  = _format_last_fetched(live.get("scraped_at"))
    product_id                    = catalog.get("product_id") if catalog else None

    with st.container(border=True):

        # ── Row: image | info ─────────────────────────────────────────────────
        col_img, col_info = st.columns([1, 4])

        with col_img:
            image_url = live.get("image_url")
            if image_url:
                st.image(image_url, width=120)
            else:
                st.markdown(
                    '<div style="width:100px;height:100px;background:#f3f4f6;'
                    'text-align:center;line-height:100px;font-size:36px;'
                    'border-radius:6px;">📦</div>',
                    unsafe_allow_html=True,
                )

        with col_info:
            # Name
            st.markdown(f"**{live.get('name', '')}**")

            # Brand
            if live.get("brand"):
                st.caption(f"Brand: {live['brand']}")

            # Platform badge + availability
            st.markdown(
                f'<span style="background:#e5e7eb;color:#374151;padding:3px 10px;'
                f'border-radius:999px;font-size:12px;">'
                f'{platform_icon} {platform_label}</span>'
                f'&nbsp;&nbsp;'
                f'<span style="color:{avail_color};font-size:12px;font-weight:500;">'
                f'{avail_text}</span>',
                unsafe_allow_html=True,
            )

            # ── Price row: price | 🔄 button ──────────────────────────────────
            # Three columns: price takes most of the width, button is snug
            # next to it, spacer fills the rest so button doesn't stretch right.
            col_price, col_btn, col_space = st.columns([3, 1, 2])
            with col_price:
                # ── Selling price + MRP + discount badge ──────────────────────
                # MRP shown with strikethrough only when different from price.
                # Discount badge shown when discount_pct present and > 0.
                # Special price shown when lower than selling price.
                # All enrichment rows hidden for Amazon/Myntra (fields are None).

                price_html_parts = [
                    f'<span style="font-size:28px;font-weight:700;color:#16a34a;">'
                    f'{_format_price(live_price)}</span>'
                ]

                if mrp and live_price and float(mrp) != float(live_price):
                    price_html_parts.append(
                        f'<span style="font-size:16px;color:#9ca3af;'
                        f'text-decoration:line-through;margin-left:8px;">'
                        f'{_format_price(mrp)}</span>'
                    )

                if discount_pct and float(discount_pct) > 0:
                    price_html_parts.append(
                        f'<span style="background:#dcfce7;color:#16a34a;'
                        f'border-radius:4px;padding:2px 7px;font-size:13px;'
                        f'font-weight:600;margin-left:8px;">'
                        f'{float(discount_pct):.0f}% off</span>'
                    )

                st.markdown(
                    f'<div style="margin:6px 0 2px;">'
                    + "".join(price_html_parts)
                    + "</div>",
                    unsafe_allow_html=True,
                )

                # Special price row — only when lower than selling price
                if special_price and live_price and float(special_price) < float(live_price):
                    st.markdown(
                        f'<p style="font-size:13px;color:#2563eb;margin:0 0 4px;">'
                        f'💰 Offer price: <strong>{_format_price(special_price)}</strong>'
                        f'</p>',
                        unsafe_allow_html=True,
                    )

                st.caption(f"Last fetched: {last_fetched}")

            with col_btn:
                # Only show when product is already in DB (catalog_data present)
                if product_id:
                    # Vertical spacer to align button with price text
                    st.markdown(
                        '<div style="margin-top:10px;"></div>',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "🔄",
                        key="preview_refresh",
                        help="Refresh from database",
                        use_container_width=True,
                    ):
                        from api_client import get_product
                        fresh = get_product(str(product_id))
                        if fresh.ok:
                            p = fresh.data
                            live["current_price"] = p.get("current_price", live["current_price"])
                            live["availability"]  = p.get("availability",  live["availability"])
                            live["scraped_at"]    = p.get("last_checked_at", live.get("scraped_at"))
                            live["name"]          = p.get("name",         live["name"])
                            live["brand"]         = p.get("brand",        live.get("brand"))
                            live["seller"]        = p.get("seller",       live.get("seller"))
                            live["rating"]        = p.get("rating",       live.get("rating"))
                            live["review_count"]  = p.get("review_count", live.get("review_count"))
                            st.session_state.preview_result = preview
                            st.rerun()
                        else:
                            st.toast("Could not refresh. Try again.", icon="⚠️")

            # ── Price change indicator ─────────────────────────────────────────
            if catalog and catalog.get("last_tracked_price") and live_price:
                indicator  = catalog.get("price_change_indicator")
                change_amt = catalog.get("price_change_amount", 0)
                last_price = catalog.get("last_tracked_price")
                if indicator == "down":
                    st.markdown(
                        f'<div style="color:#15803d;font-size:13px;font-weight:500;">'
                        f'🟢 ₹{float(change_amt):,.0f} less than last tracked price '
                        f'(₹{float(last_price):,.0f})</div>',
                        unsafe_allow_html=True,
                    )
                elif indicator == "up":
                    st.markdown(
                        f'<div style="color:#b91c1c;font-size:13px;font-weight:500;">'
                        f'🔴 ₹{float(change_amt):,.0f} more than last tracked price '
                        f'(₹{float(last_price):,.0f})</div>',
                        unsafe_allow_html=True,
                    )
                elif indicator == "unchanged":
                    st.caption(f"Same as last tracked price (₹{float(last_price):,.0f})")

            # Rating + reviews
            rating       = live.get("rating")
            review_count = live.get("review_count")
            meta_parts   = []
            if rating:
                meta_parts.append(f"⭐ {rating}")
            if review_count:
                meta_parts.append(f"{int(review_count):,} reviews")
            if meta_parts:
                st.caption("  ·  ".join(meta_parts))

            # Seller
            if live.get("seller"):
                st.caption(f"Sold by: {live['seller']}")

        # ── Bank & card offers — only when present ────────────────────────────
        # offers=[] for Amazon/Myntra/browser-scraped — section stays hidden.
        if offers:
            with st.expander(
                f"🏦 Bank & Card Offers ({len(offers)} available)", expanded=False
            ):
                for offer in offers:
                    offer_text = offer.strip()
                    if offer_text:
                        st.markdown(f"• {offer_text}")

        # ── Catalog stats section ─────────────────────────────────────────────
        st.divider()

        if catalog:
            watcher_count = catalog.get("watcher_count", 0)
            stats         = catalog.get("price_stats")
            drop_count    = stats["drop_count"]              if stats else 0
            all_time_low  = _format_price(stats["all_time_low"])  if stats else "N/A"
            all_time_high = _format_price(stats["all_time_high"]) if stats else "N/A"
            first_tracked = _format_date(stats["first_tracked_at"]) if stats else "N/A"

            cs1, cs2, cs3 = st.columns(3)
            with cs1:
                st.markdown(
                    f'<div style="background:#f3f4f6;border-radius:6px;padding:10px;'
                    f'text-align:center;">'
                    f'<div style="font-size:18px;font-weight:700;">👥 {watcher_count}</div>'
                    f'<div style="font-size:11px;color:#6b7280;text-transform:uppercase;">'
                    f'Watchers</div></div>',
                    unsafe_allow_html=True,
                )
            with cs2:
                st.markdown(
                    f'<div style="background:#f3f4f6;border-radius:6px;padding:10px;'
                    f'text-align:center;">'
                    f'<div style="font-size:18px;font-weight:700;">📉 {drop_count}</div>'
                    f'<div style="font-size:11px;color:#6b7280;text-transform:uppercase;">'
                    f'Price Checks</div></div>',
                    unsafe_allow_html=True,
                )
            with cs3:
                st.markdown(
                    f'<div style="background:#f3f4f6;border-radius:6px;padding:10px;'
                    f'text-align:center;">'
                    f'<div style="font-size:18px;font-weight:700;">{all_time_low}</div>'
                    f'<div style="font-size:11px;color:#6b7280;text-transform:uppercase;">'
                    f'All-Time Low</div></div>',
                    unsafe_allow_html=True,
                )

            st.caption(f"Highest ever: {all_time_high}  ·  Tracked since: {first_tracked}")

        else:
            st.caption("✨ Be the first to track this product!")
