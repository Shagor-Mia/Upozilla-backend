"""Coverage for the polymorphic listing_id/entity_id references (favorites,
reports, seller_reviews, conversations, moderation_queue) that have no real
FK - only a (type, id) pair the app resolves at runtime. Two layers:

1. HTTP-level: every write path already rejects a nonexistent listing_id via
   app/modules/exchange/lookup.py's get_public_listing / sellers/service.py's
   _listing_belongs_to_seller - this locks that behavior into the regression
   suite (it wasn't covered before).
2. DB-level: migration b5c6d7e8f9a0 added trigger functions that reject a bad
   (type, id) pair even when the app-layer helper is bypassed entirely - the
   actual backstop these tests are here to prove exists.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from app.core.database import SessionLocal
from app.db.models import (
    Conversation,
    ListingFavorite,
    ListingReport,
    ModerationEntityType,
    ModerationQueue,
    ModerationQueueStatus,
    ReportStatus,
    SellerReview,
)
from tests.conftest import Actors


def test_favorite_report_conversation_review_reject_nonexistent_listing(
    client: TestClient, actors: Actors, reference_ids: dict[str, str]
) -> None:
    buyer_tokens, _ = actors.register_via_otp("Integrity Buyer")
    seller_tokens, _ = actors.register_via_otp("Integrity Seller")
    seller_id = actors.client.get("/api/v1/auth/me", headers=actors.auth(seller_tokens)).json()["id"]
    bogus_listing_id = str(uuid.uuid4())

    fav = client.put(f"/api/v1/exchange/favorites/exchange/{bogus_listing_id}", headers=actors.auth(buyer_tokens))
    assert fav.status_code == 404, fav.text

    report = client.post(
        f"/api/v1/exchange/reports/exchange/{bogus_listing_id}",
        json={"reason": "spam", "details": "bogus"},
        headers=actors.auth(buyer_tokens),
    )
    assert report.status_code == 404, report.text

    conversation = client.post(
        "/api/v1/conversations",
        json={"listing_type": "exchange", "listing_id": bogus_listing_id},
        headers=actors.auth(buyer_tokens),
    )
    assert conversation.status_code == 404, conversation.text

    review = client.post(
        f"/api/v1/sellers/{seller_id}/reviews",
        json={"rating": 5, "comment": "n/a", "listing_type": "exchange", "listing_id": bogus_listing_id},
        headers=actors.auth(buyer_tokens),
    )
    assert review.status_code == 404, review.text


def _expect_bad_ref_rejected(db, obj) -> None:
    db.add(obj)
    with pytest.raises(DBAPIError, match="does not exist"):
        db.commit()
    db.rollback()


def test_db_trigger_rejects_bad_listing_ref_bypassing_app_layer(
    actors: Actors, reference_ids: dict[str, str]
) -> None:
    """Simulates a bug that skips get_public_listing entirely - the app-layer
    checks in test above never run, so only the trigger stands between this
    insert and a dangling reference."""
    buyer_tokens, _ = actors.register_via_otp("Trigger Bypass Buyer")
    seller_tokens, _ = actors.register_via_otp("Trigger Bypass Seller")
    buyer_id = uuid.UUID(actors.client.get("/api/v1/auth/me", headers=actors.auth(buyer_tokens)).json()["id"])
    seller_id = uuid.UUID(actors.client.get("/api/v1/auth/me", headers=actors.auth(seller_tokens)).json()["id"])
    bogus_id = uuid.uuid4()

    db = SessionLocal()
    try:
        _expect_bad_ref_rejected(
            db, ListingFavorite(user_id=buyer_id, listing_type="exchange", listing_id=bogus_id)
        )
        _expect_bad_ref_rejected(
            db,
            ListingReport(
                tenant_id=None, listing_type="exchange", listing_id=bogus_id,
                reporter_user_id=buyer_id, reason="spam", status=ReportStatus.OPEN.value,
            ),
        )
        _expect_bad_ref_rejected(
            db,
            SellerReview(
                tenant_id=None, seller_user_id=seller_id, reviewer_user_id=buyer_id,
                listing_type="exchange", listing_id=bogus_id, rating=3,
            ),
        )
        _expect_bad_ref_rejected(
            db,
            Conversation(
                tenant_id=None, listing_type="exchange", listing_id=bogus_id,
                buyer_id=buyer_id, seller_id=seller_id,
            ),
        )
        _expect_bad_ref_rejected(
            db,
            ModerationQueue(
                tenant_id=None, entity_type=ModerationEntityType.EXCHANGE_LISTING.value, entity_id=bogus_id,
                location_id=uuid.UUID(reference_ids["location_id"]), reason="test",
                status=ModerationQueueStatus.PENDING.value,
            ),
        )

        # a review with listing_id=NULL (a general, non-listing review) is unaffected -
        # the trigger only fires when listing_id is actually set.
        general_review = SellerReview(
            tenant_id=None, seller_user_id=seller_id, reviewer_user_id=buyer_id, rating=5,
        )
        db.add(general_review)
        db.commit()
        db.delete(general_review)
        db.commit()
    finally:
        db.close()


def test_db_trigger_rejects_unknown_discriminator_value(actors: Actors) -> None:
    buyer_tokens, _ = actors.register_via_otp("Trigger Unknown Type Buyer")
    buyer_id = uuid.UUID(actors.client.get("/api/v1/auth/me", headers=actors.auth(buyer_tokens)).json()["id"])

    db = SessionLocal()
    try:
        db.add(ListingFavorite(user_id=buyer_id, listing_type="not-a-real-type", listing_id=uuid.uuid4()))
        with pytest.raises(DBAPIError, match="unknown listing_type"):
            db.commit()
        db.rollback()
    finally:
        db.close()
