"""Moderation queue (Section 5.9, Section 10): every new listing enters the
queue as pending unless the seller's trust score auto-approves it; reports
enter the same queue for a moderator to uphold or dismiss."""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core import runtime_settings
from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.location_scope import subtree_location_ids
from app.core.pagination import PageParams
from app.core.rbac import ROLE_PERMISSIONS, Permission, Role, normalize_role
from app.core.tenant import resolve_tenant_id
from app.db.models import (
    ContractDisputeResolution,
    ContractProblem,
    ContractProblemStatus,
    ContractStatus,
    ExchangeListing,
    ListingReport,
    ListingStatus,
    ListingType,
    Location,
    MarketplaceProduct,
    ModerationEntityType,
    ModerationQueue,
    ModerationQueueStatus,
    ModerationStatus,
    ReportStatus,
    RoleRow,
    Shop,
    Tenant,
    User,
    UserRole,
    WorkContract,
)
from app.modules.moderation import trust as trust_service
from app.modules.moderation.schemas import (
    ModerationDecision,
    ModerationQueueItem,
    ModerationStats,
    QueueListingSnapshot,
    QueueReportSnapshot,
)

Listing = ExchangeListing | MarketplaceProduct | Shop


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- enqueueing (called by the marketplace/exchange services) ---------------------


def enqueue_listing(
    db: Session,
    *,
    entity_type: ModerationEntityType,
    listing: Listing,
    tenant_id: uuid.UUID | None,
) -> str:
    """Returns the listing's resulting moderation_status. Flushes, doesn't commit."""
    trust = trust_service.get_or_create(db, listing.seller_user_id)
    auto_approve = trust.score >= runtime_settings.get_int("auto_approve_trust_score", settings.AUTO_APPROVE_TRUST_SCORE)
    listing.moderation_status = (
        ModerationStatus.APPROVED.value if auto_approve else ModerationStatus.PENDING.value
    )
    db.add(
        ModerationQueue(
            tenant_id=tenant_id,
            entity_type=entity_type.value,
            entity_id=listing.id,
            location_id=listing.location_id,
            reason=f"auto-approved (trust score {trust.score})" if auto_approve else "new listing",
            status=ModerationQueueStatus.APPROVED.value if auto_approve else ModerationQueueStatus.PENDING.value,
            reviewed_at=_now() if auto_approve else None,
        )
    )
    db.flush()
    trust_service.recompute(db, listing.seller_user_id)
    return listing.moderation_status


def reenqueue_after_edit(
    db: Session, *, entity_type: ModerationEntityType, listing: Listing, tenant_id: uuid.UUID | None
) -> None:
    """Content edits by the seller send an approved listing back through review."""
    listing.moderation_status = ModerationStatus.PENDING.value
    pending = (
        db.query(ModerationQueue)
        .filter(
            ModerationQueue.entity_type == entity_type.value,
            ModerationQueue.entity_id == listing.id,
            ModerationQueue.status == ModerationQueueStatus.PENDING.value,
        )
        .first()
    )
    if pending is None:
        db.add(
            ModerationQueue(
                tenant_id=tenant_id,
                entity_type=entity_type.value,
                entity_id=listing.id,
                location_id=listing.location_id,
                reason="listing edited",
            )
        )
    db.flush()


def enqueue_report(db: Session, *, report: ListingReport, location_id: uuid.UUID | None) -> None:
    db.add(
        ModerationQueue(
            tenant_id=report.tenant_id,
            entity_type=ModerationEntityType.LISTING_REPORT.value,
            entity_id=report.id,
            location_id=location_id,
            reason=f"report: {report.reason}",
        )
    )
    db.flush()


def enqueue_contract_dispute(
    db: Session, *, problem: ContractProblem, tenant_id: uuid.UUID | None, location_id: uuid.UUID | None = None
) -> None:
    """Sibling to `enqueue_report` (mirrors `exchange/reports.py::create_report`'s
    call site) - a contract is generic/borderless so `location_id` is always
    None here; kept as a parameter only for signature symmetry."""
    db.add(
        ModerationQueue(
            tenant_id=tenant_id,
            entity_type=ModerationEntityType.CONTRACT_DISPUTE.value,
            entity_id=problem.id,
            location_id=location_id,
            reason=f"contract dispute: {problem.category}",
        )
    )
    db.flush()


# --- moderator scope ---------------------------------------------------------------


