import base64
import json
import os
import secrets
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import truststore

from zoe_assistant.config import get_settings
from zoe_assistant.db import load_secret, save_secret

truststore.inject_into_ssl()


class GoogleAuthError(RuntimeError):
    pass


class GoogleService:
    """Google OAuth, Calendar, and Gmail integration."""

    token_key = "google_credentials"
    token_path = Path(".local/google_credentials.enc")
    state_path = Path(".local/google_oauth_state.json")

    def required_scopes(self) -> list[str]:
        return [
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.compose",
        ]

    def build_authorization_url(self) -> str:
        state = secrets.token_urlsafe(32)
        flow = self._build_flow(state=state)
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        self._save_state(state=state, code_verifier=flow.code_verifier)
        return authorization_url

    def handle_oauth_callback(self, authorization_response: str) -> None:
        oauth_state = self._load_state()
        flow = self._build_flow(
            state=oauth_state["state"],
            code_verifier=oauth_state["code_verifier"],
        )
        flow.fetch_token(authorization_response=authorization_response)

        if flow.credentials is None:
            raise GoogleAuthError("Google did not return OAuth credentials.")

        self._save_credentials(flow.credentials)
        self._delete_state()

    def is_connected(self) -> bool:
        try:
            credentials = self._load_credentials()
        except GoogleAuthError:
            return False
        return bool(credentials and (credentials.valid or credentials.refresh_token))

    def list_calendar_events(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        credentials = self._get_valid_credentials()
        service = build("calendar", "v3", credentials=credentials)
        response = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=50,
            )
            .execute()
        )
        return [
            {
                "id": item.get("id"),
                "summary": item.get("summary", "(No title)"),
                "start": item.get("start", {}),
                "end": item.get("end", {}),
                "location": item.get("location"),
                "htmlLink": item.get("htmlLink"),
            }
            for item in response.get("items", [])
        ]

    def list_calendar_events_for_days(self, days: int) -> list[dict[str, Any]]:
        settings = get_settings()
        now = datetime.now(settings.tzinfo)
        return self.list_calendar_events(now, now + timedelta(days=days))

    def search_gmail(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        credentials = self._get_valid_credentials()
        service = build("gmail", "v1", credentials=credentials)
        result = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )

        messages = []
        for message in result.get("messages", []):
            detail = (
                service.users()
                .messages()
                .get(userId="me", id=message["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"])
                .execute()
            )
            headers = {
                header["name"].lower(): _decode_mime_header(header["value"])
                for header in detail.get("payload", {}).get("headers", [])
            }
            messages.append(
                {
                    "id": detail.get("id"),
                    "threadId": detail.get("threadId"),
                    "from": headers.get("from"),
                    "subject": headers.get("subject"),
                    "date": headers.get("date"),
                    "snippet": detail.get("snippet"),
                }
            )
        return messages

    def create_gmail_draft(self, to: str, subject: str, body: str) -> dict[str, Any]:
        credentials = self._get_valid_credentials()
        service = build("gmail", "v1", credentials=credentials)

        message = EmailMessage()
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        return (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": encoded}})
            .execute()
        )

    def _build_flow(self, state: str, code_verifier: str | None = None) -> Flow:
        settings = get_settings()
        if not settings.google_client_id or not settings.google_client_secret:
            raise GoogleAuthError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env.")
        if settings.app_env == "local" and settings.google_redirect_uri.startswith("http://localhost"):
            os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.google_redirect_uri],
                }
            },
            scopes=self.required_scopes(),
            state=state,
            code_verifier=code_verifier,
        )
        flow.redirect_uri = settings.google_redirect_uri
        return flow

    def _get_valid_credentials(self) -> Credentials:
        credentials = self._load_credentials()
        if credentials.valid:
            return credentials
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._save_credentials(credentials)
            return credentials
        raise GoogleAuthError("Google is not connected. Open /google/oauth/start first.")

    def _save_credentials(self, credentials: Credentials) -> None:
        payload = json.dumps(
            {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
            }
        ).encode("utf-8")
        encrypted = self._fernet().encrypt(payload)
        if self._use_database_token_store():
            save_secret(self.token_key, encrypted)
        else:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_bytes(encrypted)

    def _load_credentials(self) -> Credentials:
        encrypted = self._load_encrypted_credentials()
        if encrypted is None:
            raise GoogleAuthError("Google OAuth token is missing.")
        try:
            payload = self._fernet().decrypt(encrypted)
        except InvalidToken as exc:
            raise GoogleAuthError("Google OAuth token could not be decrypted. Check TOKEN_ENCRYPTION_KEY.") from exc
        data = json.loads(payload.decode("utf-8"))
        return Credentials.from_authorized_user_info(data, scopes=self.required_scopes())

    def _load_encrypted_credentials(self) -> bytes | None:
        if self._use_database_token_store():
            return load_secret(self.token_key)
        if not self.token_path.exists():
            return None
        return self.token_path.read_bytes()

    def _save_state(self, state: str, code_verifier: str | None) -> None:
        if not code_verifier:
            raise GoogleAuthError("OAuth code verifier was not generated.")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps({"state": state, "code_verifier": code_verifier}),
            encoding="utf-8",
        )

    def _load_state(self) -> dict[str, str]:
        if not self.state_path.exists():
            raise GoogleAuthError("OAuth state is missing. Restart the flow at /google/oauth/start.")
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not data.get("state") or not data.get("code_verifier"):
            raise GoogleAuthError("OAuth state is incomplete. Restart the flow at /google/oauth/start.")
        return data

    def _delete_state(self) -> None:
        if self.state_path.exists():
            self.state_path.unlink()

    def _fernet(self) -> Fernet:
        settings = get_settings()
        if not settings.token_encryption_key:
            raise GoogleAuthError("TOKEN_ENCRYPTION_KEY must be set in .env.")
        return Fernet(settings.token_encryption_key.encode("ascii"))

    def _use_database_token_store(self) -> bool:
        return get_settings().token_store == "database"


def _decode_mime_header(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value
