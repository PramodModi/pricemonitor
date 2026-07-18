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