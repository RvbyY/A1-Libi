import re, smtplib
from email.mime.text import MIMEText
from email.header import Header

def is_valid_email(recipient_to: str, recipient_from: str) -> bool:
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", recipient_to) and re.match(r"[^@]+@[^@]+\.[^@]+", recipient_from))

def is_valid_phone(recipient_to: str, recipient_from: str) -> bool:
    return bool(re.match(r"^\+?\d{8,15}$", recipient_to) and re.match(r"^\+?\d{8,15}$", recipient_from))

def is_valid_slack_id(recipient_to: str, recipient_from: str) -> bool:
    return (recipient_to.startswith(("U", "#")) and recipient_from.startswith(("U", "#")))

def is_valid_push_token(recipient_to: str, recipient_from: str) -> bool:
    return (len(recipient_to) > 10 and len(recipient_from) > 10)

VALIDATORS = {
    "email": is_valid_email,
    "sms": is_valid_phone,
    "slack": is_valid_slack_id,
    "push": is_valid_push_token
}

def send_email(recipient_to: str, recipient_from: str, message: str) -> bool:
    """Envoie un email."""
    try:
        subject = ">> My Subject"
        msg = MIMEText(message)
        msg['Subject'] = Header(subject)
        mail_server = smtplib.SMTP('localhost')
        mail_server.ehlo()
        mail_server.starttls()
        mail_server.ehlo()
        mail_server.sendmail(recipient_from, recipient_to, msg.as_string())
        return True
    except Exception:
        return False

def send_sms(recipient_to: str, recipient_from: str, message: str) -> bool:
    try:
        return True
    except Exception:
        return False

def send_slack(recipient_to: str, recipient_from: str, message: str) -> bool:
    try:
        return True
    except Exception:
        return False

def send_push(recipient_to: str, recipient_from: str, message: str) -> bool:
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

def send_notification(recipient_to: str, recipient_from: str, message: str, channel: str) -> bool:
    """Envoie une notif (push, sms, slack...)."""
    validator = VALIDATORS.get(channel)
    sender = SENDERS.get(channel)

    if not validator or not sender:
        return False
    if not validator(recipient_to, recipient_from):
        return False
    return sender(recipient_to, recipient_from, message)
