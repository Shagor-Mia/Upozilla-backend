import uuid
from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.location import Location
from app.db.models.tenant import Tenant


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


def assert_location_in_tenant(db: Session, location_id: uuid.UUID, tenant_id: uuid.UUID | None) -> None:
    """`locations` holds the entire country's administrative tree (Section 4),
    not one tenant's slice of it, so a bare "does this id exist" check lets a
    listing attach a location from anywhere in the country. Raises 400 if
    `location_id` sits outside the resolved tenant's upazila subtree.
    Permissive (no-op) when the tenant can't be resolved or has no
    `upazila_id` set yet - same escape hatch as `content_scope.tenant_scoped`."""
    if tenant_id is None:
        return
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None or tenant.upazila_id is None:
        return
    if not is_location_within(db, location_id, tenant.upazila_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="location is outside your tenant's area")
