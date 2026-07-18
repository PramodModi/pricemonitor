from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.core.config import settings

TEST_TO_EMAIL = "pramodkmodi@gmail.com"  # replace with your email

message = Mail(
    from_email=settings.email_from_address,
    to_emails=TEST_TO_EMAIL,
    subject="Pricemonitor — SendGrid connection test",
    plain_text_content="If you received this, SendGrid is configured correctly.",
)

try:
    sg = SendGridAPIClient(settings.sendgrid_api_key)
    response = sg.send(message)
    print(f"✅ Email sent — status={response.status_code}")
    print("Check your inbox")
except Exception as e:
    print(f"❌ Failed — {e}")