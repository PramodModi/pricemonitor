import os
import streamlit as st
from dataclasses import dataclass


@dataclass
class Config:
    api_base_url: str
    amazon_affiliate_tag: str
    flipkart_affiliate_id: str


def _get_api_base_url() -> str:
    try:
        return st.secrets["API_BASE_URL"]
    except Exception:
        return os.environ.get("API_BASE_URL", "http://localhost:8001")


def _get_amazon_affiliate_tag() -> str:
    try:
        return st.secrets["AMAZON_AFFILIATE_TAG"]
    except Exception:
        return os.environ.get("AMAZON_AFFILIATE_TAG", "")


def _get_flipkart_affiliate_id() -> str:
    try:
        return st.secrets["FLIPKART_AFFILIATE_ID"]
    except Exception:
        return os.environ.get("FLIPKART_AFFILIATE_ID", "")


settings = Config(
    api_base_url=_get_api_base_url(),
    amazon_affiliate_tag=_get_amazon_affiliate_tag(),
    flipkart_affiliate_id=_get_flipkart_affiliate_id(),
)