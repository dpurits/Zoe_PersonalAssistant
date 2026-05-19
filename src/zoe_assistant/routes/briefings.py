from fastapi import APIRouter, HTTPException

from zoe_assistant.services.briefing_service import BriefingService
from zoe_assistant.services.google_service import GoogleAuthError


router = APIRouter(prefix="/briefings", tags=["briefings"])


@router.get("/daily/preview")
async def daily_brief_preview() -> dict:
    try:
        return BriefingService().build_daily_brief_preview()
    except GoogleAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
