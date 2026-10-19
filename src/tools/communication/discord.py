import os
import requests
from dotenv import load_dotenv
from ..ITools import ToolContext, ToolResult, ToolsInterface

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
ID = os.getenv('DISCORD_ID')

class Discord(ToolsInterface):
    @property
    def name(self) -> str:
        return "discord"


    @property
    def description(self) -> str:
        return "send a discord message from the A1-Libi discord bot to a recipient."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "Discord message of the recipient.",
                },
                "content": {
                    "type": "string",
                    "description": "Body of the message",
                },
            },
            "required": ["recipient", "content"],
        }

    @staticmethod
    def is_valid_user_id(recipient: str) -> bool:
        return recipient.isnumeric() and 17 <= len(recipient) <= 20

    def send_discord_message(self, recipient: str, content: str) -> dict:
        """Send a private message to a Discord user."""
        headers = {
            "Authorization": f"Bot {TOKEN}",
            "Content-Type": "application/json",
        }

        # Discord requires a DM channel to be created before sending its message.
        channel_response = requests.post(
            "https://discord.com/api/v10/users/@me/channels",
            headers=headers,
            json={"recipient_id": recipient},
            timeout=10,
        )
        channel_response.raise_for_status()
        channel = channel_response.json()
        channel_id = channel.get("id")
        if not channel_id:
            raise ValueError("Discord did not return a direct message channel.")

        message_response = requests.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers=headers,
            json={"content": content},
            timeout=10,
        )
        message_response.raise_for_status()
        return message_response.json()

    def execute(self, context: ToolContext, payload: dict) -> ToolResult:
        del context
        recipient = payload["recipient"]
        content = payload["content"]

        if not TOKEN:
            return ToolResult(False, "The bot doesn't have a DISCORD_TOKEN set.")
        if not self.is_valid_user_id(recipient):
            return ToolResult(False, "Invalid Discord recipient user ID.")

        try:
            self.send_discord_message(recipient, content)
        except requests.RequestException as exc:
            return ToolResult(False, f"Discord message could not be sent: {exc}")
        except ValueError as exc:
            return ToolResult(False, f"Discord rejected the message: {exc}")

        return ToolResult(
            True,
            f"Message sent from A1-Libi Bot to {recipient}.",
        )