"""Tier -> OpenAI model resolution (Section 5.13/17 Phase 4 AI settings
upgrade). `ai_tier` is a plain runtime_settings lookup, not baked into a
decorator, so a tier change takes effect on the very next call - no restart.

Embeddings are NOT tiered: they stay fixed at `text-embedding-3-small`
regardless of tier, since the pgvector schema (Section 5.13) is locked to
1536 dimensions and switching embedding models would break retrieval."""

from app.core import runtime_settings

TIER_CHAT_MODELS = {
    "economy": "gpt-4o-mini",
    "standard": "gpt-4o",
    "premium": "gpt-4.1",
}
DEFAULT_TIER = "standard"


def chat_model() -> str:
    tier = runtime_settings.get("ai_tier") or DEFAULT_TIER
    return TIER_CHAT_MODELS.get(tier, TIER_CHAT_MODELS[DEFAULT_TIER])
