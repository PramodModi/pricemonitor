import html
import os
import re
import uuid
from decimal import Decimal
from typing import Optional

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.core.config import settings
from app.notifications.content.price_drop import (
    PLATFORM_LABEL,
    PLATFORM_ICON,
    CTA_TEXT,
    PRICES_DISCLAIMER,
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


def _extract_first_name(email: str) -> str:
    """Extract and capitalise the first name from an email address local part.

    pramod.modi@gmail.com  →  Pramod
    john_doe@gmail.com     →  John
    alice@gmail.com        →  Alice
    user123@gmail.com      →  ""  (greeting falls back to "Hi,")
    """
    local = email.split("@")[0]
    first_part = re.split(r"[._\-+]", local)[0]
    name = re.sub(r"[^a-zA-Z]", "", first_part)
    return name.capitalize() if len(name) >= 2 else ""


def _build_image_tag(image_url: Optional[str], alt: str) -> str:
    """Return an <img> tag using HTML width/height attributes (not CSS-only).
    CSS-only width/height is stripped by Outlook and Gmail on mobile.
    object-fit:contain is not supported in email clients — omitted.
    Falls back to a text emoji placeholder when no URL is available.
    """
    if image_url:
        return (
            f'<img src="{image_url}" alt="{alt}" '
            f'width="80" height="80" '
            f'style="display:block;border:0;outline:none;" />'
        )
    return (
        '<div style="width:80px;height:80px;background:#f3f4f6;'
        'text-align:center;line-height:80px;font-size:28px;">📦</div>'
    )


class EmailSender:
    """
    Sends price drop notification and subscription confirmation emails via SendGrid.
    HTML and plain-text templates for price drop are loaded from files.
    Subscription confirmation HTML is built inline.
    """

    def __init__(self) -> None:
        key = settings.sendgrid_api_key
        logger.info(f"EmailSender init — api_key={'SET' if key else 'EMPTY'} length={len(key)}")
        self._client = SendGridAPIClient(key)
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
        mrp: Optional[Decimal] = None,
        product_id: Optional[uuid.UUID] = None,
    ) -> bool:
        drop_amount, drop_pct = calculate_drop(old_price, new_price)
        drop_pct_int = round(drop_pct)

        platform_label = PLATFORM_LABEL.get(platform, platform.title())
        cta_text = CTA_TEXT.format(platform_label=platform_label)

        old_fmt = format_inr(old_price)
        new_fmt = format_inr(new_price)
        drop_fmt = format_inr(drop_amount)

        name_short = (product_name[:55] + "…") if len(product_name) > 55 else product_name
        subject = f"Price dropped: {name_short} — now {new_fmt}"
        safe_name = html.escape(product_name)

        first_name = _extract_first_name(to_email)
        greeting = f"Hi {first_name}," if first_name else "Hi,"

        product_image = _build_image_tag(product_image_url, safe_name)

        # MRP row — injected into template only when mrp exists and exceeds current price
        if mrp and mrp > new_price:
            mrp_fmt = format_inr(mrp)
            mrp_row_html = (
                "<tr>"
                '<td style="font-size:13px;color:#9ca3af;padding:0 24px 6px 0;white-space:nowrap;">MRP</td>'
                f'<td style="font-size:13px;color:#9ca3af;text-decoration:line-through;padding-bottom:6px;">{mrp_fmt}</td>'
                "</tr>"
            )
            mrp_row_txt = f"  MRP             {mrp_fmt}\n"
        else:
            mrp_row_html = ""
            mrp_row_txt = ""

        # PricePing product page — shown alongside portal CTA so user can
        # view price history chart without leaving PricePing ecosystem.
        # Falls back to dashboard URL when product_id is not available.
        if product_id:
            base = settings.dashboard_url.replace("/dashboard", "")
            priceping_url = f"{base}/products/{product_id}"
        else:
            priceping_url = settings.dashboard_url

        # Build HTML from template
        html_body = self._html_template
        for placeholder, value in {
            "{{greeting}}": greeting,
            "{{product_image}}": product_image,
            "{{product_name}}": safe_name,
            "{{mrp_row}}": mrp_row_html,
            "{{new_price}}": new_fmt,
            "{{old_price}}": old_fmt,
            "{{drop_amount}}": drop_fmt,
            "{{drop_pct}}": str(drop_pct_int),
            "{{product_url}}": product_url,
            "{{cta_text}}": cta_text,
            "{{prices_disclaimer}}": PRICES_DISCLAIMER,
            "{{priceping_url}}": priceping_url,
            "{{dashboard_url}}": settings.dashboard_url,
        }.items():
            html_body = html_body.replace(placeholder, value)

        # Build plain text from template
        plain_body = self._txt_template
        for placeholder, value in {
            "{{greeting}}": greeting,
            "{{product_name}}": product_name,
            "{{mrp_row}}": mrp_row_txt,
            "{{new_price}}": new_fmt,
            "{{old_price}}": old_fmt,
            "{{drop_amount}}": drop_fmt,
            "{{drop_pct}}": str(drop_pct_int),
            "{{cta_text}}": cta_text,
            "{{product_url}}": product_url,
            "{{priceping_url}}": priceping_url,
            "{{dashboard_url}}": settings.dashboard_url,
        }.items():
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
                f"SendGrid unexpected status — status={response.status_code}, to={to_email}"
            )
            return False
        except Exception as exc:
            body = getattr(exc, "body", None)
            if isinstance(body, bytes):
                body = body.decode("utf-8")
            logger.error(
                f"SendGrid exception — "
                f"to={to_email} "
                f"status={getattr(exc, 'status_code', '?')} "
                f"body={body or str(exc)}"
            )
            return False

    def send_subscription_confirmation(
        self,
        to_email: str,
        product_name: str,
        product_image_url: Optional[str],
        product_url: str,
        current_price: Decimal,
        platform: str,
        product_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Send a confirmation email when a user subscribes to a product."""
        platform_label = PLATFORM_LABEL.get(platform, platform.title())
        platform_icon = PLATFORM_ICON.get(platform, "🛒")
        safe_name = html.escape(product_name)
        price_fmt = format_inr(current_price)

        first_name = _extract_first_name(to_email)
        greeting = f"Hi {first_name}," if first_name else "Hi,"
        name_short = (product_name[:55] + "…") if len(product_name) > 55 else product_name
        subject = f"Monitoring started: {name_short}"

        image_block = _build_image_tag(product_image_url, safe_name)

        if product_id:
            base = settings.dashboard_url.replace("/dashboard", "")
            priceping_url = f"{base}/products/{product_id}"
        else:
            priceping_url = settings.dashboard_url

        html_body = f"""<!DOCTYPE html>
<html lang="en">
<body style="margin:0;padding:0;background:#ffffff;font-family:Arial,Helvetica,sans-serif;color:#111827;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:32px 16px 40px;">
  <table width="520" style="max-width:520px;" cellpadding="0" cellspacing="0">

    <tr><td style="padding-bottom:20px;font-size:15px;line-height:1.5;">
      <p style="margin:0 0 6px;color:#111827;">{greeting}</p>
      <p style="margin:0;color:#374151;">You&#39;re now monitoring this product on PricePing. We&#39;ll email you when the price drops.</p>
    </td></tr>

    <tr><td style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;padding:16px;">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td width="80" valign="top" style="padding-right:16px;">{image_block}</td>
        <td valign="top">
          <p style="margin:0 0 8px;font-size:14px;font-weight:bold;color:#111827;line-height:1.4;">{safe_name}</p>
          <p style="margin:0 0 8px;font-size:12px;color:#6b7280;">{platform_icon} {platform_label}</p>
          <p style="margin:0;font-size:13px;color:#374151;">Current price: <strong style="color:#111827;">{price_fmt}</strong></p>
        </td>
      </tr></table>
    </td></tr>

    <tr><td style="padding:24px 0 6px;">
      <a href="{product_url}" style="display:inline-block;background:#1d4ed8;color:#ffffff;text-decoration:none;padding:11px 22px;border-radius:5px;font-size:14px;font-weight:bold;">View on {platform_label} &#8594;</a>
    </td></tr>

    <tr><td style="padding-bottom:6px;">
      <a href="{priceping_url}" style="font-size:13px;color:#6b7280;text-decoration:underline;">📊 View price history on PricePing</a>
    </td></tr>

    <tr><td style="padding-bottom:28px;">
      <p style="margin:0;font-size:12px;color:#9ca3af;">Prices can change at any time.</p>
    </td></tr>

    <tr><td style="border-top:1px solid #e5e7eb;padding-top:20px;">
      <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.7;">
        You requested price alerts from PricePing.<br>
        To stop monitoring, visit your <a href="{settings.dashboard_url}" style="color:#6b7280;text-decoration:underline;">dashboard</a> and remove the item.
      </p>
    </td></tr>

  </table>
</td></tr>
</table>
</body></html>"""

        plain_body = (
            f"{greeting}\n\n"
            f"You're now monitoring this product on PricePing.\n\n"
            f"{product_name}\n"
            f"Current price: {price_fmt}\n"
            f"Platform: {platform_label}\n\n"
            f"We'll email you when the price drops.\n\n"
            f"View the product:\n{product_url}\n\n"
            f"View price history on PricePing:\n{priceping_url}\n\n"
            f"---\n"
            f"You requested price alerts from PricePing.\n"
            f"To stop monitoring, visit your dashboard:\n{settings.dashboard_url}\n"
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
            logger.error(
                f"SendGrid unexpected status — status={response.status_code}, to={to_email}"
            )
            return False
        except Exception as exc:
            body = getattr(exc, "body", None)
            if isinstance(body, bytes):
                body = body.decode("utf-8")
            logger.error(
                f"SendGrid exception — "
                f"to={to_email} "
                f"status={getattr(exc, 'status_code', '?')} "
                f"body={body or str(exc)}"
            )
            return False
