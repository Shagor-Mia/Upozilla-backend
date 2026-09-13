import uuid

from sqlalchemy.orm import Session

from app.db.models.location import Location, LocationType


def list_locations(
    db: Session, type: LocationType | None = None, parent_id: uuid.UUID | None = None
) -> list[Location]:
    query = db.query(Location)
    if type is not None:
        query = query.filter(Location.type == type)
    if parent_id is not None:
        query = query.filter(Location.parent_id == parent_id)
    return query.order_by(Location.name_bn).all()
