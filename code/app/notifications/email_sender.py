import html
import os
from decimal import Decimal
from typing import Optional

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.core.config import settings
from app.notifications.content.price_drop import (
    get_subject,
    get_preheader,
    PLATFORM_LABEL,
    PLATFORM_ICON,
    CTA_TEXT,
    FOOTER_TEXT,
    FOOTER_UNSUBSCRIBE,
    PRICES_DISCLAIMER,
    MAJOR_DROP_LABEL,
    MAJOR_DROP_THRESHOLD_PCT,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def format_inr(amount: Decimal) -> str:
    return f"₹{amount:,.0f}"


def calculate_drop(old_price: Decimal, new_price: Decimal) -> tuple[Decimal, float]:
    drop_amount = old_price - new_price
    drop_pct = float(drop_amount / old_price * 100)
    return drop_amount, drop_pct


def _load_template(filename: str) -> str:
    path = os.path.join(_TEMPLATES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _append_affiliate_tag(url: str, platform: str) -> str:
    """Append affiliate tracking parameter to product URL."""
    if platform == "amazon" and settings.amazon_affiliate_tag:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}tag={settings.amazon_affiliate_tag}"
    if platform == "flipkart" and settings.flipkart_affiliate_id:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}affid={settings.flipkart_affiliate_id}"
    return url

class EmailSender:
    """
    Sends price drop notification emails via SendGrid.
    HTML template, plain-text template, and copy are loaded from files —
    no content is hardcoded here.
    """

    def __init__(self) -> None:
        self._client = SendGridAPIClient(settings.sendgrid_api_key)
        self._html_template = _load_template("price_drop.html")
        self._txt_template = _load_template("price_drop.txt")

    def send_price_drop(
        self,
        to_email: str,
        product_name: str,
        product_image_url: Optional[str],
        product_url: str,
        old_price: Decimal,
        new_price: Decimal,
        platform: str,
    ) -> bool:
        # Append affiliate tag before building email
        product_url = _append_affiliate_tag(product_url, platform)

        drop_amount, drop_pct = calculate_drop(old_price, new_price)
        drop_pct_int = round(drop_pct)

        platform_label = PLATFORM_LABEL.get(platform, platform.title())
        platform_icon = PLATFORM_ICON.get(platform, "🛒")

        old_fmt = format_inr(old_price)
        new_fmt = format_inr(new_price)
        drop_fmt = format_inr(drop_amount)

        subject = get_subject(product_name, new_fmt)
        safe_name = html.escape(product_name)

        major_drop_label = (
            f'<p style="color:#15803d;font-size:14px;font-weight:bold;margin:0 0 8px;">'
            f'{MAJOR_DROP_LABEL}</p>'
            if drop_pct_int >= MAJOR_DROP_THRESHOLD_PCT
            else ""
        )

        if product_image_url:
            product_image = (
                f'<img src="{product_image_url}" alt="{safe_name}" '
                f'style="max-width:120px;max-height:120px;'
                f'object-fit:contain;display:block;" />'
            )
        else:
            product_image = (
                '<div style="width:80px;height:80px;background:#e5e7eb;'
                'text-align:center;line-height:80px;font-size:32px;">📦</div>'
            )

        footer_text = FOOTER_TEXT.format(product_name=safe_name)
        cta_text = CTA_TEXT.format(platform_label=platform_label)

        # Build HTML by replacing placeholders in template
        html_body = self._html_template
        replacements = {
            "{{major_drop_label}}": major_drop_label,
            "{{old_price}}": old_fmt,
            "{{new_price}}": new_fmt,
            "{{drop_amount}}": drop_fmt,
            "{{drop_pct}}": str(drop_pct_int),
            "{{product_image}}": product_image,
            "{{product_name}}": safe_name,
            "{{platform_icon}}": platform_icon,
            "{{platform_label}}": platform_label,
            "{{product_url}}": product_url,
            "{{cta_text}}": cta_text,
            "{{prices_disclaimer}}": PRICES_DISCLAIMER,
            "{{footer_text}}": footer_text,
            "{{footer_unsubscribe}}": FOOTER_UNSUBSCRIBE,
            "{{dashboard_url}}": settings.dashboard_url,
        }
        for placeholder, value in replacements.items():
            html_body = html_body.replace(placeholder, value)

        # Build plain text
        plain_body = self._txt_template
        plain_replacements = {
            "{{product_name}}": product_name,
            "{{old_price}}": old_fmt,
            "{{new_price}}": new_fmt,
            "{{drop_amount}}": drop_fmt,
            "{{drop_pct}}": str(drop_pct_int),
            "{{platform_label}}": platform_label,
            "{{product_url}}": product_url,
            "{{dashboard_url}}": settings.dashboard_url,
        }
        for placeholder, value in plain_replacements.items():
            plain_body = plain_body.replace(placeholder, value)

        message = Mail(
            from_email=(settings.email_from_address, settings.email_from_name),
            to_emails=to_email,
            subject=subject,
            html_content=html_body,
            plain_text_content=plain_body,
        )
        message.reply_to = settings.email_reply_to

        try:
            response = self._client.send(message)
            if response.status_code == 202:
                logger.info(f"Email sent — to={to_email}, subject={subject}")
                return True
            logger.error(
                f"SendGrid unexpected status — "
                f"status={response.status_code}, to={to_email}"
            )
            return False
        except Exception as exc:
            logger.error(f"SendGrid exception — to={to_email}, error={str(exc)}")
            return False

    