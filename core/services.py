"""
Africa's Talking SMS integration (UR-24 / FR-10 / SDD 6.6).

This module wraps the Africa's Talking SMS API so the rest of the app can
send appointment reminders without knowing the API details. It is designed
to degrade gracefully:

- If `AT_API_KEY` / `AT_USERNAME` are not configured (e.g. local dev or a
  clinic that hasn't signed up yet), the service logs the message and
  returns a "simulated" success so the appointment workflow still works.
- If the API call fails, the error is captured and returned so the caller
  can record it in the SMSReminder audit log.

The Africa's Talking SDK is imported lazily so the app runs even when the
`africastalking` package is not installed (it is not in requirements.txt
by default; clinics that want real SMS add it and set the env vars).
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _get_at_client():
    """
    Lazily build the Africa's Talking SMS client.

    Returns None if the SDK is not installed or credentials are missing,
    so callers can fall back to simulated sending.
    """
    api_key = getattr(settings, "AT_API_KEY", "")
    username = getattr(settings, "AT_USERNAME", "sandbox")
    if not api_key:
        return None
    try:
        import africastalking

        africastalking.initialize(username, api_key)
        return africastalking.SMS
    except ImportError:
        logger.warning("africastalking package not installed; SMS will be simulated.")
        return None


def send_sms(phone_number, message):
    """
    Send an SMS via Africa's Talking.

    Returns a dict with keys:
      - success: bool
      - message_id: str (provider message ID, or "" if simulated)
      - error: str (error message, or "" on success)

    If credentials are not configured, the message is logged and treated
    as sent (simulated mode) so the clinic workflow is not blocked.
    """
    phone_number = phone_number.strip()
    if not phone_number:
        return {"success": False, "message_id": "", "error": "No phone number provided."}

    client = _get_at_client()
    if client is None:
        logger.info(
            "[SMS SIMULATED] To %s: %s",
            phone_number,
            message,
        )
        return {"success": True, "message_id": "SIMULATED", "error": ""}

    try:
        response = client.send(message, [phone_number])
        # Africa's Talking returns a dict like:
        # {"SMSMessageData": {"Recipients": [{"status": "Success", "messageId": "..."}]}}
        recipients = (
            response.get("SMSMessageData", {}).get("Recipients", [])
        )
        if recipients and recipients[0].get("status") == "Success":
            return {
                "success": True,
                "message_id": recipients[0].get("messageId", ""),
                "error": "",
            }
        return {
            "success": False,
            "message_id": "",
            "error": str(response),
        }
    except Exception as exc:  # noqa: BLE001 - capture any API error
        logger.error("Africa's Talking SMS error: %s", exc)
        return {"success": False, "message_id": "", "error": str(exc)}


def build_reminder_message(appointment):
    """
    Build the SMS reminder text for an appointment.

    Uses plain, simple language (NFR-7) suitable for patients with basic
    phones. Includes the clinic name, appointment date/time, and reason.
    """
    clinic_name = getattr(settings, "CLINIC_NAME", "Community Health Clinic")
    when = appointment.appointment_date.strftime("%A %d %b %Y at %H:%M")
    reason = appointment.reason or "your appointment"
    return (
        f"Dear {appointment.patient.full_name}, this is a reminder from "
        f"{clinic_name} about {reason} on {when}. "
        f"Please come to the clinic. Thank you."
    )