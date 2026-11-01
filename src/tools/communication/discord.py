from typing import Optional

from src.config import config
from src.rapideAPI.client import RapideAPI
from ..ITools import ToolContext, ToolResult, ToolsInterface


class Discord(ToolsInterface):
    """Outil d'envoi de messages privés Discord via l'API v10 et RapideAPI."""

    requires_confirmation = True

    DISCORD_API_BASE = "https://discord.com/api/v10"

    def __init__(self, token: Optional[str] = None, api_client: Optional[RapideAPI] = None):
        self._token = token
        self._api_client = api_client

    @property
    def token(self) -> str:
        return self._token if self._token is not None else config.DISCORD_TOKEN

    def _get_client(self) -> RapideAPI:
        if self._api_client is not None:
            return self._api_client
        return RapideAPI(
            base_url=self.DISCORD_API_BASE,
            default_headers={
                "Authorization": f"Bot {self.token}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )

    @property
    def name(self) -> str:
        return "discord"

    @property
    def description(self) -> str:
        return "Send the same Discord direct message from the A1-Libi Discord bot to one or more recipients."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "Discord user ID of the recipient (17-20 digits).",
                },
                "recipients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Discord user IDs when sending the same message to multiple recipients.",
                },
                "content": {
                    "type": "string",
                    "description": "Body of the message.",
                },
            },
            "required": ["content"],
        }

    @staticmethod
    def is_valid_user_id(recipient: str) -> bool:
        return isinstance(recipient, str) and recipient.isnumeric() and 17 <= len(recipient) <= 20

    def send_discord_message(self, recipient: str, content: str) -> dict:
        """Crée un salon DM Discord avec le destinataire et envoie le message."""
        client = self._get_client()
        channel = client.post(
            "users/@me/channels",
            json={"recipient_id": recipient},
        )
        channel_id = channel.get("id") if isinstance(channel, dict) else None
        if not channel_id:
            raise ValueError("Discord did not return a direct message channel.")

        response = client.post(
            f"channels/{channel_id}/messages",
            json={"content": content},
        )
        return response if isinstance(response, dict) else {"raw": response}

    def execute(self, context: ToolContext, payload: dict) -> ToolResult:
        del context
        raw_recipients = payload.get("recipients")
        if raw_recipients is None:
            raw_recipients = [payload.get("recipient", "")]
        if not isinstance(raw_recipients, list):
            return ToolResult(False, "Discord recipients must be a list.")
        recipients = [str(recipient) for recipient in raw_recipients]
        content = str(payload.get("content", ""))

        if not self.token:
            return ToolResult(False, "The bot doesn't have a DISCORD_TOKEN set.")
        if not recipients or any(not self.is_valid_user_id(recipient) for recipient in recipients):
            return ToolResult(False, "Invalid Discord recipient user ID.")
        if not content:
            return ToolResult(False, "Message content cannot be empty.")

        sent = []
        failures = []
        for recipient in dict.fromkeys(recipients):
            try:
                self.send_discord_message(recipient, content)
                sent.append(recipient)
            except ValueError as exc:
                failures.append(f"{recipient}: {exc}")
            except Exception as exc:
                failures.append(f"{recipient}: {exc}")

        if failures:
            detail = "; ".join(failures)
            return ToolResult(
                False,
                f"Discord sent {len(sent)}/{len(dict.fromkeys(recipients))} message(s); failures: {detail}",
                data={"sent": sent, "failed": failures},
            )

        return ToolResult(
            True,
            f"Message sent from A1-Libi Bot to {', '.join(sent)}.",
            data={"sent": sent},
        )