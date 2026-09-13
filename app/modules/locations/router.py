import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_locale
from app.db.models.location import LocationType
from app.modules.locations import service
from app.modules.locations.schemas import LocationResponse

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=list[LocationResponse])
def list_locations(
    type: LocationType | None = None,
    parent_id: uuid.UUID | None = None,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
) -> list[LocationResponse]:
    locations = service.list_locations(db, type=type, parent_id=parent_id)
    return [LocationResponse.from_model(loc, locale) for loc in locations]
