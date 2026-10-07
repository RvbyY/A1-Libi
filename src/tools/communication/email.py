import re
import smtplib
from email.header import Header
from email.mime.text import MIMEText

from ..ITools import ToolContext, ToolResult, ToolsInterface


class Email(ToolsInterface):
    @property
    def name(self) -> str:
        return "email"

    @property
    def description(self) -> str:
        return "Send an email from the authenticated user to a recipient."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "Email address of the recipient.",
                },
                "subject": {
                    "type": "string",
                    "description": "Subject of the email.",
                },
                "content": {
                    "type": "string",
                    "description": "Body of the email.",
                },
            },
            "required": ["recipient", "subject", "content"],
        }

    @staticmethod
    def is_valid_email(address: str) -> bool:
        return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address))

    def send_email(
        self,
        sender: str,
        recipient: str,
        subject: str,
        content: str,
    ) -> None:
        msg = MIMEText(content, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = sender
        msg["To"] = recipient

        with smtplib.SMTP("localhost") as mail_server:
            mail_server.ehlo()
            mail_server.starttls()
            mail_server.ehlo()
            mail_server.sendmail(sender, [recipient], msg.as_string())

    def execute(self, context: ToolContext, payload: dict) -> ToolResult:
        sender = context.user_email
        recipient = payload["recipient"]
        subject = payload["subject"]
        content = payload["content"]

        if not sender:
            return ToolResult(False, "The user has no sender email address.")
        if not self.is_valid_email(sender):
            return ToolResult(False, "Invalid sender email format.")
        if not self.is_valid_email(recipient):
            return ToolResult(False, "Invalid recipient email format.")

        try:
            self.send_email(sender, recipient, subject, content)
        except (OSError, smtplib.SMTPException) as exc:
            return ToolResult(False, f"Email could not be sent: {exc}")

        return ToolResult(
            True,
            f"Email sent from {sender} to {recipient}.",
        )