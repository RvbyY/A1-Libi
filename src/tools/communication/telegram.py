import os
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv

from ..ITools import ToolContext, ToolResult, ToolsInterface

load_dotenv()
TOKEN = os.getenv('TOKEN')

class Telegram(ToolsInterface):
    @property
    def name(self) -> str:
        return "telegram"

    @property
    def description(self) -> str:
        return "Send a telegram from A1-Libi bot to recipient."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "Account ID of the recipient.",
                },
                "content": {
                    "type": "string",
                    "description": "Content of the message"
                },
            },
            "required": ["recipient", "content"],
        }

    @staticmethod
    def get_html(url, params=None):
        r = requests.get(url, params=params)
        return r

    @staticmethod
    def is_valid_phone(recipient: str) -> bool:
        url = f'https://t.me/{recipient}'
        try:
            response = Telegram.get_html(url)
            response.raise_for_status()
        except requests.RequestException:
            return False

        soup = BeautifulSoup(response.text, "html.parser")
        return soup.find("meta", attrs={"property": "og:title"}) is not None

    def send_telegram_message(self, recipient: str, content: str) -> dict:
        response = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": recipient,
                "text": content,
            },
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
        if not result.get("ok", False):
            description = result.get("description", "Unknown Telegram API error")
            raise ValueError(description)
        return result

    def execute(self, context: ToolContext, payload: dict) -> ToolResult:
        sender = TOKEN
        recipient = payload["recipient"]
        content = payload["content"]

        if not sender:
            return ToolResult(False, "The bot doesn't have a TOKEN set")
        if not self.is_valid_phone(recipient):
            return ToolResult(False, "Invalid recipient phone format.")

        try:
            self.send_telegram_message(recipient, content)
        except requests.RequestException as exc:
            return ToolResult(False, f"Telegram request failed: {exc}")
        except ValueError as exc:
            return ToolResult(False, f"Telegram rejected the message: {exc}")

        return ToolResult(
            True,
            f"Message sent from A1-Libi Bot to {recipient}.",
        )