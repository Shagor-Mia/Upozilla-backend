"""Celery beat housekeeping for Phase 2: listing expiry (Section 5.8
`status=expired`) and OTP retention cleanup (Section 14.4)."""

from app.core.database import SessionLocal
from app.modules.auth import otp_service
from app.modules.exchange import service as exchange_service
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.marketplace_maintenance.expire_stale_exchange_listings")
def expire_stale_exchange_listings() -> int:
    db = SessionLocal()
    try:
        return exchange_service.expire_stale(db)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.marketplace_maintenance.purge_otp_codes")
def purge_otp_codes() -> int:
    db = SessionLocal()
    try:
        return otp_service.purge_stale_codes(db)
    finally:
        db.close()
