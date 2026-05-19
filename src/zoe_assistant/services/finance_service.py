import json
from pathlib import Path


class FinanceService:
    def __init__(self) -> None:
        self.watchlist_path = Path(__file__).resolve().parents[3] / "data" / "portfolio_watchlist.json"

    def load_watchlist(self) -> dict:
        return json.loads(self.watchlist_path.read_text(encoding="utf-8"))

