from decimal import Decimal


def get_subject(product_name: str, new_price_fmt: str) -> str:
    return f"Price drop: {product_name[:60]} is now {new_price_fmt}"


def get_preheader(old_price_fmt: str, drop_amount_fmt: str, drop_pct: int) -> str:
    return f"Down from {old_price_fmt} — save {drop_amount_fmt} ({drop_pct}% off)"


# CTA button label per platform
PLATFORM_LABEL = {
    "amazon": "Amazon India",
    "flipkart": "Flipkart",
}

PLATFORM_ICON = {
    "amazon": "🛒",
    "flipkart": "🛍️",
}

CTA_TEXT = "View on {platform_label} →"

FOOTER_TEXT = (
    "You're receiving this because you're tracking "
    "{product_name} on Pricemonitor."
)

FOOTER_UNSUBSCRIBE = (
    "To stop tracking, visit your dashboard and remove the item."
)

PRICES_DISCLAIMER = "Prices can change at any time."

MAJOR_DROP_LABEL = "🔥 Major price drop!"

MAJOR_DROP_THRESHOLD_PCT = 50