import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser
from app.core.tenant import resolve_tenant_id
from app.db.models import ContractProblemStatus, ContractStatus
from app.modules.contracts import service
from app.modules.contracts.schemas import ContractProblemResponse
from app.modules.moderation import service as moderation_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def escalate_problem(
    db: Session, actor: CurrentUser, contract_id: uuid.UUID, problem_id: uuid.UUID, locale: str
) -> ContractProblemResponse:
    """Mirrors `exchange/reports.py::create_report` -> `moderation_service.enqueue_report`:
    an unresolved problem becomes a queue entry for an admin to rule on, and
    the contract itself flips to DISPUTED while the ruling is pending."""
    contract = service.get_contract(db, contract_id)
    service.require_party(contract, actor.uuid)
    problem = service.get_problem(db, contract_id, problem_id)
    if problem.status != ContractProblemStatus.OPEN.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this problem is not open")

    problem.status = ContractProblemStatus.ESCALATED.value
    problem.escalated_at = _now()
    contract.status = ContractStatus.DISPUTED.value
    db.flush()
    moderation_service.enqueue_contract_dispute(db, problem=problem, tenant_id=resolve_tenant_id(db, actor))
    db.commit()
    db.refresh(problem)
    name = service.user_names(db, {problem.raised_by_user_id}).get(problem.raised_by_user_id)
    return service.problem_response(problem, locale, name)
