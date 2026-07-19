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
    CONFIRMATION_SUBJECT,
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

    def send_subscription_confirmation(
    self,
    to_email: str,
    product_name: str,
    product_image_url: Optional[str],
    product_url: str,
    current_price: Decimal,
    platform: str,
    ) -> bool:
        """
        Send a confirmation email when a user subscribes to a product.
        """
        platform_label = PLATFORM_LABEL.get(platform, platform.title())
        platform_icon = PLATFORM_ICON.get(platform, "🛒")
        safe_name = html.escape(product_name)
        price_fmt = format_inr(current_price)
        subject = CONFIRMATION_SUBJECT.format(product_name=product_name[:60])

        if product_image_url:
            image_block = (
                f'<img src="{product_image_url}" alt="{safe_name}" '
                f'style="max-width:120px;max-height:120px;object-fit:contain;display:block;" />'
            )
        else:
            image_block = (
                '<div style="width:80px;height:80px;background:#e5e7eb;'
                'text-align:center;line-height:80px;font-size:32px;">📦</div>'
            )

        html_body = f"""<!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
    <table width="100%" bgcolor="#f3f4f6" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:24px 16px;">
    <table width="600" style="max-width:600px;background:#ffffff;border-radius:8px;overflow:hidden;">

    <tr><td bgcolor="#1a1a2e" style="padding:24px 32px;">
        <span style="color:#ffffff;font-size:22px;font-weight:bold;letter-spacing:1px;">👁️ PRICEMONITOR</span><br>
        <span style="color:#a0a0c0;font-size:12px;text-transform:uppercase;letter-spacing:2px;">Tracking Confirmed</span>
    </td></tr>

    <tr><td bgcolor="#ffffff" style="padding:32px 32px 16px 32px;">
        <p style="color:#111827;font-size:18px;font-weight:600;margin:0 0 8px;">You're now tracking this product!</p>
        <p style="color:#6b7280;font-size:14px;margin:0;">We'll email you at <strong>{to_email}</strong> when the price drops.</p>
    </td></tr>

    <tr><td bgcolor="#f9fafb" style="padding:24px 32px;border-top:1px solid #e5e7eb;">
        <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td width="120" valign="top">{image_block}</td>
        <td style="padding-left:16px;" valign="top">
            <p style="font-size:16px;font-weight:600;color:#111827;margin:0 0 8px;">{safe_name}</p>
            <span style="background:#e5e7eb;color:#374151;padding:3px 10px;border-radius:999px;font-size:12px;">{platform_icon} {platform_label}</span>
            <p style="font-size:20px;font-weight:700;color:#16a34a;margin:8px 0 0;">Current price: {price_fmt}</p>
        </td>
        </tr></table>
    </td></tr>

    <tr><td bgcolor="#ffffff" style="padding:24px 32px;text-align:center;">
        <a href="{product_url}" style="background:#1d4ed8;color:#ffffff;padding:14px 32px;border-radius:6px;font-size:16px;font-weight:bold;text-decoration:none;display:inline-block;">View on {platform_label} →</a>
        <p style="font-size:12px;color:#6b7280;margin:12px 0 0;">Prices can change at any time.</p>
    </td></tr>

    <tr><td bgcolor="#f3f4f6" style="padding:24px 32px;border-top:1px solid #e5e7eb;text-align:center;">
        <p style="font-size:12px;color:#6b7280;margin:0;">
        You're receiving this because you subscribed to price alerts for {safe_name} on PriceMonitor.<br><br>
        To stop tracking, visit your <a href="{settings.dashboard_url}" style="color:#4b5563;">dashboard</a> and remove the item.
        </p>
    </td></tr>

    </table></td></tr></table>
    </body></html>"""

        plain_body = (
            f"PRICEMONITOR — TRACKING CONFIRMED\n"
            f"==================================\n\n"
            f"You're now tracking {product_name}!\n\n"
            f"Current price: {price_fmt}\n"
            f"Platform: {platform_label}\n\n"
            f"We'll email you at {to_email} when the price drops.\n\n"
            f"View the product:\n{product_url}\n\n"
            f"---\n"
            f"To stop tracking, visit your dashboard: {settings.dashboard_url}\n"
        )

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
                logger.info(f"Confirmation email sent — to={to_email}")
                return True
            logger.error(f"SendGrid unexpected status — status={response.status_code}, to={to_email}")
            return False
        except Exception as exc:
            logger.error(f"SendGrid exception — to={to_email}, error={str(exc)}")
            return False    