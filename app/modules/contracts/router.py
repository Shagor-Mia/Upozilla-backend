import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, get_locale, require_phone_verified
from app.core.rate_limit import rate_limit_by_user
from app.core.ws_manager import manager
from app.db.models.contract import ContractStatus
from app.modules.contracts import disputes, service
from app.modules.contracts.schemas import (
    ContractCancelBody,
    ContractCreate,
    ContractPaymentCreate,
    ContractPaymentResponse,
    ContractProblemCreate,
    ContractProblemResponse,
    ContractProgressCreate,
    ContractProgressResponse,
    ContractRejectBody,
    ContractResponse,
)

router = APIRouter(prefix="/contracts", tags=["contracts"])


async def _notify(user_id: uuid.UUID | None, event: str, contract_response: ContractResponse) -> None:
    """WS notify-after-commit, exact pattern of `messaging/router.py::send_message`.
    A `None` recipient (the other party's account was deleted, SET NULL) is a
    silent no-op - there's no one left to notify."""
    if user_id is None:
        return
    await manager.send_to_user(
        str(user_id),
        {
            "type": "contract_update",
            "event": event,
            "contract_id": str(contract_response.id),
            "contract": contract_response.model_dump(mode="json"),
        },
    )


@router.post(
    "",
    response_model=ContractResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_by_user("contracts-create", settings.CONTRACTS_PER_USER_PER_MINUTE, 60))],
)
def create_contract(
    payload: ContractCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    employer: CurrentUser = Depends(require_phone_verified),
) -> ContractResponse:
    contract = service.create(db, employer, payload, background_tasks)
    return service.to_response(db, contract, locale)


@router.get("/mine", response_model=list[ContractResponse])
def my_contracts(
    role: str | None = None,
    status: ContractStatus | None = None,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ContractResponse]:
    rows = service.list_mine(db, current_user, role, status)
    return service.to_responses(db, rows, locale)


@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: uuid.UUID,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    viewer: CurrentUser = Depends(get_current_user),
) -> ContractResponse:
    return service.to_response(db, service.get_one(db, contract_id, viewer), locale)


@router.post("/{contract_id}/accept", response_model=ContractResponse)
async def accept_contract(
    contract_id: uuid.UUID,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    worker: CurrentUser = Depends(require_phone_verified),
) -> ContractResponse:
    contract = await run_in_threadpool(service.accept, db, worker, contract_id)
    response = service.to_response(db, contract, locale)
    await _notify(contract.employer_user_id, "accepted", response)
    return response


@router.post("/{contract_id}/reject", response_model=ContractResponse)
def reject_contract(
    contract_id: uuid.UUID,
    payload: ContractRejectBody,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    worker: CurrentUser = Depends(require_phone_verified),
) -> ContractResponse:
    contract = service.reject(db, worker, contract_id, payload.reason)
    return service.to_response(db, contract, locale)


@router.post("/{contract_id}/cancel", response_model=ContractResponse)
def cancel_contract(
    contract_id: uuid.UUID,
    payload: ContractCancelBody,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_phone_verified),
) -> ContractResponse:
    contract = service.cancel(db, actor, contract_id, payload.reason)
    return service.to_response(db, contract, locale)


@router.post("/{contract_id}/complete", response_model=ContractResponse)
def complete_contract(
    contract_id: uuid.UUID,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_phone_verified),
) -> ContractResponse:
    contract = service.complete(db, actor, contract_id)
    return service.to_response(db, contract, locale)


# --- progress -------------------------------------------------------------------------


@router.get("/{contract_id}/progress", response_model=list[ContractProgressResponse])
def list_progress(
    contract_id: uuid.UUID,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    viewer: CurrentUser = Depends(get_current_user),
) -> list[ContractProgressResponse]:
    return service.list_progress(db, contract_id, viewer, locale)


@router.post(
    "/{contract_id}/progress",
    response_model=ContractProgressResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_by_user("contract-progress", settings.CONTRACT_ENTRIES_PER_USER_PER_MINUTE, 60))],
)
def add_progress(
    contract_id: uuid.UUID,
    payload: ContractProgressCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_phone_verified),
) -> ContractProgressResponse:
    return service.add_progress(db, actor, contract_id, payload, background_tasks, locale)


# --- payments ---------------------------------------------------------------------------


@router.get("/{contract_id}/payments", response_model=list[ContractPaymentResponse])
def list_payments(
    contract_id: uuid.UUID,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    viewer: CurrentUser = Depends(get_current_user),
) -> list[ContractPaymentResponse]:
    return service.list_payments(db, contract_id, viewer, locale)


@router.post(
    "/{contract_id}/payments",
    response_model=ContractPaymentResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_by_user("contract-payments", settings.CONTRACT_ENTRIES_PER_USER_PER_MINUTE, 60))],
)
async def add_payment(
    contract_id: uuid.UUID,
    payload: ContractPaymentCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_phone_verified),
) -> ContractPaymentResponse:
    response, recipient_id, contract_response = await run_in_threadpool(
        service.add_payment, db, actor, contract_id, payload, background_tasks, locale
    )
    await _notify(recipient_id, "payment_logged", contract_response)
    return response


@router.post("/{contract_id}/payments/{payment_id}/confirm", response_model=ContractPaymentResponse)
def confirm_payment(
    contract_id: uuid.UUID,
    payment_id: uuid.UUID,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_phone_verified),
) -> ContractPaymentResponse:
    return service.confirm_payment(db, actor, contract_id, payment_id, locale)


# --- problems ---------------------------------------------------------------------------


@router.get("/{contract_id}/problems", response_model=list[ContractProblemResponse])
def list_problems(
    contract_id: uuid.UUID,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    viewer: CurrentUser = Depends(get_current_user),
) -> list[ContractProblemResponse]:
    return service.list_problems(db, contract_id, viewer, locale)


@router.post(
    "/{contract_id}/problems",
    response_model=ContractProblemResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_by_user("contract-problems", settings.CONTRACT_ENTRIES_PER_USER_PER_MINUTE, 60))],
)
async def add_problem(
    contract_id: uuid.UUID,
    payload: ContractProblemCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_phone_verified),
) -> ContractProblemResponse:
    response, recipient_id, contract_response = await run_in_threadpool(
        service.add_problem, db, actor, contract_id, payload, background_tasks, locale
    )
    await _notify(recipient_id, "problem_reported", contract_response)
    return response


@router.post("/{contract_id}/problems/{problem_id}/resolve", response_model=ContractProblemResponse)
def resolve_problem(
    contract_id: uuid.UUID,
    problem_id: uuid.UUID,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_phone_verified),
) -> ContractProblemResponse:
    return service.resolve_problem(db, actor, contract_id, problem_id, locale)


@router.post("/{contract_id}/problems/{problem_id}/escalate", response_model=ContractProblemResponse)
def escalate_problem(
    contract_id: uuid.UUID,
    problem_id: uuid.UUID,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_phone_verified),
) -> ContractProblemResponse:
    return disputes.escalate_problem(db, actor, contract_id, problem_id, locale)
