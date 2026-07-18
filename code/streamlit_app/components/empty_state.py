import os
import streamlit as st


def _load_html(filename: str) -> str:
    path = os.path.join(
        os.path.dirname(__file__), "..", "static", "html", filename
    )
    with open(path, "r") as f:
        return f.read()


def render_empty_state() -> None:
    html = _load_html("empty_state.html")
    st.markdown(html, unsafe_allow_html=True)