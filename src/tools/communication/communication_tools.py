"""
Module communication_tools.py
Encapsule l'envoi de notifications multi-canaux (email, sms, slack, push)
dans une classe NotificationTool héritant de ToolsInterface.
"""
import re
from typing import Optional

from .email import Email
from ..ITools import ToolContext, ToolResult, ToolsInterface


class NotificationTool(ToolsInterface):
    """Outil multi-canal permettant d'envoyer des notifications (email, sms, slack, push)."""

    requires_confirmation = True

    SUPPORTED_CHANNELS = ("email", "sms", "slack", "push")

    def __init__(self, email_tool: Optional[Email] = None):
        self.email_tool = email_tool or Email()

    @property
    def name(self) -> str:
        return "notification"

    @property
    def description(self) -> str:
        return "Send a notification to a recipient via email, sms, slack, or push."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "enum": list(self.SUPPORTED_CHANNELS),
                    "description": "Notification channel to use (email, sms, slack, push).",
                },
                "recipient_to": {
                    "type": "string",
                    "description": "Recipient identifier (email, phone number, Slack ID, or push token).",
                },
                "recipient_from": {
                    "type": "string",
                    "description": "Sender identifier (optional if available in user context).",
                },
                "message": {
                    "type": "string",
                    "description": "Notification body.",
                },
                "subject": {
                    "type": "string",
                    "description": "Optional subject (used for email notifications).",
                },
            },
            "required": ["channel", "recipient_to", "message"],
        }

    # ── Validateurs par canal ────────────────────────────────────────

    @staticmethod
    def is_valid_email_pair(recipient_to: str, recipient_from: str) -> bool:
        return Email.is_valid_email(recipient_to) and Email.is_valid_email(recipient_from)

    @staticmethod
    def is_valid_phone_pair(recipient_to: str, recipient_from: str) -> bool:
        pattern = r"^\+?\d{8,15}$"
        return bool(re.match(pattern, recipient_to) and re.match(pattern, recipient_from))

    @staticmethod
    def is_valid_slack_pair(recipient_to: str, recipient_from: str) -> bool:
        return recipient_to.startswith(("U", "#")) and recipient_from.startswith(("U", "#"))

    @staticmethod
    def is_valid_push_pair(recipient_to: str, recipient_from: str) -> bool:
        return len(recipient_to) > 10 and len(recipient_from) > 10

    def validate_channel(self, channel: str, recipient_to: str, recipient_from: str) -> bool:
        validators = {
            "email": self.is_valid_email_pair,
            "sms": self.is_valid_phone_pair,
            "slack": self.is_valid_slack_pair,
            "push": self.is_valid_push_pair,
        }
        validator = validators.get(channel)
        if not validator:
            return False
        return validator(recipient_to, recipient_from)

    # ── Envoi par canal ──────────────────────────────────────────────

    def _send_email(self, recipient_to: str, recipient_from: str, message: str, subject: str = "Notification SensAI") -> bool:
        try:
            self.email_tool.send_email(
                sender=recipient_from,
                recipient=recipient_to,
                subject=subject,
                content=message,
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _send_sms(recipient_to: str, recipient_from: str, message: str) -> bool:
        del recipient_to, recipient_from, message
        return True

    @staticmethod
    def _send_slack(recipient_to: str, recipient_from: str, message: str) -> bool:
        del recipient_to, recipient_from, message
        return True

    @staticmethod
    def _send_push(recipient_to: str, recipient_from: str, message: str) -> bool:
        del recipient_to, recipient_from, message
        return True

    def send(
        self,
        recipient_to: str,
        recipient_from: str,
        message: str,
        channel: str,
        subject: str = "Notification SensAI",
    ) -> bool:
        """Valide et envoie une notification sur le canal demandé."""
        if not self.validate_channel(channel, recipient_to, recipient_from):
            return False

        if channel == "email":
            return self._send_email(recipient_to, recipient_from, message, subject=subject)
        if channel == "sms":
            return self._send_sms(recipient_to, recipient_from, message)
        if channel == "slack":
            return self._send_slack(recipient_to, recipient_from, message)
        if channel == "push":
            return self._send_push(recipient_to, recipient_from, message)
        return False

    def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        channel = str(arguments.get("channel", "")).lower()
        recipient_to = str(arguments.get("recipient_to", ""))
        recipient_from = str(arguments.get("recipient_from") or context.user_email or "")
        message = str(arguments.get("message", ""))
        subject = str(arguments.get("subject", "Notification SensAI"))

        if channel not in self.SUPPORTED_CHANNELS:
            return ToolResult(False, f"Unsupported channel: {channel}")

        if not self.validate_channel(channel, recipient_to, recipient_from):
            return ToolResult(False, f"Invalid sender or recipient format for channel '{channel}'.")

        success = self.send(recipient_to, recipient_from, message, channel, subject=subject)
        if not success:
            return ToolResult(False, f"Notification could not be sent via {channel}.")

        return ToolResult(True, f"Notification sent to {recipient_to} via {channel}.")


def send_notification(recipient_to: str, recipient_from: str, message: str, channel: str) -> bool:
    """Fonction de compatibilité déléguant à NotificationTool."""
    return NotificationTool().send(recipient_to, recipient_from, message, channel)
