import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage

from fastapi import HTTPException, status

from app.core.config import Settings


class EmailSender(ABC):
    @abstractmethod
    def send_validation_code(self, recipient_email: str, full_name: str, code: str, expires_in: int) -> None:
        raise NotImplementedError


class SMTPEmailSender(EmailSender):
    """Strategy implementation for sending emails over SMTP."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def send_validation_code(self, recipient_email: str, full_name: str, code: str, expires_in: int) -> None:
        if not self.settings.smtp_host or not self.settings.smtp_from_email:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="SMTP is not configured. Set SMTP_* values in .env",
            )

        message = EmailMessage()
        message["Subject"] = "Your Password Reset Code"
        message["From"] = f'{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>'
        message["To"] = recipient_email
        message.set_content(
            "\n".join(
                [
                    f"Hi {full_name},",
                    "",
                    "Use this validation code to reset your password:",
                    f"{code}",
                    "",
                    f"This code expires in {expires_in} minutes.",
                    "If you did not request this, ignore this email.",
                ]
            )
        )

        try:
            if self.settings.smtp_use_ssl:
                with smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port) as server:
                    self._authenticate(server)
                    server.send_message(message)
                return

            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
                if self.settings.smtp_use_tls:
                    server.starttls()
                self._authenticate(server)
                server.send_message(message)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send reset code email.",
            ) from exc

    def _authenticate(self, server: smtplib.SMTP) -> None:
        if self.settings.smtp_username:
            server.login(self.settings.smtp_username, self.settings.smtp_password)
