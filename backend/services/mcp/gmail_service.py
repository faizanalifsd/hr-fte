"""
Gmail MCP Service - Email sending integration.

Supports TWO authentication methods (auto-detected from .env):

METHOD 1 — App Password + SMTP  (recommended, simpler)
  Required env vars:
    GMAIL_APP_PASSWORD   = 16-char app password from Google Account settings
    GMAIL_SENDER_EMAIL   = your Gmail address (e.g. you@gmail.com)

  How to get an App Password:
    1. Go to myaccount.google.com → Security
    2. Enable 2-Step Verification (required)
    3. Search "App passwords" → Select app: Mail → Generate
    4. Copy the 16-char password into .env

METHOD 2 — OAuth2 with Refresh Token  (original, complex)
  Required env vars:
    GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN

Auto-detection order: App Password → OAuth2 → Mock (dev fallback)
"""

import os
import uuid
import base64
import smtplib
import ssl
import logging
import time
from typing import Optional, Dict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

logger = logging.getLogger(__name__)


class GmailService:
    """
    Gmail service supporting App Password (SMTP) and OAuth2.
    App Password is tried first — it's simpler and more reliable.
    """

    def __init__(self):
        # Method 1 — App Password
        self.app_password   = os.getenv("GMAIL_APP_PASSWORD")
        self.sender_email   = os.getenv("GMAIL_SENDER_EMAIL")

        # Method 2 — OAuth2
        self.client_id      = os.getenv("GMAIL_CLIENT_ID")
        self.client_secret  = os.getenv("GMAIL_CLIENT_SECRET")
        self.refresh_token  = os.getenv("GMAIL_REFRESH_TOKEN")

        # Decide which method to use
        if self.app_password and self.sender_email:
            self.auth_method = "app_password"
            logger.info("Gmail: using App Password (SMTP) authentication")
        elif all([self.client_id, self.client_secret, self.refresh_token]):
            self.auth_method = "oauth2"
            logger.info("Gmail: using OAuth2 authentication")
        else:
            self.auth_method = "mock"
            logger.warning(
                "Gmail: no valid credentials found — running in mock mode.\n"
                "  To fix: add GMAIL_APP_PASSWORD + GMAIL_SENDER_EMAIL to .env\n"
                "  See backend/services/mcp/gmail_service.py for instructions."
            )

        self.max_retries = 3
        self.retry_delay = 2
        self._oauth_service = None   # cached OAuth2 service object

    # ------------------------------------------------------------------ #
    #  PUBLIC API                                                          #
    # ------------------------------------------------------------------ #

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cv_file_path: Optional[str] = None,
        cv_file_name: Optional[str] = None,
        to_name: Optional[str] = None,
        cc_emails: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Send job application email.

        Returns:
            {
                "message_id": str,
                "thread_id":  str,
                "status":     "sent" | "failed",
                "error":      str | None
            }
        """
        logger.info(f"Sending email → {to_email} | subject: '{subject}' | method: {self.auth_method}")

        for attempt in range(self.max_retries):
            try:
                if self.auth_method == "app_password":
                    return self._send_via_smtp(to_email, subject, body, cv_file_path, cv_file_name, to_name, cc_emails)
                elif self.auth_method == "oauth2":
                    return self._send_via_oauth(to_email, subject, body, cv_file_path, cv_file_name, to_name, cc_emails)
                else:
                    return self._send_mock(to_email, subject)

            except Exception as e:
                logger.warning(f"Email send attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                else:
                    logger.error(f"Email failed after {self.max_retries} attempts")
                    return {"message_id": None, "thread_id": None, "status": "failed", "error": str(e)}

        return {"message_id": None, "thread_id": None, "status": "failed", "error": "Max retries exceeded"}

    def validate_credentials(self) -> bool:
        """Test the configured auth method. Returns True if working."""
        if self.auth_method == "app_password":
            return self._validate_smtp()
        elif self.auth_method == "oauth2":
            return self._validate_oauth()
        else:
            logger.warning("Gmail running in mock mode — no real credentials configured")
            return False

    # ------------------------------------------------------------------ #
    #  METHOD 1 — APP PASSWORD (SMTP)                                     #
    # ------------------------------------------------------------------ #

    def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        body: str,
        cv_file_path: Optional[str],
        cv_file_name: Optional[str],
        to_name: Optional[str],
        cc_emails: Optional[str],
    ) -> Dict[str, str]:
        """Send using Gmail SMTP with App Password (port 465 SSL)."""
        msg = MIMEMultipart()
        msg["From"]    = self.sender_email
        msg["To"]      = f"{to_name} <{to_email}>" if to_name else to_email
        msg["Subject"] = subject

        # Unique message ID for traceability
        msg_id = f"<{uuid.uuid4().hex}@gmail.com>"
        msg["Message-ID"] = msg_id

        if cc_emails:
            msg["Cc"] = cc_emails

        msg.attach(MIMEText(body, "plain"))

        # Attach CV if file exists
        if cv_file_path and os.path.exists(cv_file_path):
            try:
                with open(cv_file_path, "rb") as f:
                    attachment = MIMEApplication(f.read(), _subtype="pdf")
                attachment.add_header(
                    "Content-Disposition", "attachment",
                    filename=cv_file_name or "Resume.pdf"
                )
                msg.attach(attachment)
                logger.info(f"CV attached: {cv_file_name or 'Resume.pdf'}")
            except Exception as e:
                logger.warning(f"CV attach failed (continuing without): {e}")

        # Build recipient list
        recipients = [to_email]
        if cc_emails:
            recipients += [e.strip() for e in cc_emails.split(",")]

        # Send via SSL on port 465
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(self.sender_email, self.app_password)
            server.sendmail(self.sender_email, recipients, msg.as_string())

        logger.info(f"Email sent via SMTP. Message-ID: {msg_id}")
        return {
            "message_id": msg_id,
            "thread_id":  msg_id,     # SMTP has no thread concept
            "status":     "sent",
            "error":      None,
        }

    def _validate_smtp(self) -> bool:
        """Test SMTP login without sending."""
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                server.login(self.sender_email, self.app_password)
            logger.info(f"Gmail SMTP validated for: {self.sender_email}")
            return True
        except Exception as e:
            logger.error(f"Gmail SMTP validation failed: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  METHOD 2 — OAUTH2                                                  #
    # ------------------------------------------------------------------ #

    def _get_oauth_service(self):
        """Build or return cached OAuth2 Gmail API service."""
        if self._oauth_service:
            return self._oauth_service
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        )
        self._oauth_service = build("gmail", "v1", credentials=creds)
        return self._oauth_service

    def _send_via_oauth(
        self,
        to_email: str,
        subject: str,
        body: str,
        cv_file_path: Optional[str],
        cv_file_name: Optional[str],
        to_name: Optional[str],
        cc_emails: Optional[str],
    ) -> Dict[str, str]:
        """Send using Gmail REST API with OAuth2."""
        msg = MIMEMultipart()
        msg["To"]      = f"{to_name} <{to_email}>" if to_name else to_email
        msg["Subject"] = subject
        if cc_emails:
            msg["Cc"] = cc_emails
        msg.attach(MIMEText(body, "plain"))

        if cv_file_path and os.path.exists(cv_file_path):
            try:
                with open(cv_file_path, "rb") as f:
                    attachment = MIMEApplication(f.read(), _subtype="pdf")
                attachment.add_header(
                    "Content-Disposition", "attachment",
                    filename=cv_file_name or "Resume.pdf"
                )
                msg.attach(attachment)
            except Exception as e:
                logger.warning(f"CV attach failed: {e}")

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        service = self._get_oauth_service()
        result  = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        logger.info(f"Email sent via OAuth2. Message ID: {result['id']}")
        return {
            "message_id": result.get("id"),
            "thread_id":  result.get("threadId"),
            "status":     "sent",
            "error":      None,
        }

    def _validate_oauth(self) -> bool:
        """Test OAuth2 credentials by fetching Gmail profile."""
        try:
            service = self._get_oauth_service()
            profile = service.users().getProfile(userId="me").execute()
            logger.info(f"Gmail OAuth2 validated for: {profile.get('emailAddress')}")
            return True
        except Exception as e:
            logger.error(f"Gmail OAuth2 validation failed: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  MOCK FALLBACK                                                       #
    # ------------------------------------------------------------------ #

    def _send_mock(self, to_email: str, subject: str) -> Dict[str, str]:
        """Simulate send for dev/testing — no real email sent."""
        mock_id = f"mock_{uuid.uuid4().hex[:16]}"
        logger.warning(f"[MOCK] Email NOT sent (no credentials). Would send to {to_email}: '{subject}'")
        return {
            "message_id": mock_id,
            "thread_id":  f"thread_{mock_id}",
            "status":     "sent",   # returns "sent" so pipeline continues
            "error":      None,
        }
