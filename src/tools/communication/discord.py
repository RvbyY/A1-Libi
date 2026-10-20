from typing import Optional

from src.config import config
from src.rapideAPI.client import RapideAPI
from ..ITools import ToolContext, ToolResult, ToolsInterface


class Discord(ToolsInterface):
    """Outil d'envoi de messages privés Discord via l'API v10 et RapideAPI."""

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
        return "Send a Discord direct message from the A1-Libi Discord bot to a recipient."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "Discord user ID of the recipient (17-20 digits).",
                },
                "content": {
                    "type": "string",
                    "description": "Body of the message.",
                },
            },
            "required": ["recipient", "content"],
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
        recipient = str(payload.get("recipient", ""))
        content = str(payload.get("content", ""))

        if not self.token:
            return ToolResult(False, "The bot doesn't have a DISCORD_TOKEN set.")
        if not self.is_valid_user_id(recipient):
            return ToolResult(False, "Invalid Discord recipient user ID.")
        if not content:
            return ToolResult(False, "Message content cannot be empty.")

        try:
            self.send_discord_message(recipient, content)
        except ValueError as exc:
            return ToolResult(False, f"Discord rejected the message: {exc}")
        except Exception as exc:
            return ToolResult(False, f"Discord message could not be sent: {exc}")

        return ToolResult(
            True,
            f"Message sent from A1-Libi Bot to {recipient}.",
        )