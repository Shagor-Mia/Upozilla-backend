"""Section 5.9 / Section 10 trust score.

    score = approved listings + rounded avg rating - 2 x upheld reports

Tracked, not hard-gated (Section 10): its only automatic effect is skipping
the manual moderation queue once `score >= AUTO_APPROVE_TRUST_SCORE`.
"""

import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    ExchangeListing,
    ListingReport,
    ListingType,
    MarketplaceProduct,
    ModerationStatus,
    ReportStatus,
    SellerReview,
    Shop,
    UserTrustScore,
)

UPHELD_REPORT_PENALTY = 2


def get_or_create(db: Session, user_id: uuid.UUID) -> UserTrustScore:
    trust = db.query(UserTrustScore).filter(UserTrustScore.user_id == user_id).first()
    if trust is None:
        trust = UserTrustScore(user_id=user_id)
        db.add(trust)
        db.flush()
    return trust


def _upheld_reports(db: Session, user_id: uuid.UUID) -> int:
    exchange_ids = db.query(ExchangeListing.id).filter(ExchangeListing.seller_user_id == user_id)
    product_ids = db.query(MarketplaceProduct.id).filter(MarketplaceProduct.seller_user_id == user_id)
    return (
        db.query(ListingReport)
        .filter(
            ListingReport.status == ReportStatus.UPHELD.value,
            (
                (ListingReport.listing_type == ListingType.EXCHANGE.value)
                & ListingReport.listing_id.in_(exchange_ids)
            )
            | (
                (ListingReport.listing_type == ListingType.MARKETPLACE.value)
                & ListingReport.listing_id.in_(product_ids)
            ),
        )
        .count()
    )


def recompute(db: Session, user_id: uuid.UUID) -> UserTrustScore:
    """Flushes but does not commit - callers own the transaction."""
    trust = get_or_create(db, user_id)

    approved = (
        db.query(ExchangeListing)
        .filter(
            ExchangeListing.seller_user_id == user_id,
            ExchangeListing.moderation_status == ModerationStatus.APPROVED.value,
        )
        .count()
        + db.query(MarketplaceProduct)
        .filter(
            MarketplaceProduct.seller_user_id == user_id,
            MarketplaceProduct.moderation_status == ModerationStatus.APPROVED.value,
        )
        .count()
        + db.query(Shop)
        .filter(Shop.seller_user_id == user_id, Shop.moderation_status == ModerationStatus.APPROVED.value)
        .count()
    )
    total = (
        db.query(ExchangeListing).filter(ExchangeListing.seller_user_id == user_id).count()
        + db.query(MarketplaceProduct).filter(MarketplaceProduct.seller_user_id == user_id).count()
        + db.query(Shop).filter(Shop.seller_user_id == user_id).count()
    )
    avg_rating, review_count = (
        db.query(func.avg(SellerReview.rating), func.count(SellerReview.id))
        .filter(SellerReview.seller_user_id == user_id)
        .one()
    )
    upheld = _upheld_reports(db, user_id)

    trust.total_listings = total
    trust.total_reports = upheld
    trust.avg_rating = round(float(avg_rating), 2) if avg_rating is not None else None
    trust.review_count = int(review_count or 0)
    rating_bonus = round(float(avg_rating)) if avg_rating is not None else 0
    trust.score = approved + rating_bonus - UPHELD_REPORT_PENALTY * upheld
    db.flush()
    return trust
