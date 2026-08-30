import os
from dotenv import load_dotenv
import resend

load_dotenv()
resend.api_key = os.environ.get("RESEND_API_KEY")

if not resend.api_key:
    print("Error: RESEND_API_KEY is not set in .env")
    exit(1)

resend_from = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")

params = {
    "from": f"Unified IT <{resend_from}>",
    "to": ["promitwho@gmail.com"],
    "subject": "Test Verification Code",
    "text": "Hello, this is a test verification code from your AI assistant!"
}

try:
    print(f"Sending test email from {resend_from} to promitwho@gmail.com...")
    email = resend.Emails.send(params)
    print("Email sent successfully! Response:", email)
except Exception as e:
    print("Failed to send email:", e)
