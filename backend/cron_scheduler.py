"""
Cron Scheduler for Trading Intel MVP
Uses built-in threading.Timer — no external deps needed.
Runs the content pipeline on a schedule.
"""

import time
import threading
import asyncio
import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from app.services.content_pipeline import (
    run_morning_briefing_pipeline,
    run_macro_roundup_pipeline,
    run_full_daily_pipeline,
)
from app.services import rss_news_service as news_service
from app.services.alert_service import check_alerts


def run_async_in_thread(coro):
    """Run an async coroutine in a background thread with its own event loop."""
    def _thread_target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro)
        finally:
            loop.close()
    t = threading.Thread(target=_thread_target, daemon=True)
    t.start()
    return t


def run_sync_in_thread(fn, *args, **kwargs):
    """Run a synchronous function in a background thread."""
    def _target():
        fn(*args, **kwargs)
    t = threading.Thread(target=_target, daemon=True)
    t.start()
    return t


def schedule_morning_briefing(hour=6, minute=0, timezone="UTC"):
    """Schedule morning briefing to run daily at hour:minute UTC."""
    now = datetime.utcnow()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    delay = (target - now).total_seconds()
    print(f"Morning briefing scheduled in {delay/3600:.1f} hours")

    def run_and_check():
        async def _run():
            await run_morning_briefing_pipeline()
            # Check alerts after pipeline run
            await check_alerts({"pipeline": "morning_briefing"})

        run_async_in_thread(_run())
        schedule_morning_briefing(hour, minute)

    t = threading.Timer(delay, run_and_check)
    t.daemon = True
    t.start()
    return t


def schedule_weekly_roundup(day="Friday", hour=17, minute=0):
    """Schedule macro roundup to run weekly on day at hour:minute UTC."""
    days = {
        "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
        "Friday": 4, "Saturday": 5, "Sunday": 6
    }
    now = datetime.utcnow()
    weekday = now.weekday()
    target_weekday = days[day]
    days_ahead = target_weekday - weekday
    if days_ahead < 0:
        days_ahead += 7
    if days_ahead == 0 and (now.hour > hour or (now.hour == hour and now.minute >= minute)):
        days_ahead += 7
    target = now + timedelta(days=days_ahead)
    target = target.replace(hour=hour, minute=minute, second=0, microsecond=0)
    delay = (target - now).total_seconds()
    print(f"Weekly roundup scheduled in {delay/86400:.1f} days")

    def run_and_check():
        async def _run():
            await run_macro_roundup_pipeline()
            await check_alerts({"pipeline": "weekly_roundup"})

        run_async_in_thread(_run())
        schedule_weekly_roundup(day, hour, minute)

    t = threading.Timer(delay, run_and_check)
    t.daemon = True
    t.start()
    return t


def schedule_news_fetch(interval_minutes=30):
    """Schedule news RSS fetch to run every N minutes."""
    delay = interval_minutes * 60
    print(f"News fetch scheduled every {interval_minutes} minutes")
    t = threading.Timer(
        delay,
        lambda: (
            run_sync_in_thread(news_service.fetch_all_sources_sync),
            schedule_news_fetch(interval_minutes)
        )
    )
    t.daemon = True
    t.start()
    return t


if __name__ == "__main__":
    print("=== Trading Intel Cron Scheduler ===")
    print(f"Started at {datetime.utcnow().isoformat()} UTC")

    # Start schedule (comment out for manual-only)
    # schedule_morning_briefing(hour=6, minute=0)
    # schedule_weekly_roundup(day="Friday", hour=17, minute=0)
    # schedule_news_fetch(interval_minutes=30)

    # Keep running
    while True:
        time.sleep(60)
