import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import streamlit as st
from api_client import get_items, delete_subscription
from components.product_card import render_product_card
from components.empty_state import render_empty_state


def init_session_state():
    defaults = {
        "user_email": None,
        "track_step": "input",
        "preview_result": None,
        "delete_confirm": None,
        "view_product_id": None,
        "navigate_to_product": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()

# ── Check if we need to navigate to product page ──────────────────
if st.session_state.navigate_to_product and st.session_state.view_product_id:
    st.session_state.navigate_to_product = False
    st.switch_page("pages/product.py")

st.title("📋 My Tracked Items")

with st.container(border=True):
    col1, col2 = st.columns([4, 1])
    with col1:
        email_input = st.text_input(
            "Email",
            value=st.session_state.user_email or "",
            placeholder="you@example.com",
            label_visibility="collapsed",
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
st.caption(
    f"Showing {count} item{'s' if count != 1 else ''} "
    f"for **{st.session_state.user_email}**"
)

# Delete confirmation dialog
if st.session_state.delete_confirm:
    pending = st.session_state.delete_confirm
    with st.container(border=True):
        st.warning(f"Remove **{pending['name']}** from your tracking list?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, remove", type="primary", use_container_width=True):
                res = delete_subscription(
                    pending["subscription_id"],
                    st.session_state.user_email,
                )
                st.session_state.delete_confirm = None
                if res.ok:
                    st.success("Product removed.")
                else:
                    st.error(res.error_message)
                st.rerun()
        with col2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.delete_confirm = None
                st.rerun()

if count == 0:
    render_empty_state()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button(
            "➕ Track Your First Item",
            use_container_width=True,
            type="primary",
        ):
            st.switch_page("pages/track.py")
    st.stop()
# Navigate to product page if view button was clicked
if st.session_state.get("view_product_id") and st.session_state.get("navigate_to_product"):
    st.session_state.navigate_to_product = False
    st.switch_page("pages/product.py")

for item in items:
    render_product_card(item)