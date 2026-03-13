"""sms_gateway.py - simple Twilio wrapper (best-effort, optional).

If Twilio is not configured, send_sms() returns False but the app continues to work.
"""

import os

try:
    from twilio.rest import Client as TwilioClient
except ImportError:  # Twilio not installed; keep optional
    TwilioClient = None


def send_sms(phone: str, body: str) -> bool:
    """Send SMS using Twilio. Returns True on success, False otherwise."""
    if not TwilioClient:
        # Library not installed; skip sending
        print("Twilio client not installed.")
        return False

    sid = os.getenv("TWILIO_SID")
    token = os.getenv("TWILIO_TOKEN")
    from_num = os.getenv("TWILIO_FROM")

    if not all([sid, token, from_num]):
        print("Twilio env vars not set.")
        return False

    try:
        client = TwilioClient(sid, token)
        msg = client.messages.create(to=phone, from_=from_num, body=body)
        return msg.sid is not None
    except Exception as e:  # pragma: no cover - network/credentials issues
        print("SMS error:", e)
        return False