def _moderator_scope(db: Session, moderator: CurrentUser) -> set[uuid.UUID] | None:
    """None = unscoped (sees everything). Otherwise the union of location subtrees
    the moderator's scoped roles cover (Section 12).

    Every other org-wide primary role (MARKETPLACE_MODERATOR, UNION_ADMIN,
    BUSINESS_VERIFIER, SUPER_ADMIN) genuinely means "unscoped within this
    deployment" and that's intended - narrower visibility is granted via an
    explicit scoped UserRole assignment instead, unchanged below. UPAZILA_ADMIN
    is different: `locations` holds the *entire country's* administrative
    tree (Section 4), not just this tenant's upazila+unions, so an unscoped
    UPAZILA_ADMIN was seeing (and could moderate) content tagged with any
    location nationwide, not just their own upazila. Scope it to the tenant's
    own subtree instead - a real narrowing, not a no-op, since `locations` is
    much bigger than any one tenant's slice of it."""
    primary = normalize_role(moderator.role)
    if primary is Role.UPAZILA_ADMIN:
        tenant_id = resolve_tenant_id(db, moderator)
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first() if tenant_id else None
        if tenant and tenant.upazila_id:
            return subtree_location_ids(db, tenant.upazila_id)
        return None  # no resolvable tenant - fall back to the pre-existing unscoped behaviour
    if primary and Permission.MARKETPLACE_MODERATE in ROLE_PERMISSIONS[primary]:
        return None

    rows = (
        db.query(UserRole.scope_location_id, RoleRow.name)
        .join(RoleRow, RoleRow.id == UserRole.role_id)
        .filter(UserRole.user_id == moderator.uuid)
        .all()
    )
    scope: set[uuid.UUID] = set()
    for scope_location_id, role_name in rows:
        role = normalize_role(role_name)
        if role is None or Permission.MARKETPLACE_MODERATE not in ROLE_PERMISSIONS[role]:
            continue
        if scope_location_id is None:
            return None
        scope |= subtree_location_ids(db, scope_location_id)
    return scope


def _assert_in_scope(
    db: Session, moderator: CurrentUser, location_id: uuid.UUID | None, entity_type: str | None = None
) -> None:
    # Contracts are generic/borderless (Section 1 of the Work Contract plan -
    # no `location_id` on `WorkContract` at all), unlike location-tagged
    # listings, so the location-subtree narrowing below doesn't make sense
    # for them. The caller already holds MARKETPLACE_MODERATE via
    # `require_permission` before `review()` is ever reached, so this only
    # removes the location filter, not the permission check itself.
    if entity_type == ModerationEntityType.CONTRACT_DISPUTE.value:
        return
    scope = _moderator_scope(db, moderator)
    if scope is None:
        return
    if location_id is None or location_id not in scope:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="outside your moderation scope")


# --- queue reads -------------------------------------------------------------------


def _index_by_id(db: Session, model: type, ids: set[uuid.UUID]) -> dict[uuid.UUID, object]:
    if not ids:
        return {}
    return {row.id: row for row in db.query(model).filter(model.id.in_(ids)).all()}


