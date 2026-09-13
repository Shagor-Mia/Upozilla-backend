import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_phone_verified
from app.core.rate_limit import rate_limit_by_user
from app.modules.sellers import service
from app.modules.sellers.schemas import SellerProfileResponse, SellerReviewCreate, SellerReviewResponse

router = APIRouter(prefix="/sellers", tags=["sellers"])


@router.get("/{seller_id}", response_model=SellerProfileResponse)
def get_seller_profile(seller_id: uuid.UUID, db: Session = Depends(get_db)) -> SellerProfileResponse:
    return service.get_seller_profile(db, seller_id)


@router.get("/{seller_id}/reviews", response_model=list[SellerReviewResponse])
def list_reviews(seller_id: uuid.UUID, db: Session = Depends(get_db)) -> list[SellerReviewResponse]:
    return service.list_reviews(db, seller_id)


@router.post(
    "/{seller_id}/reviews",
    response_model=SellerReviewResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_by_user("reviews", limit=10, window_seconds=3600))],
)
def create_review(
    seller_id: uuid.UUID,
    payload: SellerReviewCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_phone_verified),
) -> SellerReviewResponse:
    return service.create_review(db, current_user, seller_id, payload)
