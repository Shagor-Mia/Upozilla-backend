import uuid
from collections import defaultdict

from sqlalchemy.orm import Session

from app.db.models.location import Location


def is_location_within(db: Session, location_id: uuid.UUID | None, ancestor_id: uuid.UUID | None) -> bool:
    """Section 12 scope rule: `scope_location_id IS NULL` means unscoped; otherwise
    the resource's location must sit inside the scope's subtree."""
    if ancestor_id is None:
        return True
    if location_id is None:
        return False

    current: uuid.UUID | None = location_id
    # The hierarchy is only five levels deep (Section 4); cap the walk anyway so a
    # corrupted parent cycle can't hang a request.
    for _ in range(8):
        if current is None:
            return False
        if current == ancestor_id:
            return True
        row = db.query(Location.parent_id).filter(Location.id == current).first()
        current = row[0] if row else None
    return False


def subtree_location_ids(db: Session, root_id: uuid.UUID) -> set[uuid.UUID]:
    """All location ids at/under `root_id`. The whole tree for one tenant is a
    few dozen rows, so one query + in-memory walk beats a recursive CTE here."""
    children: dict[uuid.UUID | None, list[uuid.UUID]] = defaultdict(list)
    for loc_id, parent_id in db.query(Location.id, Location.parent_id).all():
        children[parent_id].append(loc_id)

    result: set[uuid.UUID] = set()
    stack = [root_id]
    while stack:
        node = stack.pop()
        if node in result:
            continue
        result.add(node)
        stack.extend(children.get(node, ()))
    return result
