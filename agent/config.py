from os import getenv

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = getenv("DATABASE_URL", "").strip().strip('"').strip("'")
GEMINI_API_KEY = (getenv("GEMINI_API_KEY") or "").strip()
GEMINI_MODEL = (getenv("GEMINI_MODEL") or "gemini-3.1-flash-lite").strip()
GEMINI_LIVE_MODEL = (getenv("GEMINI_LIVE_MODEL") or "gemini-3.1-flash-live-preview").strip()

SMTP_SERVER = getenv("SMTP_SERVER", "")
SMTP_PORT = int(getenv("SMTP_PORT", "587"))
SMTP_USERNAME = getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = getenv("SMTP_PASSWORD", "")
RESEND_API_KEY = getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")

if not GEMINI_MODEL:
    raise RuntimeError("GEMINI_MODEL must be a non-empty string.")
    