import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config
from .base import ToolPlugin, ToolContext

logger = logging.getLogger(__name__)


class EmailTool(ToolPlugin):
    name = "send_email"
    description = (
        "Send an email via Gmail SMTP. "
        "Can send results, reports, code, or any text content to an email address. "
        "Supports plain text and HTML body."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address",
            },
            "subject": {
                "type": "string",
                "description": "Email subject line",
            },
            "body": {
                "type": "string",
                "description": "Email body content",
            },
            "html": {
                "type": "boolean",
                "description": "If true, body is treated as HTML (default: false)",
            },
        },
        "required": ["to", "subject", "body"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        if not config.GMAIL_ADDRESS or not config.GMAIL_APP_PASSWORD:
            return (
                "Error: Gmail is not configured. "
                "Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env"
            )

        to = tool_input["to"]
        subject = tool_input["subject"]
        body = tool_input["body"]
        html = tool_input.get("html", False)

        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = config.GMAIL_ADDRESS
            msg["To"] = to
            msg["Subject"] = subject

            content_type = "html" if html else "plain"
            msg.attach(MIMEText(body, content_type, "utf-8"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
                server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
                server.send_message(msg)

            logger.info("Email sent to %s: %s", to, subject)
            return f"Email sent successfully to {to}"

        except smtplib.SMTPAuthenticationError:
            return (
                "Error: Gmail authentication failed. "
                "Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD (use App Password, not regular password)"
            )
        except Exception as e:
            return f"Error sending email: {e}"
