import os
import streamlit as st
from dataclasses import dataclass


@dataclass
class Config:
    api_base_url: str


def _get_api_base_url() -> str:
    # Try Streamlit secrets first (production)
    try:
        return st.secrets["API_BASE_URL"]
    except Exception:
        # Fall back to environment variable (local)
        return os.environ.get("API_BASE_URL", "http://localhost:8001")


settings = Config(
    api_base_url=_get_api_base_url()
)