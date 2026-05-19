from datetime import datetime, time, timedelta
from typing import Any

from zoe_assistant.config import get_settings
from zoe_assistant.services.google_service import GoogleAuthError, GoogleService


class BriefingService:
    def build_daily_brief_preview(self) -> dict[str, Any]:
        settings = get_settings()
        now = datetime.now(settings.tzinfo)
        day_start = datetime.combine(now.date(), time.min, tzinfo=settings.tzinfo)
        day_end = day_start + timedelta(days=1)

        google = GoogleService()
        events = google.list_calendar_events(day_start, day_end)
        messages = google.search_gmail(query="newer_than:2d", max_results=10)

        return {
            "title": "Daily brief",
            "timezone": settings.timezone,
            "date": now.date().isoformat(),
            "calendar": {
                "count": len(events),
                "events": events,
            },
            "gmail": {
                "count": len(messages),
                "messages": messages,
            },
            "summary": self._compose_plain_summary(events=events, messages=messages),
        }

    async def run_daily_brief(self) -> None:
        try:
            preview = self.build_daily_brief_preview()
        except GoogleAuthError as exc:
            print(f"Daily brief skipped: {exc}")
            return
        print(preview["summary"])

    async def run_sunday_finance_brief(self) -> None:
        # TODO: Gather market data, portfolio changes, news, and candidate ideas.
        print("Sunday finance brief job triggered")

    def _compose_plain_summary(self, events: list[dict[str, Any]], messages: list[dict[str, Any]]) -> str:
        lines = ["Good morning. Here is your daily brief."]

        if events:
            lines.append(f"You have {len(events)} calendar event(s) today:")
            for event in events[:5]:
                start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
                lines.append(f"- {start}: {event.get('summary')}")
        else:
            lines.append("You have no calendar events today.")

        if messages:
            lines.append(f"Recent Gmail items found: {len(messages)}.")
            for message in messages[:5]:
                sender = message.get("from") or "Unknown sender"
                subject = message.get("subject") or "(No subject)"
                lines.append(f"- {sender}: {subject}")
        else:
            lines.append("No recent Gmail items were found.")

        return "\n".join(lines)
