from app.db.models.location import Location, LocationType


def get_or_create_location(db, type_: LocationType, name: str, parent_id) -> Location:
    """`name` is the seed source (currently English-only) and is stored as
    both `name_bn`/`name_en` until an admin (or automatic translation)
    supplies a real Bangla name."""
    existing = (
        db.query(Location)
        .filter(Location.type == type_, Location.name_bn == name, Location.parent_id == parent_id)
        .first()
    )
    if existing:
        return existing

    location = Location(type=type_, name_bn=name, name_en=name, parent_id=parent_id)
    db.add(location)
    db.flush()
    return location
