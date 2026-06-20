"""Email sending abstraction.

In development we log emails to the console. In production, swap in an SMTP or
provider-backed sender (ideally dispatched via a Celery task) behind the same
``EmailSender`` interface — no call sites change.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("teamsync.email")


@dataclass
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailSender:
    """Interface for sending transactional email."""

    async def send(self, message: EmailMessage) -> None:  # pragma: no cover
        raise NotImplementedError


class ConsoleEmailSender(EmailSender):
    """Logs emails instead of sending them — useful for local development."""

    async def send(self, message: EmailMessage) -> None:
        logger.info(
            "[email] to=%s subject=%s\n%s",
            message.to,
            message.subject,
            message.body,
        )


_default_sender = ConsoleEmailSender()


def get_email_sender() -> EmailSender:
    """FastAPI dependency — override in tests/production."""
    return _default_sender


def build_password_reset_email(to: str, reset_link: str) -> EmailMessage:
    body = (
        "You requested a password reset for your TeamSync account.\n\n"
        f"Reset your password using this link (valid for a limited time):\n{reset_link}\n\n"
        "If you didn't request this, you can safely ignore this email."
    )
    return EmailMessage(to=to, subject="Reset your TeamSync password", body=body)