def _index_names(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    return {user_id: full_name for user_id, full_name in db.query(User.id, User.full_name).filter(User.id.in_(ids))}


def _listing_snapshot_from(
    entity_type: str, listing: Listing | None, seller_names: dict[uuid.UUID, str]
) -> QueueListingSnapshot | None:
    if listing is None:
        return None
    if entity_type == ModerationEntityType.EXCHANGE_LISTING.value:
        listing_type, price, currency = ListingType.EXCHANGE.value, float(listing.price), "BDT"
    elif entity_type == ModerationEntityType.SHOP.value:
        # Shops don't sell at a fixed price - the field exists only for the
        # generic moderation queue display, not a real shop attribute.
        listing_type, price, currency = ModerationEntityType.SHOP.value, 0.0, "BDT"
    else:
        listing_type, price, currency = ListingType.MARKETPLACE.value, float(listing.price), listing.currency
    return QueueListingSnapshot(
        listing_type=listing_type,
        title=listing.name_bn if entity_type == ModerationEntityType.SHOP.value else listing.title_bn,
        price=price,
        currency=currency,
        status=listing.status,
        moderation_status=listing.moderation_status,
        seller_user_id=listing.seller_user_id,
        seller_name=seller_names.get(listing.seller_user_id, ""),
        cover_image=(listing.images or [None])[0],
        description=listing.description_bn,
    )


def _report_snapshot_from(
    report: ListingReport | None,
    reporter_names: dict[uuid.UUID, str],
    exchange_by_id: dict[uuid.UUID, ExchangeListing],
    marketplace_by_id: dict[uuid.UUID, MarketplaceProduct],
) -> QueueReportSnapshot | None:
    if report is None:
        return None
    if report.listing_type == ListingType.EXCHANGE.value:
        listing = exchange_by_id.get(report.listing_id)
    else:
        listing = marketplace_by_id.get(report.listing_id)
    return QueueReportSnapshot(
        reason=report.reason,
        details=report.details,
        status=report.status,
        reporter_name=reporter_names.get(report.reporter_user_id, ""),
        listing_type=report.listing_type,
        listing_id=report.listing_id,
        listing_title=listing.title_bn if listing else None,
        listing_status=listing.status if listing else None,
    )


def _find_listing(db: Session, listing_type: str, listing_id: uuid.UUID) -> Listing | None:
    if listing_type == ListingType.EXCHANGE.value:
        return db.query(ExchangeListing).filter(ExchangeListing.id == listing_id).first()
    return db.query(MarketplaceProduct).filter(MarketplaceProduct.id == listing_id).first()


_ENTITY_MODEL = {
    ModerationEntityType.EXCHANGE_LISTING.value: ExchangeListing,
    ModerationEntityType.SHOP.value: Shop,
}


def _to_item(db: Session, row: ModerationQueue) -> ModerationQueueItem:
    """Single-row lookup for one queue entry (used right after a review
    decision) - reuses list_queue's batched building blocks with singleton
    inputs rather than duplicating the assembly logic."""
    location_name = (
        db.query(Location.name_bn).filter(Location.id == row.location_id).scalar() if row.location_id else None
    )
    item = ModerationQueueItem(
        id=row.id,
        entity_type=ModerationEntityType(row.entity_type),
        entity_id=row.entity_id,
        location_id=row.location_id,
        location_name=location_name,
        reason=row.reason,
        status=ModerationQueueStatus(row.status),
        created_at=row.created_at,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        review_note=row.review_note,
    )

    if row.entity_type == ModerationEntityType.LISTING_REPORT.value:
        report = db.query(ListingReport).filter(ListingReport.id == row.entity_id).first()
        reporter_names = _index_names(db, {report.reporter_user_id} if report else set())
        exchange_by_id: dict[uuid.UUID, ExchangeListing] = {}
        marketplace_by_id: dict[uuid.UUID, MarketplaceProduct] = {}
        if report and report.listing_type == ListingType.EXCHANGE.value:
            exchange_by_id = _index_by_id(db, ExchangeListing, {report.listing_id})
        elif report:
            marketplace_by_id = _index_by_id(db, MarketplaceProduct, {report.listing_id})
        item.report = _report_snapshot_from(report, reporter_names, exchange_by_id, marketplace_by_id)
    else:
        model = _ENTITY_MODEL.get(row.entity_type, MarketplaceProduct)
        listing = db.query(model).filter(model.id == row.entity_id).first()
        seller_names = _index_names(db, {listing.seller_user_id} if listing else set())
        item.listing = _listing_snapshot_from(row.entity_type, listing, seller_names)
    return item


def list_queue(
    db: Session,
    moderator: CurrentUser,
    *,
    queue_status: ModerationQueueStatus | None,
    entity_type: ModerationEntityType | None,
    page: PageParams,
) -> tuple[list[ModerationQueueItem], int]:
    query = db.query(ModerationQueue)
    if queue_status is not None:
        query = query.filter(ModerationQueue.status == queue_status.value)
    if entity_type is not None:
        query = query.filter(ModerationQueue.entity_type == entity_type.value)
    scope = _moderator_scope(db, moderator)
    if scope is not None:
        query = query.filter(ModerationQueue.location_id.in_(scope))

    total = query.count()
    rows = query.order_by(ModerationQueue.created_at.asc()).offset(page.offset).limit(page.page_size).all()

    location_ids = {r.location_id for r in rows if r.location_id}
    location_names = {
        loc_id: name
        for loc_id, name in db.query(Location.id, Location.name_bn).filter(Location.id.in_(location_ids)).all()
    } if location_ids else {}

    # Batch-fetch every listing/report this page references in one query per
    # model instead of 2-3 queries per row (was up to ~180 round-trips at
    # page_size=60 before this - see Section 19's "no N+1" rule).
    exchange_ids = {r.entity_id for r in rows if r.entity_type == ModerationEntityType.EXCHANGE_LISTING.value}
    marketplace_ids = {r.entity_id for r in rows if r.entity_type == ModerationEntityType.MARKETPLACE_PRODUCT.value}
    shop_ids = {r.entity_id for r in rows if r.entity_type == ModerationEntityType.SHOP.value}
    report_ids = {r.entity_id for r in rows if r.entity_type == ModerationEntityType.LISTING_REPORT.value}

    exchange_by_id = _index_by_id(db, ExchangeListing, exchange_ids)
    marketplace_by_id = _index_by_id(db, MarketplaceProduct, marketplace_ids)
    shop_by_id = _index_by_id(db, Shop, shop_ids)
    reports_by_id = _index_by_id(db, ListingReport, report_ids)

    # Reports point at a listing of their own - batch those in too, extending
    # the same dicts so a listing referenced both directly and via a report
    # is only ever fetched once.
    report_exchange_ids = {
        r.listing_id for r in reports_by_id.values() if r.listing_type == ListingType.EXCHANGE.value
    } - exchange_by_id.keys()
    report_marketplace_ids = {
        r.listing_id for r in reports_by_id.values() if r.listing_type != ListingType.EXCHANGE.value
    } - marketplace_by_id.keys()
    exchange_by_id.update(_index_by_id(db, ExchangeListing, report_exchange_ids))
    marketplace_by_id.update(_index_by_id(db, MarketplaceProduct, report_marketplace_ids))

    seller_ids = {
        listing.seller_user_id for listing in (*exchange_by_id.values(), *marketplace_by_id.values(), *shop_by_id.values())
    }
    reporter_ids = {r.reporter_user_id for r in reports_by_id.values()}
    user_names = _index_names(db, seller_ids | reporter_ids)

    items = []
    for row in rows:
        item = ModerationQueueItem(
            id=row.id,
            entity_type=ModerationEntityType(row.entity_type),
            entity_id=row.entity_id,
            location_id=row.location_id,
            location_name=location_names.get(row.location_id) if row.location_id else None,
            reason=row.reason,
            status=ModerationQueueStatus(row.status),
            created_at=row.created_at,
            reviewed_by=row.reviewed_by,
            reviewed_at=row.reviewed_at,
            review_note=row.review_note,
        )
        if row.entity_type == ModerationEntityType.LISTING_REPORT.value:
            item.report = _report_snapshot_from(
                reports_by_id.get(row.entity_id), user_names, exchange_by_id, marketplace_by_id
            )
        elif row.entity_type == ModerationEntityType.EXCHANGE_LISTING.value:
            item.listing = _listing_snapshot_from(row.entity_type, exchange_by_id.get(row.entity_id), user_names)
        elif row.entity_type == ModerationEntityType.SHOP.value:
            item.listing = _listing_snapshot_from(row.entity_type, shop_by_id.get(row.entity_id), user_names)
        else:
            item.listing = _listing_snapshot_from(row.entity_type, marketplace_by_id.get(row.entity_id), user_names)
        items.append(item)
    return items, total


def get_stats(db: Session, moderator: CurrentUser) -> ModerationStats:
    query = db.query(ModerationQueue)
    scope = _moderator_scope(db, moderator)
    if scope is not None:
        query = query.filter(ModerationQueue.location_id.in_(scope))
    counts = {s.value: query.filter(ModerationQueue.status == s.value).count() for s in ModerationQueueStatus}
    return ModerationStats(pending=counts["pending"], approved=counts["approved"], rejected=counts["rejected"])


# --- decisions -------------------------------------------------------------------


def review(
    db: Session,
    moderator: CurrentUser,
    queue_id: uuid.UUID,
    decision: ModerationDecision,
    note: str | None,
    favored_party: str | None = None,
) -> tuple[ModerationQueueItem, dict | None]:
    """Second tuple element is only populated for a CONTRACT_DISPUTE decision -
    `{employer_user_id, worker_user_id, contract_id, resolution}` for the
    router to push a `dispute_resolved` WS event to both parties; `None` for
    every other entity type."""
    row = db.query(ModerationQueue).filter(ModerationQueue.id == queue_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="queue item not found")
    if row.status != ModerationQueueStatus.PENDING.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this item was already reviewed")
    _assert_in_scope(db, moderator, row.location_id, row.entity_type)

    approved = decision is ModerationDecision.APPROVE
    seller_id: uuid.UUID | None = None
    dispute_notification: dict | None = None

    if row.entity_type == ModerationEntityType.CONTRACT_DISPUTE.value:
        if approved and favored_party not in ("employer", "worker"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="favored_party is required to approve a contract dispute",
            )
        dispute_notification = _apply_contract_dispute_decision(
            db, row.entity_id, decision, favored_party, moderator.uuid, note
        )
    elif row.entity_type == ModerationEntityType.LISTING_REPORT.value:
        seller_id = _apply_report_decision(db, row.entity_id, approved)
    else:
        seller_id = _apply_listing_decision(db, row.entity_type, row.entity_id, approved)

    row.status = ModerationQueueStatus.APPROVED.value if approved else ModerationQueueStatus.REJECTED.value
    row.reviewed_by = moderator.uuid
    row.reviewed_at = _now()
    row.review_note = note

    record_audit(
        db,
        actor_user_id=moderator.uuid,
        action=f"moderation.{decision.value}",
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        meta={"queue_id": str(row.id), "note": note},
    )
    if seller_id is not None:
        # SessionLocal runs with autoflush=False - push the status change first so
        # recompute's COUNT queries see it.
        db.flush()
        trust_service.recompute(db, seller_id)
    db.commit()
    db.refresh(row)
    return _to_item(db, row), dispute_notification


def _apply_contract_dispute_decision(
    db: Session,
    problem_id: uuid.UUID,
    decision: ModerationDecision,
    favored_party: str | None,
    moderator_id: uuid.UUID,
    note: str | None,
) -> dict | None:
    """REJECT -> dismissed, the contract goes back to ACTIVE (work continues).
    APPROVE -> the favored party's ruling ends the contract (a ruling that
    finds fault ends the working relationship); no automatic money movement -
    the platform doesn't handle real payments, `resolution_note` carries any
    such guidance as free text."""
    problem = db.query(ContractProblem).filter(ContractProblem.id == problem_id).first()
    if problem is None:
        return None
    contract = db.query(WorkContract).filter(WorkContract.id == problem.contract_id).first()
    if contract is None:
        return None

    problem.status = ContractProblemStatus.DISPUTE_RESOLVED.value
    problem.resolution_note = note
    problem.resolved_by = moderator_id
    problem.resolved_at = _now()

    if decision is ModerationDecision.REJECT:
        problem.resolution = ContractDisputeResolution.DISMISSED.value
        contract.status = ContractStatus.ACTIVE.value
    else:
        resolution = (
            ContractDisputeResolution.FAVOR_EMPLOYER
            if favored_party == "employer"
            else ContractDisputeResolution.FAVOR_WORKER
        )
        problem.resolution = resolution.value
        contract.status = ContractStatus.CANCELLED.value
        contract.cancelled_by_user_id = None  # system/admin action, not either party
        contract.cancelled_at = _now()
        contract.cancellation_reason = f"Admin dispute ruling: {resolution.value}"

    return {
        "employer_user_id": contract.employer_user_id,
        "worker_user_id": contract.worker_user_id,
        "contract_id": contract.id,
        "resolution": problem.resolution,
    }


def _apply_listing_decision(db: Session, entity_type: str, entity_id: uuid.UUID, approved: bool) -> uuid.UUID | None:
    if entity_type == ModerationEntityType.SHOP.value:
        listing = db.query(Shop).filter(Shop.id == entity_id).first()
    else:
        listing = _find_listing(
            db,
            ListingType.EXCHANGE.value if entity_type == ModerationEntityType.EXCHANGE_LISTING.value else ListingType.MARKETPLACE.value,
            entity_id,
        )
    if listing is None:
        return None
    listing.moderation_status = ModerationStatus.APPROVED.value if approved else ModerationStatus.REJECTED.value
    return listing.seller_user_id


def _apply_report_decision(db: Session, report_id: uuid.UUID, upheld: bool) -> uuid.UUID | None:
    report = db.query(ListingReport).filter(ListingReport.id == report_id).first()
    if report is None:
        return None
    report.status = ReportStatus.UPHELD.value if upheld else ReportStatus.DISMISSED.value
    listing = _find_listing(db, report.listing_type, report.listing_id)
    if listing is None:
        return None
    if upheld:
        # An upheld report takes the listing off the public site (Section 5.8 status=reported).
        listing.status = ListingStatus.REPORTED.value
    return listing.seller_user_id


def assert_can_moderate_location(db: Session, moderator: CurrentUser, location_id: uuid.UUID | None) -> None:
    """Exposed for other modules (e.g. a moderator editing a listing directly)."""
    _assert_in_scope(db, moderator, location_id)
