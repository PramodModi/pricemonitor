def get_subject(product_name: str) -> str:
    return f"Your tracked item dropped — {product_name[:60]}"


def get_preheader(old_price_fmt: str, drop_amount_fmt: str, drop_pct: int) -> str:
    return f"Down from {old_price_fmt} — save {drop_amount_fmt} ({drop_pct}% off)"


# CTA button label per platform
PLATFORM_LABEL = {
    "amazon": "Amazon India",
    "flipkart": "Flipkart",
    "myntra": "Myntra",
}

PLATFORM_ICON = {
    "amazon": "🛒",
    "flipkart": "🛍️",
    "myntra": "👗",
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

MAJOR_DROP_THRESHOLD_PCT = 15

# Confirmation email content
CONFIRMATION_SUBJECT = "You're now tracking {product_name}"

CONFIRMATION_BODY = (
    "You've successfully subscribed to price alerts for {product_name}. "
    "We'll notify you when the price changes."
)