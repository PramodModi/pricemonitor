import os
from decimal import Decimal

from app.notifications.email_sender import EmailSender, format_inr, calculate_drop


# ── Change this to your own email to receive the test email ──────────────────
TEST_EMAIL = "pramodkmodi@gmail.com"

# ── Sample product data ───────────────────────────────────────────────────────
PRODUCT_NAME = "Apple iPhone 15 (128 GB) - Black"
PRODUCT_IMAGE_URL = "https://m.media-amazon.com/images/I/61cNRBTEFkL._SX679_.jpg"
PRODUCT_URL = "https://www.amazon.in/Apple-iPhone-15-128GB-Black/dp/B0CHX1W1XY"
OLD_PRICE = Decimal("79999.00")
NEW_PRICE = Decimal("69999.00")
PLATFORM = "amazon"


def test_format_inr():
    print("\n── format_inr ───────────────────────────────────────────────────")
    assert format_inr(Decimal("69999.00")) == "₹69,999"
    assert format_inr(Decimal("1000.00")) == "₹1,000"
    assert format_inr(Decimal("129999.00")) == "₹1,29,999" or \
           format_inr(Decimal("129999.00")) == "₹129,999"  # standard comma format
    print("✅ format_inr: formats prices correctly")


def test_calculate_drop():
    print("\n── calculate_drop ───────────────────────────────────────────────")
    drop_amount, drop_pct = calculate_drop(Decimal("79999.00"), Decimal("69999.00"))
    assert drop_amount == Decimal("10000.00")
    assert round(drop_pct, 1) == 12.5
    print(f"✅ calculate_drop: amount=₹{drop_amount}, pct={round(drop_pct, 1)}%")


def test_template_loading():
    print("\n── Template loading ─────────────────────────────────────────────")
    sender = EmailSender()
    assert "{{product_name}}" in sender._html_template or \
           "{{old_price}}" in sender._html_template, \
           "HTML template does not contain expected placeholders"
    assert "{{product_name}}" in sender._txt_template, \
           "Plain text template does not contain expected placeholders"
    print("✅ HTML template loaded with placeholders")
    print("✅ Plain text template loaded with placeholders")


def test_placeholder_replacement():
    print("\n── Placeholder replacement ──────────────────────────────────────")
    sender = EmailSender()

    # Call internal build methods directly to verify replacement without sending
    drop_amount, drop_pct = calculate_drop(OLD_PRICE, NEW_PRICE)
    drop_pct_int = round(drop_pct)

    from app.notifications.content.price_drop import (
        PLATFORM_LABEL, PLATFORM_ICON, CTA_TEXT,
        FOOTER_TEXT, FOOTER_UNSUBSCRIBE, PRICES_DISCLAIMER,
        MAJOR_DROP_LABEL, MAJOR_DROP_THRESHOLD_PCT,
    )
    from app.notifications.email_sender import format_inr
    import html

    safe_name = html.escape(PRODUCT_NAME)
    old_fmt = format_inr(OLD_PRICE)
    new_fmt = format_inr(NEW_PRICE)
    drop_fmt = format_inr(drop_amount)
    platform_label = PLATFORM_LABEL[PLATFORM]
    platform_icon = PLATFORM_ICON[PLATFORM]

    html_body = sender._html_template
    replacements = {
        "{{major_drop_label}}": "",
        "{{old_price}}": old_fmt,
        "{{new_price}}": new_fmt,
        "{{drop_amount}}": drop_fmt,
        "{{drop_pct}}": str(drop_pct_int),
        "{{product_image}}": "",
        "{{product_name}}": safe_name,
        "{{platform_icon}}": platform_icon,
        "{{platform_label}}": platform_label,
        "{{product_url}}": PRODUCT_URL,
        "{{cta_text}}": CTA_TEXT.format(platform_label=platform_label),
        "{{prices_disclaimer}}": PRICES_DISCLAIMER,
        "{{footer_text}}": FOOTER_TEXT.format(product_name=safe_name),
        "{{footer_unsubscribe}}": FOOTER_UNSUBSCRIBE,
        "{{dashboard_url}}": "https://pricewatch.app/dashboard",
    }
    for placeholder, value in replacements.items():
        html_body = html_body.replace(placeholder, value)

    # No placeholders should remain
    assert "{{" not in html_body, "Unreplaced placeholders found in HTML"
    assert "}}" not in html_body, "Unreplaced placeholders found in HTML"
    print("✅ All placeholders replaced in HTML template")

    # Check key content is present
    assert old_fmt in html_body
    assert new_fmt in html_body
    assert str(drop_pct_int) in html_body
    assert platform_label in html_body
    print("✅ Key content present in rendered HTML")


def test_send_real_email():
    print("\n── Send real email ──────────────────────────────────────────────")
    print(f"  Sending to: {TEST_EMAIL}")

    sender = EmailSender()
    success = sender.send_price_drop(
        to_email=TEST_EMAIL,
        product_name=PRODUCT_NAME,
        product_image_url=PRODUCT_IMAGE_URL,
        product_url=PRODUCT_URL,
        old_price=OLD_PRICE,
        new_price=NEW_PRICE,
        platform=PLATFORM,
    )

    assert success is True, "SendGrid did not return 202 — check API key and sender verification"
    print("✅ Email sent successfully — check your inbox")

    # ── Also test with no image (placeholder path) ────────────────────────
    success_no_img = sender.send_price_drop(
        to_email=TEST_EMAIL,
        product_name="Sony WH-1000XM5 Headphones",
        product_image_url=None,
        product_url="https://www.amazon.in/dp/B09XS7JWHH",
        old_price=Decimal("29990.00"),
        new_price=Decimal("19990.00"),
        platform="amazon",
    )
    assert success_no_img is True
    print("✅ Email with no image sent successfully — check your inbox")

    # ── Test major drop (>= 50%) ──────────────────────────────────────────
    success_major = sender.send_price_drop(
        to_email=TEST_EMAIL,
        product_name="Test Product Major Drop",
        product_image_url=None,
        product_url="https://www.amazon.in/dp/B0CHX1W1XY",
        old_price=Decimal("10000.00"),
        new_price=Decimal("4000.00"),
        platform="flipkart",
    )
    assert success_major is True
    print("✅ Major drop email (60% off) sent successfully — check your inbox")


def test_email_sender():
    test_format_inr()
    test_calculate_drop()
    test_template_loading()
    test_placeholder_replacement()
    test_send_real_email()
    print("\n✅ All email sender tests passed")


test_email_sender()