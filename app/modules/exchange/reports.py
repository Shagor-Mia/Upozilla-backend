import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser
from app.core.tenant import resolve_tenant_id
from app.db.models import ListingReport, ListingType, ReportStatus
from app.modules.exchange.lookup import get_public_listing
from app.modules.exchange.schemas import ListingReportCreate, ListingReportResponse
from app.modules.moderation import service as moderation_service


def create_report(
    db: Session,
    reporter: CurrentUser,
    listing_type: ListingType,
    listing_id: uuid.UUID,
    payload: ListingReportCreate,
) -> ListingReportResponse:
    listing = get_public_listing(db, listing_type, listing_id)
    if listing.seller_user_id == reporter.uuid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="you cannot report your own listing")

    duplicate = (
        db.query(ListingReport)
        .filter(
            ListingReport.listing_type == listing_type.value,
            ListingReport.listing_id == listing_id,
            ListingReport.reporter_user_id == reporter.uuid,
            ListingReport.status == ReportStatus.OPEN.value,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="you already reported this listing")

    report = ListingReport(
        tenant_id=resolve_tenant_id(db, reporter),
        listing_type=listing_type.value,
        listing_id=listing_id,
        reporter_user_id=reporter.uuid,
        reason=payload.reason.value,
        details=payload.details.strip() if payload.details else None,
    )
    db.add(report)
    db.flush()
    moderation_service.enqueue_report(db, report=report, location_id=listing.location_id)
    db.commit()
    db.refresh(report)
    return ListingReportResponse(
        id=report.id,
        listing_type=report.listing_type,
        listing_id=report.listing_id,
        reason=report.reason,
        status=report.status,
        created_at=report.created_at,
    )
