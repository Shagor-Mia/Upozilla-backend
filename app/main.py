from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.ws_manager import manager as ws_manager
from app.modules.admin.router import router as admin_router
from app.modules.ai.router import router as ai_router
from app.modules.auth.router import router as auth_router
from app.modules.businesses.router import router as businesses_router
from app.modules.contracts.router import router as contracts_router
from app.modules.exchange.router import router as exchange_router
from app.modules.faqs.router import router as faqs_router
from app.modules.government_services.router import router as government_services_router
from app.modules.hospitals.router import router as hospitals_router
from app.modules.locations.router import router as locations_router
from app.modules.marketplace.router import router as marketplace_router
from app.modules.markets.router import router as markets_router
from app.modules.messaging.router import router as messaging_router
from app.modules.messaging.router import ws_router as messaging_ws_router
from app.modules.meta.router import router as meta_router
from app.modules.moderation.router import router as moderation_router
from app.modules.news.router import router as news_router
from app.modules.places.router import router as places_router
from app.modules.recommendations.router import router as recommendations_router
from app.modules.representatives.router import router as representatives_router
from app.modules.sellers.router import router as sellers_router
from app.modules.settings.router import admin_router as settings_admin_router
from app.modules.settings.router import router as settings_router
from app.modules.shops.router import router as shops_router
from app.modules.uploads.router import router as uploads_router
from app.modules.users.router import router as users_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Section 19.2: Redis pub/sub fan-out so chat works across API instances.
    await ws_manager.start()
    try:
        yield
    finally:
        await ws_manager.stop()


app = FastAPI(
    title="Upazila Digital Ecosystem API",
    version="0.3.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_v1 = settings.API_V1_PREFIX
app.include_router(meta_router, prefix=api_v1)
app.include_router(auth_router, prefix=api_v1)
app.include_router(users_router, prefix=api_v1)
app.include_router(locations_router, prefix=api_v1)
app.include_router(places_router, prefix=api_v1)
app.include_router(government_services_router, prefix=api_v1)
app.include_router(hospitals_router, prefix=api_v1)
app.include_router(markets_router, prefix=api_v1)
app.include_router(shops_router, prefix=api_v1)
app.include_router(representatives_router, prefix=api_v1)
app.include_router(businesses_router, prefix=api_v1)
app.include_router(news_router, prefix=api_v1)
app.include_router(faqs_router, prefix=api_v1)
# Phase 2 - Marketplace & Exchange (Section 17)
app.include_router(marketplace_router, prefix=api_v1)
app.include_router(exchange_router, prefix=api_v1)
app.include_router(contracts_router, prefix=api_v1)
app.include_router(sellers_router, prefix=api_v1)
app.include_router(messaging_router, prefix=api_v1)
app.include_router(messaging_ws_router, prefix=api_v1)
app.include_router(moderation_router, prefix=api_v1)
app.include_router(settings_router, prefix=api_v1)
app.include_router(settings_admin_router, prefix=api_v1)
app.include_router(admin_router, prefix=api_v1)
app.include_router(ai_router, prefix=api_v1)
app.include_router(recommendations_router, prefix=api_v1)
app.include_router(uploads_router, prefix=api_v1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
