from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.triggers.cron import CronTrigger

from app.services.ftp_import import get_ftp_settings, run_ftp_import, set_next_run


scheduler = BackgroundScheduler(timezone="Europe/Moscow")


def _update_next_run(event=None) -> None:
    job = scheduler.get_job("daily_ftp_import")
    set_next_run(job.next_run_time if job else None)


def refresh_ftp_schedule() -> None:
    settings = get_ftp_settings()
    hour, minute = (int(part) for part in settings.run_time.split(":", 1))
    scheduler.add_job(
        run_ftp_import,
        CronTrigger(hour=hour, minute=minute, timezone="Europe/Moscow"),
        id="daily_ftp_import",
        replace_existing=True,
        max_instances=1,
        kwargs={"retry_when_empty": True},
    )
    _update_next_run()


def start_ftp_scheduler() -> None:
    if not scheduler.running:
        scheduler.add_listener(_update_next_run, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        scheduler.start()
    refresh_ftp_schedule()


def stop_ftp_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
