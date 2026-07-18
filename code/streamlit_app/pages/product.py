import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
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
        st.markdown(
            '<div style="font-size:48px;text-align:center;">📦</div>',
            unsafe_allow_html=True,
        )

with col_info:
    st.markdown(f"## {p.get('name', 'Product')}")
    if p.get("brand"):
        st.caption(f"Brand: {p['brand']}")

    platform = p.get("platform", "amazon")
    platform_label = "🛒 Amazon India" if platform == "amazon" else "🛍️ Flipkart"
    avail = "✅ In Stock" if p.get("availability") else "❌ Out of Stock"
    st.caption(f"{platform_label}  ·  {avail}")

    if p.get("current_price"):
        st.markdown(f"### ₹{p['current_price']:,.0f}")

    meta = []
    if p.get("rating"):
        meta.append(f"⭐ {p['rating']}")
    if p.get("review_count"):
        meta.append(f"{p['review_count']:,} reviews")
    if meta:
        st.caption("  ·  ".join(meta))

    if p.get("seller"):
        st.caption(f"Sold by: {p['seller']}")

    if p.get("last_checked_at"):
        st.caption(f"Last checked: {p['last_checked_at']}")

    st.link_button(
        f"View on {'Amazon India' if platform == 'amazon' else 'Flipkart'} →",
        url=p["url"],
        type="primary",
    )

# Price stats
stats = p.get("price_stats")
if stats:
    st.divider()
    st.subheader("Price History")
    col1, col2, col3 = st.columns(3)
    col1.metric("All-Time Low", f"₹{stats['all_time_low']:,.0f}")
    col2.metric("All-Time High", f"₹{stats['all_time_high']:,.0f}")
    col3.metric("Price Drops", stats["drop_count"])
    if stats.get("first_tracked_at"):
        st.caption(f"Tracked since {stats['first_tracked_at'][:10]}")

if p.get("watcher_count"):
    st.caption(f"👥 {p['watcher_count']} people watching this product")

st.divider()
if st.button("← Back to My Items"):
    st.switch_page("pages/dashboard.py")