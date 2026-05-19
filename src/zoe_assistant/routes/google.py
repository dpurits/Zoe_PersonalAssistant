from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from zoe_assistant.config import get_settings
from zoe_assistant.services.google_service import GoogleAuthError, GoogleService


router = APIRouter(prefix="/google", tags=["google"])


class DraftRequest(BaseModel):
    to: str
    subject: str
    body: str


@router.get("/oauth/start")
async def start_google_oauth() -> RedirectResponse:
    try:
        authorization_url = GoogleService().build_authorization_url()
    except GoogleAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Google OAuth start failed: {exc}") from exc
    return RedirectResponse(authorization_url)


@router.get("/oauth/callback")
async def google_oauth_callback(request: Request) -> dict[str, Any]:
    try:
        diagnostics = GoogleService().handle_oauth_callback(str(request.url))
    except GoogleAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Google OAuth callback failed: {exc}") from exc
    return {
        "status": "connected",
        "message": "Google OAuth completed. You can close this tab.",
        "diagnostics": diagnostics,
    }


@router.get("/oauth/status")
async def google_oauth_status() -> dict:
    return GoogleService().connection_status()


@router.get("/oauth/storage-test")
async def google_oauth_storage_test() -> dict:
    try:
        return GoogleService().test_token_storage()
    except GoogleAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/calendar/events")
async def upcoming_calendar_events(days: int = Query(default=7, ge=1, le=31)) -> dict:
    settings = get_settings()
    now = datetime.now(settings.tzinfo)
    end = now + timedelta(days=days)
    try:
        events = GoogleService().list_calendar_events(now, end)
    except GoogleAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"events": events}


@router.get("/gmail/search")
async def search_gmail(q: str = Query(default="newer_than:7d"), max_results: int = Query(default=10, ge=1, le=25)) -> dict:
    try:
        messages = GoogleService().search_gmail(query=q, max_results=max_results)
    except GoogleAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"messages": messages}


@router.post("/gmail/drafts")
async def create_gmail_draft(request: DraftRequest) -> dict:
    try:
        draft = GoogleService().create_gmail_draft(
            to=request.to,
            subject=request.subject,
            body=request.body,
        )
    except GoogleAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"draft": draft}
