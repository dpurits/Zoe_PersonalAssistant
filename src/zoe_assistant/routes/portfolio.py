import json
from pathlib import Path

from fastapi import APIRouter


router = APIRouter(prefix="/portfolio", tags=["portfolio"])
WATCHLIST_PATH = Path(__file__).resolve().parents[3] / "data" / "portfolio_watchlist.json"


@router.get("/watchlist")
async def watchlist() -> dict:
    return json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))

