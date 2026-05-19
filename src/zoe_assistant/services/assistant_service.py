from zoe_assistant.config import get_settings
from zoe_assistant.services.briefing_service import BriefingService
from zoe_assistant.services.google_service import GoogleAuthError, GoogleService


class AssistantService:
    """Routes user messages to the assistant engine.

    The current implementation is a deterministic shell so the WhatsApp and API
    plumbing can be tested before connecting model tool calls.
    """

    async def reply(self, message: str, sender: str) -> str:
        settings = get_settings()
        normalized = message.strip().lower()

        if not normalized:
            return "Send me a message and I will help. You can write in English or Hebrew."

        if _mentions_daily_brief(normalized, message):
            try:
                return BriefingService().build_daily_brief_preview()["summary"]
            except GoogleAuthError as exc:
                return f"Google is not connected yet: {exc}"

        if _mentions_calendar(normalized, message):
            try:
                events = GoogleService().list_calendar_events_for_days(days=7)
            except GoogleAuthError as exc:
                return f"Google Calendar is not connected yet: {exc}"
            if not events:
                return "I found no calendar events in the next 7 days."
            lines = [f"I found {len(events)} upcoming calendar event(s):"]
            for event in events[:8]:
                start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
                lines.append(f"- {start}: {event.get('summary')}")
            return "\n".join(lines)

        if _mentions_gmail(normalized, message):
            try:
                messages = GoogleService().search_gmail(query="newer_than:7d", max_results=8)
            except GoogleAuthError as exc:
                return f"Gmail is not connected yet: {exc}"
            if not messages:
                return "I found no Gmail messages from the last 7 days."
            lines = [f"I found {len(messages)} recent Gmail item(s):"]
            for item in messages:
                lines.append(f"- {item.get('from')}: {item.get('subject') or '(No subject)'}")
            return "\n".join(lines)

        if "portfolio" in normalized or "watchlist" in normalized:
            return (
                "I loaded your watchlist from the screenshots. Next step is connecting a market data "
                "provider so the Sunday review can analyze price moves, news, and candidates."
            )

        if _looks_hebrew(message):
            return (
                "אני מוכן להתחיל. בשלב הראשון אחבר WhatsApp, Google Calendar, Gmail drafts, "
                "וסיכום יומי בשעה 07:45 לפי שעון ישראל."
            )

        return (
            f"Zoe is online in {settings.timezone}. I can start with WhatsApp chat, Google Calendar, "
            "Gmail drafts, daily briefs, and the Sunday finance review."
        )


def _looks_hebrew(text: str) -> bool:
    return any("\u0590" <= char <= "\u05ff" for char in text)


def _mentions_daily_brief(normalized: str, original: str) -> bool:
    return any(term in normalized for term in ["daily brief", "morning brief", "today summary"]) or any(
        term in original for term in ["סיכום יומי", "סיכום בוקר", "היום שלי"]
    )


def _mentions_calendar(normalized: str, original: str) -> bool:
    return "calendar" in normalized or any(term in original for term in ["יומן", "פגישות", "לו\"ז"])


def _mentions_gmail(normalized: str, original: str) -> bool:
    return any(term in normalized for term in ["email", "gmail", "inbox"]) or any(
        term in original for term in ["אימייל", "מייל", "תיבת דואר"]
    )
