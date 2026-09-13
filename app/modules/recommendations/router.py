import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_locale, get_optional_user
from app.modules.recommendations import service
from app.modules.recommendations.schemas import RecommendationsResponse

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationsResponse)
def get_recommendations(
    location_id: uuid.UUID | None = None,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    viewer: CurrentUser | None = Depends(get_optional_user),
) -> RecommendationsResponse:
    return service.get_recommendations(db, viewer, locale, location_id)
