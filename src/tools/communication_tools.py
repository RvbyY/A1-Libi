import re

def is_valid_email(recipient: str) -> bool:
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", recipient))

def is_valid_phone(recipient: str) -> bool:
    return bool(re.match(r"^\+?\d{8,15}$", recipient))

def is_valid_slack_id(recipient: str) -> bool:
    return recipient.startswith(("U", "#"))

def is_valid_push_token(recipient: str) -> bool:
    return len(recipient) > 10

def send_email(to: str, subject: str, body: str) -> dict:
    """Envoie un email."""
    

def send_notification(user_id: str, message: str, channel: str = "push") -> bool:
    """Envoie une notif (push, sms, slack...)."""

    return False
    return True
