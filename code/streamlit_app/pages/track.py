import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import streamlit as st
from api_client import preview_product, confirm_subscription
from components.preview_card import render_preview_card


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

def _show_preview_error(code: str, message: str) -> None:
    if code == "INVALID_URL":
        st.error(
            "❌ That doesn't look like a valid product URL. "
            "Please paste a direct product link from Amazon India or Flipkart.\n\n"
            "**Example:** https://www.amazon.in/dp/B0CHX1W1XY"
        )
    elif code == "UNSUPPORTED_PLATFORM":
        st.error(
            "❌ Only Amazon India (amazon.in) and Flipkart (flipkart.com) "
            "are supported right now."
        )
    elif code in ("SCRAPE_BLOCKED", "SCRAPE_FAILED"):
        st.warning(
            "⚠️ We couldn't fetch that product right now. "
            "The marketplace may be temporarily blocking requests. "
            "Please try again in a few minutes."
        )
    elif code == "TIMEOUT":
        st.warning(
            "⚠️ The request timed out. The server is taking too long — "
            "please try again."
        )
    elif code == "CONNECTION_ERROR":
        st.error(
            "❌ Cannot reach the PriceMonitor server. "
            "Please check your connection."
        )
    else:
        st.error(
            f"❌ Could not fetch that product. "
            f"Please check the URL and try again.\n\n"
            f"_(Error: {code} — {message})_"
        )


def _show_confirm_error(code: str, message: str) -> None:
    if code == "PREVIEW_NOT_FOUND":
        st.warning("Your preview expired. Please search for the product again.")
        st.session_state.track_step = "input"
        st.session_state.preview_result = None
        st.rerun()
    else:
        st.error(f"Could not complete tracking: {message}")


init_session_state()

st.title("➕ Track New Item")

# ── STATE: input ──────────────────────────────────────────────────────────────
if st.session_state.track_step == "input":
    st.write(
        "Paste a product URL from Amazon India or Flipkart or Myntra and we'll "
        "show you the details before you start tracking."
    )

    with st.form("url_form", border=True):
        url = st.text_input(
            "Product URL",
            placeholder="Enter product url... ",
        )
        submitted = st.form_submit_button(
            "Fetch Product Details",
            type="primary",
            use_container_width=True,
        )

    st.caption("✅ Supported: Amazon India·Flipkart . Myntra")

    if submitted:
        if not url.strip():
            st.error("Please enter a product URL.")
            st.stop()

        with st.spinner("Fetching live product details — this may take up to 30 seconds..."):
            result = preview_product(url.strip())

        if result.ok:
            st.session_state.preview_result = result.data
            st.session_state.track_step = "preview"
            st.rerun()
        else:
            _show_preview_error(result.error_code, result.error_message)

# ── STATE: preview ────────────────────────────────────────────────────────────
elif st.session_state.track_step == "preview":
    preview = st.session_state.preview_result
    if not preview:
        st.session_state.track_step = "input"
        st.rerun()

    st.subheader("Is this the right product?")
    render_preview_card(preview)

    email = st.text_input(
        "📧 Your email — we'll notify you here when the price changes",
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
                    preview["preview_id"],
                    email.strip().lower(),
                )

            if result.ok:
                st.session_state.user_email = email.strip().lower()
                st.session_state.view_product_id = result.data["product"]["product_id"]
                st.session_state.track_step = "success"
                st.session_state.preview_result = None
                st.rerun()
            else:
                _show_confirm_error(result.error_code, result.error_message)

# ── STATE: success ────────────────────────────────────────────────────────────
elif st.session_state.track_step == "success":
    with st.container(border=True):
        st.success("🎉 You're now tracking this product!")
        st.write(
            f"We'll email **{st.session_state.user_email}** "
            f"when the price changes."
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "View Product Details →",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.track_step = "input"
                st.switch_page("pages/product.py")
        with col2:
            if st.button(
                "← Back to Dashboard",
                use_container_width=True,
            ):
                st.session_state.track_step = "input"
                st.switch_page("pages/dashboard.py")


