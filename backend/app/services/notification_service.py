import logging

from app.config import settings

logger = logging.getLogger(__name__)


def send_whatsapp_message(to: str, message: str) -> bool:
    if not all((settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_whatsapp_from)):
        return False

    try:
        from twilio.rest import Client

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            from_=settings.twilio_whatsapp_from,
            to=to,
            body=message,
        )
        return True
    except Exception:
        logger.exception("Could not send a WhatsApp notification")
        return False
