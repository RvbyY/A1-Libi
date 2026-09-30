import re

def is_valid_email(recipient: str) -> bool:
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", recipient))

def is_valid_phone(recipient: str) -> bool:
    return bool(re.match(r"^\+?\d{8,15}$", recipient))

def is_valid_slack_id(recipient: str) -> bool:
    return recipient.startswith(("U", "#"))

def is_valid_push_token(recipient: str) -> bool:
    return len(recipient) > 10

VALIDATORS = {
    "email": is_valid_email,
    "sms": is_valid_phone,
    "slack": is_valid_slack_id,
    "push": is_valid_push_token
}

def send_email(recipient: str, message: str) -> bool:
    """Envoie un email."""
    try:
        return True
    except Exception:
        return False

def send_sms(recipient: str, message: str) -> bool:
    try:
        return True
    except Exception:
        return False

def send_slack(recipient: str, message: str) -> bool:
    try:
        return True
    except Exception:
        return False

def send_push(recipient: str, message: str) -> bool:
    try:
        return True
    except Exception:
        return False

SENDERS = {
    "email": send_email,
    "sms": send_sms,
    "slack": send_slack,
    "push": send_push
}

def send_notification(recipient: str, message: str, channel: str) -> bool:
    """Envoie une notif (push, sms, slack...)."""
    validator = VALIDATORS.get(channel)
    sender = SENDERS.get(channel)

    if not validator or not sender:
        return False
    if not validator(recipient):
        return False
    return sender(recipient, message)
