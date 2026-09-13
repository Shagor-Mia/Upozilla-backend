"""Section 17 Phase 4 RAG retrieval: tenant-scoped nearest-neighbour lookup
over `knowledge_chunks`. Kept separate from `app/modules/ai/service.py` so
the SQL/pgvector bits are testable independently of the LLM call."""

import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models.ai import KnowledgeChunk

# Cosine distance (0 = identical, 2 = opposite). Chunks past this are treated
# as irrelevant rather than passed to the model as "context".
MAX_DISTANCE = 0.5
DEFAULT_TOP_K = 6


def retrieve(
    db: Session,
    tenant_id: str | None,
    query_embedding: list[float],
    k: int = DEFAULT_TOP_K,
) -> list[tuple[KnowledgeChunk, float]]:
    """Returns up to `k` (chunk, distance) pairs, nearest first, scoped to
    this tenant (or untenanted rows - Section 1: nullable in Phase 1),
    filtered to a similarity floor so unrelated content is never handed to
    the model as grounding."""
    tenant_uuid = uuid.UUID(tenant_id) if tenant_id else None
    distance = KnowledgeChunk.embedding.cosine_distance(query_embedding).label("distance")
    rows = (
        db.query(KnowledgeChunk, distance)
        .filter(or_(KnowledgeChunk.tenant_id == tenant_uuid, KnowledgeChunk.tenant_id.is_(None)))
        .order_by(distance)
        .limit(k)
        .all()
    )
    return [(chunk, float(dist)) for chunk, dist in rows if dist <= MAX_DISTANCE]
