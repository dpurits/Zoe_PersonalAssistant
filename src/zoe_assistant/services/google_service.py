import base64
import json
import os
import time
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.message import EmailMessage
from pathlib import Path
from random import SystemRandom
from string import ascii_letters, digits
from typing import Any
from urllib.parse import parse_qs, urlparse

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

    def required_scopes(self) -> list[str]:
        return [
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.compose",
        ]

    def build_authorization_url(self) -> str:
        code_verifier = _generate_code_verifier()
        state = self._encode_oauth_state(code_verifier)
        flow = self._build_flow(state=state, code_verifier=code_verifier)
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return authorization_url

    def handle_oauth_callback(self, authorization_response: str) -> None:
        oauth_state = self._decode_oauth_state(authorization_response)
        flow = self._build_flow(
            state=oauth_state["state"],
            code_verifier=oauth_state["code_verifier"],
        )
        flow.fetch_token(authorization_response=authorization_response)

        if flow.credentials is None:
            raise GoogleAuthError("Google did not return OAuth credentials.")

        self._save_credentials(flow.credentials)

    def is_connected(self) -> bool:
        return self.connection_status()["connected"]

    def connection_status(self) -> dict[str, Any]:
        diagnostics = self._token_store_diagnostics()
        try:
            credentials = self._load_credentials()
        except GoogleAuthError as exc:
            return {
                "connected": False,
                "reason": str(exc),
                "token_store": get_settings().token_store,
                "diagnostics": diagnostics,
            }
        connected = bool(credentials and (credentials.valid or credentials.refresh_token))
        return {
            "connected": connected,
            "reason": None if connected else "Google credentials exist but are not usable.",
            "token_store": get_settings().token_store,
            "has_refresh_token": bool(credentials.refresh_token),
            "diagnostics": diagnostics,
        }

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
            token_path = self._token_path()
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_bytes(encrypted)

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
        token_path = self._token_path()
        if not token_path.exists():
            return None
        return token_path.read_bytes()

    def _fernet(self) -> Fernet:
        settings = get_settings()
        if not settings.token_encryption_key:
            raise GoogleAuthError("TOKEN_ENCRYPTION_KEY must be set in .env.")
        return Fernet(settings.token_encryption_key.encode("ascii"))

    def _use_database_token_store(self) -> bool:
        return get_settings().token_store == "database"

    def _token_store_diagnostics(self) -> dict[str, Any]:
        if self._use_database_token_store():
            return {"mode": "database"}
        token_path = self._token_path()
        return {
            "mode": "file",
            "cwd": str(Path.cwd()),
            "token_path": str(token_path.resolve()),
            "token_file_exists": token_path.exists(),
            "token_file_size": token_path.stat().st_size if token_path.exists() else 0,
            "token_parent_exists": token_path.parent.exists(),
            "token_parent_writable": os.access(token_path.parent, os.W_OK)
            if token_path.parent.exists()
            else None,
        }

    def _token_path(self) -> Path:
        settings = get_settings()
        if settings.token_file_path:
            return Path(settings.token_file_path)
        if settings.app_env == "production":
            return Path("/tmp/zoe/google_credentials.enc")
        return Path(".local/google_credentials.enc")

    def _encode_oauth_state(self, code_verifier: str) -> str:
        payload = json.dumps(
            {
                "code_verifier": code_verifier,
                "issued_at": int(time.time()),
            }
        ).encode("utf-8")
        return self._fernet().encrypt(payload).decode("ascii")

    def _decode_oauth_state(self, authorization_response: str) -> dict[str, str]:
        state = parse_qs(urlparse(authorization_response).query).get("state", [None])[0]
        if not state:
            raise GoogleAuthError("OAuth state is missing. Restart the flow at /google/oauth/start.")
        try:
            payload = self._fernet().decrypt(state.encode("ascii"), ttl=600)
        except InvalidToken as exc:
            raise GoogleAuthError("OAuth state expired or could not be decrypted. Restart at /google/oauth/start.") from exc
        data = json.loads(payload.decode("utf-8"))
        if not data.get("code_verifier"):
            raise GoogleAuthError("OAuth state is incomplete. Restart the flow at /google/oauth/start.")
        data["state"] = state
        return data


def _decode_mime_header(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _generate_code_verifier() -> str:
    chars = ascii_letters + digits + "-._~"
    random = SystemRandom()
    return "".join(random.choice(chars) for _ in range(128))
