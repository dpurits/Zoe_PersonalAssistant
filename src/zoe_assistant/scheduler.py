from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from zoe_assistant.config import Settings
from zoe_assistant.services.briefing_service import BriefingService


def build_scheduler(settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    briefing_service = BriefingService()

    hour, minute = _parse_hhmm(settings.daily_brief_time)
    scheduler.add_job(
        briefing_service.run_daily_brief,
        CronTrigger(hour=hour, minute=minute, timezone=settings.timezone),
        id="daily_morning_brief",
        replace_existing=True,
    )

    finance_hour, finance_minute = _parse_hhmm(settings.sunday_finance_brief_time)
    scheduler.add_job(
        briefing_service.run_sunday_finance_brief,
        CronTrigger(day_of_week="sun", hour=finance_hour, minute=finance_minute, timezone=settings.timezone),
        id="sunday_finance_brief",
        replace_existing=True,
    )

    return scheduler


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour_text, minute_text = value.split(":", maxsplit=1)
    return int(hour_text), int(minute_text)
