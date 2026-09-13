import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core import translation
from app.core.dependencies import CurrentUser
from app.core.i18n import DEFAULT_LOCALE, localized_value
from app.core.rbac import Permission
from app.core.tenant import resolve_tenant_id
from app.db.models import (
    ContractPayment,
    ContractPaymentStatus,
    ContractProblem,
    ContractProblemStatus,
    ContractProgressEntry,
    ContractStatus,
    User,
    WorkContract,
)
from app.modules.contracts.schemas import (
    ContractCreate,
    ContractPaymentCreate,
    ContractPaymentResponse,
    ContractProblemCreate,
    ContractProblemResponse,
    ContractProgressCreate,
    ContractProgressResponse,
    ContractResponse,
)

# A ruling ends the working relationship; peer-cancel is only allowed while
# the work hasn't already concluded one way or another.
CANCELLABLE_STATUSES = {ContractStatus.PENDING, ContractStatus.ACTIVE}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- shared lookups (also used by disputes.py) --------------------------------------


def get_contract(db: Session, contract_id: uuid.UUID) -> WorkContract:
    contract = db.query(WorkContract).filter(WorkContract.id == contract_id).first()
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")
    return contract


def require_party(contract: WorkContract, user_id: uuid.UUID) -> None:
    if user_id not in {contract.employer_user_id, contract.worker_user_id}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="you are not a party to this contract")


def get_problem(db: Session, contract_id: uuid.UUID, problem_id: uuid.UUID) -> ContractProblem:
    problem = (
        db.query(ContractProblem)
        .filter(ContractProblem.id == problem_id, ContractProblem.contract_id == contract_id)
        .first()
    )
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="problem not found")
    return problem


def other_party(contract: WorkContract, actor_id: uuid.UUID) -> uuid.UUID | None:
    return contract.worker_user_id if actor_id == contract.employer_user_id else contract.employer_user_id


# --- response building ---------------------------------------------------------------


