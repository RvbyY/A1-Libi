from typing import Optional
from bs4 import BeautifulSoup

from src.config import config
from src.rapideAPI.client import RapideAPI
from ..ITools import ToolContext, ToolResult, ToolsInterface


class Telegram(ToolsInterface):
    """Outil d'envoi de messages Telegram via RapideAPI et Config."""

    TELEGRAM_API_BASE = "https://api.telegram.org"

    def __init__(self, token: Optional[str] = None, api_client: Optional[RapideAPI] = None):
        self._token = token
        self._api_client = api_client

    @property
    def token(self) -> str:
        return self._token if self._token is not None else config.TELEGRAM_TOKEN

    def _get_client(self) -> RapideAPI:
        if self._api_client is not None:
            return self._api_client
        return RapideAPI(base_url=self.TELEGRAM_API_BASE, timeout=10)

    @property
    def name(self) -> str:
        return "telegram"

    @property
    def description(self) -> str:
        return "Send a Telegram message from A1-Libi bot to a recipient."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "Account ID or username of the recipient.",
                },
                "content": {
                    "type": "string",
                    "description": "Content of the message.",
                },
            },
            "required": ["recipient", "content"],
        }

    def is_valid_recipient(self, recipient: str) -> bool:
        if not recipient:
            return False
        url = f"https://t.me/{recipient}"
        try:
            html_text = self._get_client().get(url)
        except Exception:
            return False

        if not isinstance(html_text, str):
            return False
        soup = BeautifulSoup(html_text, "html.parser")
        return soup.find("meta", attrs={"property": "og:title"}) is not None

    def send_telegram_message(self, recipient: str, content: str) -> dict:
        response = self._get_client().post(
            f"bot{self.token}/sendMessage",
            json={
                "chat_id": recipient,
                "text": content,
            },
        )
        if not isinstance(response, dict) or not response.get("ok", False):
            description = (
                response.get("description", "Unknown Telegram API error")
                if isinstance(response, dict)
                else "Invalid Telegram response"
            )
            raise ValueError(description)
        return response

    def execute(self, context: ToolContext, payload: dict) -> ToolResult:
        del context
        recipient = str(payload.get("recipient", ""))
        content = str(payload.get("content", ""))

        if not self.token:
            return ToolResult(False, "The bot doesn't have a TOKEN set")
        if not self.is_valid_recipient(recipient):
            return ToolResult(False, "Invalid recipient phone format.")

        try:
            self.send_telegram_message(recipient, content)
        except ValueError as exc:
            return ToolResult(False, f"Telegram rejected the message: {exc}")
        except Exception as exc:
            return ToolResult(False, f"Telegram request failed: {exc}")

        return ToolResult(
            True,
            f"Message sent from A1-Libi Bot to {recipient}.",
        )