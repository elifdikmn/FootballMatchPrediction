"""Optional local scheduler. Production scheduling is handled by GitHub Actions."""

from apscheduler.schedulers.blocking import BlockingScheduler

from db_setup import init_db
from fixture_sync import sync_all
from sync_pipeline import predict_pending_fixtures


scheduler = BlockingScheduler(timezone="UTC")


@scheduler.scheduled_job("cron", hour=2, minute=17)
def full_sync():
    totals = sync_all("full")
    totals["predictions"] = predict_pending_fixtures()
    print("Daily fixture sync:", totals)


@scheduler.scheduled_job("cron", hour="*/3", minute=43)
def refresh_sync():
    totals = sync_all("refresh")
    totals["predictions"] = predict_pending_fixtures()
    print("Three-hour fixture refresh:", totals)


if __name__ == "__main__":
    init_db()
    print("Scheduler running: daily full sync and three-hour refresh.")
    scheduler.start()
