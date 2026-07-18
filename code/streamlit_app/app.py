import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from api_client import get_health


st.set_page_config(
    page_title="PriceMonitor",
    page_icon="👁️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Load custom CSS
css_path = os.path.join(os.path.dirname(__file__), "static", "css", "main.css")
with open(css_path) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Health check
health = get_health()
if not health.ok:
    st.warning("⚠️ PriceMonitor is experiencing issues. Some features may not work.")

# Navigation
dashboard = st.Page("pages/dashboard.py", title="My Items",        icon="📋", default=True)
track     = st.Page("pages/track.py",     title="Track New Item",  icon="➕")
product   = st.Page("pages/product.py",   title="Product Details", icon="📦")
settings  = st.Page("pages/settings.py",  title="Settings",        icon="⚙️")

pg = st.navigation([dashboard, track, settings, product])
pg.run()