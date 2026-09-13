"""Phase 2 integration tests run against the compose Postgres/Redis (no separate
test DB yet). Every row they create is tracked and deleted on teardown so the
local dev data stays clean."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import or_

from app.core.database import SessionLocal
from app.core.rbac import Role
from app.core.redis_client import get_redis
from app.db.models import (
    AuditLog,
    Conversation,
    ExchangeListing,
    ListingFavorite,
    ListingReport,
    Location,
    LocationType,
    Market,
    MarketplaceCategory,
    MarketplaceProduct,
    Message,
    ModerationQueue,
    NewsSource,
    OtpCode,
    RefreshToken,
    Representative,
    SellerReview,
    ServiceCategory,
    Shop,
    ShopCategory,
    User,
    UserRole,
    UserTrustScore,
)
from app.main import app


class Actors:
    """Registers throw-away users through the real API and remembers them for cleanup."""

    def __init__(self, client: TestClient):
        self.client = client
        self.run_id = uuid.uuid4().hex[:8]
        self.user_ids: list[uuid.UUID] = []
        self.phones: list[str] = []
        self._phone_seq = 0

    def next_phone(self) -> str:
        # 017 + 8 digits, unique per run (BD mobile format expected by normalize_bd_phone)
        self._phone_seq += 1
        digits = f"{int(self.run_id, 16) % 10**6:06d}{self._phone_seq:02d}"
        phone = f"+88017{digits}"
        self.phones.append(phone)
        return phone

    def register_via_otp(self, full_name: str) -> tuple[dict, str]:
        phone = self.next_phone()
        requested = self.client.post("/api/v1/auth/otp/request", json={"phone": phone, "purpose": "register"})
        assert requested.status_code == 200, requested.text
        code = requested.json()["dev_code"]
        assert code, "console SMS gateway must echo the code in local env"
        verified = self.client.post(
            "/api/v1/auth/otp/verify",
            json={"phone": phone, "code": code, "purpose": "register", "full_name": full_name},
        )
        assert verified.status_code == 200, verified.text
        tokens = verified.json()
        me = self.client.get("/api/v1/auth/me", headers=self.auth(tokens))
        self.user_ids.append(uuid.UUID(me.json()["id"]))
        return tokens, phone

    def register_via_password(self, full_name: str) -> dict:
        email = f"{full_name.lower().replace(' ', '.')}.{self.run_id}@example.com"
        response = self.client.post(
            "/api/v1/auth/register",
            json={"full_name": full_name, "email": email, "password": "password123"},
        )
        assert response.status_code == 201, response.text
        tokens = response.json()
        me = self.client.get("/api/v1/auth/me", headers=self.auth(tokens))
        self.user_ids.append(uuid.UUID(me.json()["id"]))
        return tokens

    def promote(self, tokens: dict, role: Role) -> dict:
        """Sets the primary role directly in the DB, then re-logs in so the JWT carries it."""
        me = self.client.get("/api/v1/auth/me", headers=self.auth(tokens)).json()
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == uuid.UUID(me["id"])).first()
            user.role = role.value
            db.commit()
            phone = user.phone
        finally:
            db.close()
        requested = self.client.post("/api/v1/auth/otp/request", json={"phone": phone, "purpose": "login"})
        verified = self.client.post(
            "/api/v1/auth/otp/verify",
            json={"phone": phone, "code": requested.json()["dev_code"], "purpose": "login"},
        )
        assert verified.status_code == 200, verified.text
        return verified.json()

    @staticmethod
    def auth(tokens: dict) -> dict[str, str]:
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    def cleanup(self) -> None:
        db = SessionLocal()
        try:
            ids = self.user_ids
            if not ids:
                return
            exchange_ids = [r[0] for r in db.query(ExchangeListing.id).filter(ExchangeListing.seller_user_id.in_(ids))]
            product_ids = [r[0] for r in db.query(MarketplaceProduct.id).filter(MarketplaceProduct.seller_user_id.in_(ids))]
            shop_ids = [r[0] for r in db.query(Shop.id).filter(Shop.seller_user_id.in_(ids))]
            listing_ids = exchange_ids + product_ids + shop_ids
            conversation_ids = [
                r[0]
                for r in db.query(Conversation.id).filter(
                    or_(Conversation.buyer_id.in_(ids), Conversation.seller_id.in_(ids))
                )
            ]
            if conversation_ids:
                db.query(Message).filter(Message.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
                db.query(Conversation).filter(Conversation.id.in_(conversation_ids)).delete(synchronize_session=False)
            report_ids = [r[0] for r in db.query(ListingReport.id).filter(ListingReport.reporter_user_id.in_(ids))]
            if listing_ids or report_ids:
                db.query(ModerationQueue).filter(ModerationQueue.entity_id.in_(listing_ids + report_ids)).delete(
                    synchronize_session=False
                )
            db.query(ListingReport).filter(ListingReport.reporter_user_id.in_(ids)).delete(synchronize_session=False)
            db.query(ListingFavorite).filter(ListingFavorite.user_id.in_(ids)).delete(synchronize_session=False)
            db.query(SellerReview).filter(
                or_(SellerReview.seller_user_id.in_(ids), SellerReview.reviewer_user_id.in_(ids))
            ).delete(synchronize_session=False)
            db.query(ExchangeListing).filter(ExchangeListing.seller_user_id.in_(ids)).delete(synchronize_session=False)
            db.query(MarketplaceProduct).filter(MarketplaceProduct.seller_user_id.in_(ids)).delete(
                synchronize_session=False
            )
            db.query(Shop).filter(Shop.seller_user_id.in_(ids)).delete(synchronize_session=False)
            db.query(Representative).filter(Representative.user_id.in_(ids)).delete(synchronize_session=False)
            db.query(UserTrustScore).filter(UserTrustScore.user_id.in_(ids)).delete(synchronize_session=False)
            db.query(AuditLog).filter(AuditLog.actor_user_id.in_(ids)).delete(synchronize_session=False)
            db.query(UserRole).filter(UserRole.user_id.in_(ids)).delete(synchronize_session=False)
            db.query(RefreshToken).filter(RefreshToken.user_id.in_(ids)).delete(synchronize_session=False)
            if self.phones:
                db.query(OtpCode).filter(OtpCode.phone.in_(self.phones)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


@pytest.fixture(scope="module", autouse=True)
def reset_test_rate_limits() -> None:
    """Every test user registers via OTP from the TestClient's fixed IP, sharing one
    `otp:req:ip:testclient` bucket across every purpose (register/login/verify_phone -
    app/modules/auth/otp_service.py). With enough test modules that adds up past the
    per-IP OTP limit (Section 14.1), so reset it before each module gets its own budget;
    per-phone counters are unique per run already."""
    try:
        get_redis().delete("otp:req:ip:testclient")
    except Exception:  # noqa: BLE001 - the limiter itself fails open without Redis
        pass


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def actors(client: TestClient) -> Iterator[Actors]:
    registry = Actors(client)
    yield registry
    registry.cleanup()


@pytest.fixture(scope="module")
def reference_ids() -> dict[str, str]:
    db = SessionLocal()
    try:
        upazila = db.query(Location).filter(Location.type == LocationType.UPAZILA).first()
        union = db.query(Location).filter(Location.type == LocationType.UNION).first()
        category = db.query(MarketplaceCategory).order_by(MarketplaceCategory.sort_order).first()
        market = db.query(Market).first()
        shop_category = db.query(ShopCategory).order_by(ShopCategory.sort_order).first()
        service_category = db.query(ServiceCategory).first()
        news_source = db.query(NewsSource).first()
        assert upazila and union and category, "run seed_homna + seed_marketplace_categories first"
        assert market, "run seed_placeholder_content (or equivalent) to seed a market first"
        assert shop_category, "run seed_shop_categories first"
        assert service_category, "run seed_content_taxonomies first"
        assert news_source, "run seed_placeholder_content (or equivalent) to seed a news source first"
        return {
            "location_id": str(upazila.id),
            "union_id": str(union.id),
            "category_id": str(category.id),
            "market_id": str(market.id),
            "shop_category_id": str(shop_category.id),
            "service_category_id": str(service_category.id),
            "news_source_id": str(news_source.id),
        }
    finally:
        db.close()
