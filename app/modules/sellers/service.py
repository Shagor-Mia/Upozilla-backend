import uuid
from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser
from app.core.tenant import resolve_tenant_id
from app.db.models import (
    ExchangeListing,
    ListingStatus,
    ListingType,
    MarketplaceProduct,
    ModerationStatus,
    ProductStatus,
    SellerReview,
    Shop,
    ShopStatus,
    User,
    UserTrustScore,
)
from app.modules.auth.phone import mask_phone
from app.modules.moderation import trust as trust_service
from app.modules.sellers.schemas import (
    SellerProfileResponse,
    SellerReviewCreate,
    SellerReviewResponse,
    SellerSummary,
)


def _summary(user: User, trust: UserTrustScore | None) -> SellerSummary:
    return SellerSummary(
        id=user.id,
        full_name=user.full_name,
        phone_masked=mask_phone(user.phone) if user.phone_verified_at else None,
        phone_verified=user.phone_verified_at is not None,
        member_since=user.created_at,
        trust_score=trust.score if trust else 0,
        avg_rating=trust.avg_rating if trust else None,
        review_count=trust.review_count if trust else 0,
    )


def get_seller_summaries(db: Session, user_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, SellerSummary]:
    ids = set(user_ids)
    if not ids:
        return {}
    users = db.query(User).filter(User.id.in_(ids)).all()
    trust = {t.user_id: t for t in db.query(UserTrustScore).filter(UserTrustScore.user_id.in_(ids)).all()}
    return {u.id: _summary(u, trust.get(u.id)) for u in users}


def _get_seller(db: Session, seller_id: uuid.UUID) -> User:
    user = db.query(User).filter(User.id == seller_id, User.status == "active").first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="seller not found")
    return user


def _review_response(review: SellerReview, reviewer_name: str) -> SellerReviewResponse:
    return SellerReviewResponse(
        id=review.id,
        seller_user_id=review.seller_user_id,
        reviewer_user_id=review.reviewer_user_id,
        reviewer_name=reviewer_name,
        listing_type=review.listing_type,
        listing_id=review.listing_id,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
    )


def list_reviews(db: Session, seller_id: uuid.UUID) -> list[SellerReviewResponse]:
    rows = (
        db.query(SellerReview, User.full_name)
        .join(User, User.id == SellerReview.reviewer_user_id)
        .filter(SellerReview.seller_user_id == seller_id)
        .order_by(SellerReview.created_at.desc())
        .limit(100)
        .all()
    )
    return [_review_response(review, name) for review, name in rows]


def get_seller_profile(db: Session, seller_id: uuid.UUID) -> SellerProfileResponse:
    user = _get_seller(db, seller_id)
    trust = db.query(UserTrustScore).filter(UserTrustScore.user_id == seller_id).first()

    public_exchange = db.query(ExchangeListing).filter(
        ExchangeListing.seller_user_id == seller_id,
        ExchangeListing.moderation_status == ModerationStatus.APPROVED.value,
    )
    public_products = db.query(MarketplaceProduct).filter(
        MarketplaceProduct.seller_user_id == seller_id,
        MarketplaceProduct.moderation_status == ModerationStatus.APPROVED.value,
    )
    public_shops = db.query(Shop).filter(
        Shop.seller_user_id == seller_id, Shop.moderation_status == ModerationStatus.APPROVED.value
    )
    active = (
        public_exchange.filter(ExchangeListing.status == ListingStatus.ACTIVE.value).count()
        + public_products.filter(MarketplaceProduct.status == ProductStatus.ACTIVE.value).count()
        + public_shops.filter(Shop.status == ShopStatus.ACTIVE.value).count()
    )

    summary = _summary(user, trust)
    return SellerProfileResponse(
        **summary.model_dump(),
        active_listings=active,
        total_listings=public_exchange.count() + public_products.count() + public_shops.count(),
        reviews=list_reviews(db, seller_id),
    )


def _listing_belongs_to_seller(db: Session, listing_type: ListingType, listing_id: uuid.UUID, seller_id: uuid.UUID) -> bool:
    if listing_type is ListingType.EXCHANGE:
        return (
            db.query(ExchangeListing.id)
            .filter(ExchangeListing.id == listing_id, ExchangeListing.seller_user_id == seller_id)
            .first()
            is not None
        )
    return (
        db.query(MarketplaceProduct.id)
        .filter(MarketplaceProduct.id == listing_id, MarketplaceProduct.seller_user_id == seller_id)
        .first()
        is not None
    )


def create_review(
    db: Session, reviewer: CurrentUser, seller_id: uuid.UUID, payload: SellerReviewCreate
) -> SellerReviewResponse:
    if reviewer.uuid == seller_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="you cannot review yourself")
    _get_seller(db, seller_id)

    if (payload.listing_type is None) != (payload.listing_id is None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="listing_type and listing_id go together")
    if payload.listing_type and payload.listing_id:
        if not _listing_belongs_to_seller(db, payload.listing_type, payload.listing_id, seller_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing not found for this seller")

    duplicate = (
        db.query(SellerReview)
        .filter(
            SellerReview.seller_user_id == seller_id,
            SellerReview.reviewer_user_id == reviewer.uuid,
            SellerReview.listing_type == (payload.listing_type.value if payload.listing_type else None),
            SellerReview.listing_id == payload.listing_id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="you already reviewed this seller for this listing")

    review = SellerReview(
        tenant_id=resolve_tenant_id(db, reviewer),
        seller_user_id=seller_id,
        reviewer_user_id=reviewer.uuid,
        listing_type=payload.listing_type.value if payload.listing_type else None,
        listing_id=payload.listing_id,
        rating=payload.rating,
        comment=payload.comment.strip() if payload.comment else None,
    )
    db.add(review)
    db.flush()
    trust_service.recompute(db, seller_id)
    db.commit()
    db.refresh(review)

    reviewer_row = db.query(User).filter(User.id == reviewer.uuid).first()
    return _review_response(review, reviewer_row.full_name if reviewer_row else "")