def user_names(db: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    real_ids = {i for i in ids if i is not None}
    if not real_ids:
        return {}
    return {uid: name for uid, name in db.query(User.id, User.full_name).filter(User.id.in_(real_ids)).all()}


def to_response(db: Session, contract: WorkContract, locale: str = DEFAULT_LOCALE) -> ContractResponse:
    names = user_names(db, {contract.employer_user_id, contract.worker_user_id})
    return ContractResponse.from_model(
        contract, locale, names.get(contract.employer_user_id), names.get(contract.worker_user_id)
    )


def to_responses(db: Session, contracts: list[WorkContract], locale: str = DEFAULT_LOCALE) -> list[ContractResponse]:
    if not contracts:
        return []
    ids: set[uuid.UUID | None] = set()
    for c in contracts:
        ids.add(c.employer_user_id)
        ids.add(c.worker_user_id)
    names = user_names(db, ids)
    return [
        ContractResponse.from_model(c, locale, names.get(c.employer_user_id), names.get(c.worker_user_id))
        for c in contracts
    ]


def get_response(db: Session, contract_id: uuid.UUID, locale: str = DEFAULT_LOCALE) -> ContractResponse:
    """Cross-module convenience (used by `moderation/router.py` to build the
    `dispute_resolved` WS payload) - fetches and shapes a single contract."""
    return to_response(db, get_contract(db, contract_id), locale)


def progress_response(entry: ContractProgressEntry, locale: str, name: str | None) -> ContractProgressResponse:
    return ContractProgressResponse(
        id=entry.id,
        contract_id=entry.contract_id,
        created_by_user_id=entry.created_by_user_id,
        created_by_name=name,
        note=localized_value(entry.note_bn, entry.note_en, entry.note_ar, locale),
        percent_complete=entry.percent_complete,
        images=entry.images or [],
        created_at=entry.created_at,
    )


def payment_response(
    payment: ContractPayment, locale: str, name: str | None, confirmed_by_name: str | None = None
) -> ContractPaymentResponse:
    return ContractPaymentResponse(
        id=payment.id,
        contract_id=payment.contract_id,
        logged_by_user_id=payment.logged_by_user_id,
        logged_by_name=name,
        amount=float(payment.amount),
        method=payment.method,
        note=localized_value(payment.note_bn, payment.note_en, payment.note_ar, locale) if payment.note_bn else None,
        proof_images=payment.proof_images or [],
        paid_at=payment.paid_at,
        status=payment.status,
        confirmed_by_user_id=payment.confirmed_by_user_id,
        confirmed_by_name=confirmed_by_name,
        confirmed_at=payment.confirmed_at,
        created_at=payment.created_at,
    )


def problem_response(
    problem: ContractProblem, locale: str, name: str | None, resolved_by_name: str | None = None
) -> ContractProblemResponse:
    return ContractProblemResponse(
        id=problem.id,
        contract_id=problem.contract_id,
        raised_by_user_id=problem.raised_by_user_id,
        raised_by_name=name,
        category=problem.category,
        description=localized_value(problem.description_bn, problem.description_en, problem.description_ar, locale),
        images=problem.images or [],
        status=problem.status,
        escalated_at=problem.escalated_at,
        resolution=problem.resolution,
        resolution_note=problem.resolution_note,
        resolved_by_user_id=problem.resolved_by,
        resolved_by_name=resolved_by_name,
        resolved_at=problem.resolved_at,
        created_at=problem.created_at,
    )


# --- contract lifecycle ----------------------------------------------------------------


def create(db: Session, employer: CurrentUser, payload: ContractCreate, background_tasks: BackgroundTasks) -> WorkContract:
    if payload.worker_user_id == employer.uuid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="you cannot create a contract with yourself")
    worker = db.query(User).filter(User.id == payload.worker_user_id, User.status == "active").first()
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="worker not found")

    contract = WorkContract(
        tenant_id=resolve_tenant_id(db, employer),
        employer_user_id=employer.uuid,
        worker_user_id=payload.worker_user_id,
        title_bn=payload.title,
        description_bn=payload.description,
        payment_amount=payload.payment_amount,
        payment_type=payload.payment_type.value,
        currency=payload.currency,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reference_images=payload.reference_images,
        status=ContractStatus.PENDING.value,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    translation.schedule_translations(background_tasks, WorkContract, contract.id, ["title", "description"])
    return contract


def list_mine(db: Session, current_user: CurrentUser, role: str | None, status_filter: ContractStatus | None) -> list[WorkContract]:
    query = db.query(WorkContract)
    if role == "employer":
        query = query.filter(WorkContract.employer_user_id == current_user.uuid)
    elif role == "worker":
        query = query.filter(WorkContract.worker_user_id == current_user.uuid)
    else:
        query = query.filter(
            or_(WorkContract.employer_user_id == current_user.uuid, WorkContract.worker_user_id == current_user.uuid)
        )
    if status_filter is not None:
        query = query.filter(WorkContract.status == status_filter.value)
    return query.order_by(WorkContract.created_at.desc()).all()


def get_one(db: Session, contract_id: uuid.UUID, viewer: CurrentUser) -> WorkContract:
    contract = get_contract(db, contract_id)
    is_party = viewer.uuid in {contract.employer_user_id, contract.worker_user_id}
    if not is_party and not viewer.has_permission(Permission.MARKETPLACE_MODERATE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="you are not a party to this contract")
    return contract


def accept(db: Session, worker: CurrentUser, contract_id: uuid.UUID) -> WorkContract:
    contract = get_contract(db, contract_id)
    if contract.worker_user_id != worker.uuid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only the named worker can accept this contract")
    if contract.status != ContractStatus.PENDING.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this contract is no longer pending")
    contract.worker_accepted_at = _now()
    contract.status = ContractStatus.ACTIVE.value
    db.commit()
    db.refresh(contract)
    return contract


def reject(db: Session, worker: CurrentUser, contract_id: uuid.UUID, reason: str | None) -> WorkContract:
    contract = get_contract(db, contract_id)
    if contract.worker_user_id != worker.uuid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only the named worker can reject this contract")
    if contract.status != ContractStatus.PENDING.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this contract is no longer pending")
    contract.status = ContractStatus.REJECTED.value
    contract.cancellation_reason = reason
    db.commit()
    db.refresh(contract)
    return contract


def cancel(db: Session, actor: CurrentUser, contract_id: uuid.UUID, reason: str) -> WorkContract:
    contract = get_contract(db, contract_id)
    require_party(contract, actor.uuid)
    if ContractStatus(contract.status) not in CANCELLABLE_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this contract can no longer be cancelled")
    contract.status = ContractStatus.CANCELLED.value
    contract.cancelled_by_user_id = actor.uuid
    contract.cancelled_at = _now()
    contract.cancellation_reason = reason
    db.commit()
    db.refresh(contract)
    return contract


def complete(db: Session, actor: CurrentUser, contract_id: uuid.UUID) -> WorkContract:
    contract = get_contract(db, contract_id)
    require_party(contract, actor.uuid)
    if contract.status != ContractStatus.ACTIVE.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this contract is not active")
    now = _now()
    if actor.uuid == contract.employer_user_id:
        contract.employer_completion_confirmed_at = now
    if actor.uuid == contract.worker_user_id:
        contract.worker_completion_confirmed_at = now
    if contract.employer_completion_confirmed_at and contract.worker_completion_confirmed_at:
        contract.status = ContractStatus.COMPLETED.value
    db.commit()
    db.refresh(contract)
    return contract


# --- progress ---------------------------------------------------------------------------


def list_progress(db: Session, contract_id: uuid.UUID, viewer: CurrentUser, locale: str) -> list[ContractProgressResponse]:
    contract = get_contract(db, contract_id)
    require_party(contract, viewer.uuid)
    rows = (
        db.query(ContractProgressEntry)
        .filter(ContractProgressEntry.contract_id == contract_id)
        .order_by(ContractProgressEntry.created_at.desc())
        .all()
    )
    names = user_names(db, {r.created_by_user_id for r in rows})
    return [progress_response(r, locale, names.get(r.created_by_user_id)) for r in rows]


def add_progress(
    db: Session,
    actor: CurrentUser,
    contract_id: uuid.UUID,
    payload: ContractProgressCreate,
    background_tasks: BackgroundTasks,
    locale: str,
) -> ContractProgressResponse:
    contract = get_contract(db, contract_id)
    require_party(contract, actor.uuid)
    if contract.status != ContractStatus.ACTIVE.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this contract is not active")
    entry = ContractProgressEntry(
        tenant_id=contract.tenant_id,
        contract_id=contract.id,
        created_by_user_id=actor.uuid,
        note_bn=payload.note,
        percent_complete=payload.percent_complete,
        images=payload.images,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    translation.schedule_translations(background_tasks, ContractProgressEntry, entry.id, ["note"])
    name = user_names(db, {actor.uuid}).get(actor.uuid)
    return progress_response(entry, locale, name)


# --- payments ---------------------------------------------------------------------------


def list_payments(db: Session, contract_id: uuid.UUID, viewer: CurrentUser, locale: str) -> list[ContractPaymentResponse]:
    contract = get_contract(db, contract_id)
    require_party(contract, viewer.uuid)
    rows = (
        db.query(ContractPayment)
        .filter(ContractPayment.contract_id == contract_id)
        .order_by(ContractPayment.created_at.desc())
        .all()
    )
    names = user_names(db, {r.logged_by_user_id for r in rows} | {r.confirmed_by_user_id for r in rows})
    return [
        payment_response(r, locale, names.get(r.logged_by_user_id), names.get(r.confirmed_by_user_id))
        for r in rows
    ]


def add_payment(
    db: Session,
    actor: CurrentUser,
    contract_id: uuid.UUID,
    payload: ContractPaymentCreate,
    background_tasks: BackgroundTasks,
    locale: str,
) -> tuple[ContractPaymentResponse, uuid.UUID | None, ContractResponse]:
    """Returns the payment response, the other party's user id (for the
    router's WS notify), and the contract response (embedded in that WS
    frame per the `contract_update` payload shape)."""
    contract = get_contract(db, contract_id)
    require_party(contract, actor.uuid)
    payment = ContractPayment(
        tenant_id=contract.tenant_id,
        contract_id=contract.id,
        logged_by_user_id=actor.uuid,
        amount=payload.amount,
        method=payload.method.value,
        note_bn=payload.note,
        proof_images=payload.proof_images,
        status=ContractPaymentStatus.PENDING_CONFIRMATION.value,
    )
    if payload.paid_at is not None:
        payment.paid_at = payload.paid_at
    db.add(payment)
    db.commit()
    db.refresh(payment)
    translation.schedule_translations(background_tasks, ContractPayment, payment.id, ["note"])
    name = user_names(db, {actor.uuid}).get(actor.uuid)
    return payment_response(payment, locale, name), other_party(contract, actor.uuid), to_response(db, contract, locale)


def confirm_payment(
    db: Session, actor: CurrentUser, contract_id: uuid.UUID, payment_id: uuid.UUID, locale: str
) -> ContractPaymentResponse:
    contract = get_contract(db, contract_id)
    require_party(contract, actor.uuid)
    payment = (
        db.query(ContractPayment)
        .filter(ContractPayment.id == payment_id, ContractPayment.contract_id == contract_id)
        .first()
    )
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
    if payment.logged_by_user_id == actor.uuid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="you cannot confirm your own payment entry")
    if payment.status != ContractPaymentStatus.PENDING_CONFIRMATION.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this payment was already confirmed")
    payment.status = ContractPaymentStatus.CONFIRMED.value
    payment.confirmed_by_user_id = actor.uuid
    payment.confirmed_at = _now()
    db.commit()
    db.refresh(payment)
    names = user_names(db, {payment.logged_by_user_id, actor.uuid})
    return payment_response(payment, locale, names.get(payment.logged_by_user_id), names.get(actor.uuid))


# --- problems ---------------------------------------------------------------------------


def list_problems(db: Session, contract_id: uuid.UUID, viewer: CurrentUser, locale: str) -> list[ContractProblemResponse]:
    contract = get_contract(db, contract_id)
    require_party(contract, viewer.uuid)
    rows = (
        db.query(ContractProblem)
        .filter(ContractProblem.contract_id == contract_id)
        .order_by(ContractProblem.created_at.desc())
        .all()
    )
    names = user_names(db, {r.raised_by_user_id for r in rows} | {r.resolved_by for r in rows})
    return [
        problem_response(r, locale, names.get(r.raised_by_user_id), names.get(r.resolved_by)) for r in rows
    ]


def add_problem(
    db: Session,
    actor: CurrentUser,
    contract_id: uuid.UUID,
    payload: ContractProblemCreate,
    background_tasks: BackgroundTasks,
    locale: str,
) -> tuple[ContractProblemResponse, uuid.UUID | None, ContractResponse]:
    """Same three-part return shape as `add_payment` - see its docstring."""
    contract = get_contract(db, contract_id)
    require_party(contract, actor.uuid)
    problem = ContractProblem(
        tenant_id=contract.tenant_id,
        contract_id=contract.id,
        raised_by_user_id=actor.uuid,
        category=payload.category.value,
        description_bn=payload.description,
        images=payload.images,
        status=ContractProblemStatus.OPEN.value,
    )
    db.add(problem)
    db.commit()
    db.refresh(problem)
    translation.schedule_translations(background_tasks, ContractProblem, problem.id, ["description"])
    name = user_names(db, {actor.uuid}).get(actor.uuid)
    return problem_response(problem, locale, name), other_party(contract, actor.uuid), to_response(db, contract, locale)


def resolve_problem(
    db: Session, actor: CurrentUser, contract_id: uuid.UUID, problem_id: uuid.UUID, locale: str
) -> ContractProblemResponse:
    contract = get_contract(db, contract_id)
    require_party(contract, actor.uuid)
    problem = get_problem(db, contract_id, problem_id)
    if problem.status != ContractProblemStatus.OPEN.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this problem is not open")
    problem.status = ContractProblemStatus.RESOLVED.value
    problem.resolved_by = actor.uuid
    problem.resolved_at = _now()
    db.commit()
    db.refresh(problem)
    names = user_names(db, {problem.raised_by_user_id, actor.uuid})
    return problem_response(problem, locale, names.get(problem.raised_by_user_id), names.get(actor.uuid))
