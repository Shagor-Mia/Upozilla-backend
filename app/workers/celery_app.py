from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery("upazila", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.autodiscover_tasks(["app.workers.tasks"])

celery_app.conf.beat_schedule = {
    "ingest-news-every-30-minutes": {
        "task": "app.workers.tasks.news_ingest.ingest_all_active_sources",
        "schedule": crontab(minute="*/30"),
    },
    "expire-exchange-listings-daily": {
        "task": "app.workers.tasks.marketplace_maintenance.expire_stale_exchange_listings",
        "schedule": crontab(hour=3, minute=0),
    },
    "purge-otp-codes-daily": {
        "task": "app.workers.tasks.marketplace_maintenance.purge_otp_codes",
        "schedule": crontab(hour=3, minute=30),
    },
}
