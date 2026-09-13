"""Section 17 Phase 4 RAG chatbot. Grounded-only: never falls through to the
model's general knowledge. Uses `httpx` directly, same style as
`translation.py`/`embeddings.py` - no OpenAI SDK for a couple of HTTP calls."""

import logging

import httpx
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core import ai_models, embeddings, rag, runtime_settings
from app.modules.ai.schemas import ChatResponse, SourceRef

logger = logging.getLogger(__name__)

_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"

REFUSAL = (
    "আমি শুধু এই উপজেলার নিজস্ব তথ্যের ভিত্তিতে উত্তর দিতে পারি, এবং এই প্রশ্নের উত্তর "
    "দেওয়ার মতো যথেষ্ট তথ্য আমার কাছে নেই। (I can only answer questions about this "
    "upazila's own information, and I don't have enough to answer that.)"
)


def _system_prompt(context: str) -> str:
    return (
        "You are a local information assistant for one upazila (sub-district) in Bangladesh. "
        "Answer ONLY using the CONTEXT below, which is this upazila's own data (places, "
        "government services, hospitals, markets, news, FAQs). Never use outside/general "
        "knowledge, even if you know the answer. If the CONTEXT does not contain enough to "
        "answer, say so plainly instead of guessing. Answer in the same language the question "
        "was asked in, briefly and concretely.\n\nCONTEXT:\n" + context
    )


async def _complete(system_prompt: str, message: str) -> str | None:
    api_key = runtime_settings.get("openai_api_key")
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                _CHAT_COMPLETIONS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": ai_models.chat_model(),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message},
                    ],
                    "temperature": 0.2,
                },
                timeout=30.0,
            )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip() or None
    except Exception:  # noqa: BLE001 - a chat failure must degrade to the refusal, not a 500
        logger.warning("chat completion failed", exc_info=True)
        return None


async def ask(db: Session, tenant_id: str | None, message: str) -> ChatResponse:
    query_embedding = await embeddings.embed_async(message)
    if query_embedding is None:
        # No key configured, or the embedding call failed - refuse rather
        # than answering from the model's general knowledge.
        return ChatResponse(answer=REFUSAL, sources=[])

    matches = await run_in_threadpool(rag.retrieve, db, tenant_id, query_embedding)
    if not matches:
        return ChatResponse(answer=REFUSAL, sources=[])

    context = "\n---\n".join(chunk.content for chunk, _distance in matches)
    answer = await _complete(_system_prompt(context), message)
    if answer is None:
        return ChatResponse(answer=REFUSAL, sources=[])

    sources = [
        SourceRef(source_type=chunk.source_type.value, source_id=chunk.source_id) for chunk, _distance in matches
    ]
    return ChatResponse(answer=answer, sources=sources)
