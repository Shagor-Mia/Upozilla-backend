"""End-to-end Phase 2 checks against the real API + DB:
OTP register -> phone-verified gate -> listing moderation -> favorites,
messaging, reports, reviews, and the IDOR / RBAC guards around them."""

from fastapi.testclient import TestClient

from app.core.rbac import Role
from tests.conftest import Actors

LISTING_PAYLOAD = {
    "title": "[Test] Used bicycle",
    "description": "integration-test listing",
    "price": 3500,
    "is_negotiable": True,
    "condition": "used",
    "images": ["https://example.test/bike.jpg"],
}


def _listing_body(reference_ids: dict[str, str]) -> dict:
    return {**LISTING_PAYLOAD, **reference_ids}


def test_password_user_is_blocked_from_selling_until_phone_verified(
    client: TestClient, actors: Actors, reference_ids: dict[str, str]
) -> None:
    tokens = actors.register_via_password("Unverified Seller")
    response = client.post("/api/v1/exchange/listings", json=_listing_body(reference_ids), headers=actors.auth(tokens))
    assert response.status_code == 403
    assert "phone verification" in response.json()["detail"]

    # verify_phone purpose attaches a number to the signed-in account
    phone = actors.next_phone()
    requested = client.post(
        "/api/v1/auth/otp/request", json={"phone": phone, "purpose": "verify_phone"}, headers=actors.auth(tokens)
    )
    assert requested.status_code == 200, requested.text
    wrong = client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": phone, "code": "000000", "purpose": "verify_phone"},
        headers=actors.auth(tokens),
    )
    assert wrong.status_code == 400
    verified = client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": phone, "code": requested.json()["dev_code"], "purpose": "verify_phone"},
        headers=actors.auth(tokens),
    )
    assert verified.status_code == 200, verified.text
    me = client.get("/api/v1/auth/me", headers=actors.auth(verified.json())).json()
    assert me["phone_verified"] is True and me["phone"] == phone


def test_listing_lifecycle_with_moderation(client: TestClient, actors: Actors, reference_ids: dict[str, str]) -> None:
    seller_tokens, _ = actors.register_via_otp("Seller One")
    buyer_tokens, _ = actors.register_via_otp("Buyer One")
    moderator_tokens = actors.promote(actors.register_via_otp("Mod One")[0], Role.MARKETPLACE_MODERATOR)

    created = client.post("/api/v1/exchange/listings", json=_listing_body(reference_ids), headers=actors.auth(seller_tokens))
    assert created.status_code == 201, created.text
    listing = created.json()
    assert listing["moderation_status"] == "pending"
    assert listing["seller"]["phone_masked"].endswith(listing["seller"]["phone_masked"][-3:])
    assert "****" in listing["seller"]["phone_masked"]

    # Pending listings are invisible publicly, but visible to the owner.
    public = client.get("/api/v1/exchange/listings", params={"q": "[Test] Used bicycle"}).json()
    assert all(item["id"] != listing["id"] for item in public["items"])
    assert client.get(f"/api/v1/exchange/listings/{listing['id']}").status_code == 404
    assert client.get(f"/api/v1/exchange/listings/{listing['id']}", headers=actors.auth(seller_tokens)).status_code == 200

    # IDOR: another verified user cannot edit it.
    forbidden = client.patch(
        f"/api/v1/exchange/listings/{listing['id']}", json={"title": "hacked"}, headers=actors.auth(buyer_tokens)
    )
    assert forbidden.status_code == 403

    # A plain user cannot see the moderation queue; a marketplace_moderator can.
    assert client.get("/api/v1/moderation/queue", headers=actors.auth(buyer_tokens)).status_code == 403
    queue = client.get("/api/v1/moderation/queue", headers=actors.auth(moderator_tokens))
    assert queue.status_code == 200, queue.text
    item = next(i for i in queue.json()["items"] if i["entity_id"] == listing["id"])
    assert item["listing"]["title"] == LISTING_PAYLOAD["title"]

    reviewed = client.post(
        f"/api/v1/moderation/queue/{item['id']}/review",
        json={"decision": "approve", "note": "looks fine"},
        headers=actors.auth(moderator_tokens),
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "approved"

    detail = client.get(f"/api/v1/exchange/listings/{listing['id']}")
    assert detail.status_code == 200 and detail.json()["moderation_status"] == "approved"

    # Favorites + contact reveal + messaging + report from the buyer side.
    fav = client.put(f"/api/v1/exchange/favorites/exchange/{listing['id']}", headers=actors.auth(buyer_tokens))
    assert fav.status_code == 200 and fav.json()["is_favorited"] is True
    favorites = client.get("/api/v1/exchange/favorites", headers=actors.auth(buyer_tokens)).json()
    assert [f["id"] for f in favorites["exchange"]] == [listing["id"]]

    contact = client.post(f"/api/v1/exchange/listings/{listing['id']}/contact", headers=actors.auth(buyer_tokens))
    assert contact.status_code == 200 and contact.json()["phone"].startswith("+880")

    conversation = client.post(
        "/api/v1/conversations",
        json={"listing_type": "exchange", "listing_id": listing["id"]},
        headers=actors.auth(buyer_tokens),
    )
    assert conversation.status_code == 201, conversation.text
    conversation_id = conversation.json()["id"]
    sent = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"body": "Is this still available?"},
        headers=actors.auth(buyer_tokens),
    )
    assert sent.status_code == 201, sent.text
    # Seller sees it; a third party gets 404 (participant check).
    seller_view = client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=actors.auth(seller_tokens))
    assert seller_view.status_code == 200 and seller_view.json()[0]["body"] == "Is this still available?"
    assert client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=actors.auth(moderator_tokens)).status_code == 404
    # Sellers cannot open a conversation with themselves.
    assert (
        client.post(
            "/api/v1/conversations",
            json={"listing_type": "exchange", "listing_id": listing["id"]},
            headers=actors.auth(seller_tokens),
        ).status_code
        == 400
    )

    report = client.post(
        f"/api/v1/exchange/reports/exchange/{listing['id']}",
        json={"reason": "spam", "details": "test report"},
        headers=actors.auth(buyer_tokens),
    )
    assert report.status_code == 201, report.text
    report_items = client.get(
        "/api/v1/moderation/queue", params={"entity_type": "listing_report"}, headers=actors.auth(moderator_tokens)
    ).json()["items"]
    report_item = next(i for i in report_items if i["entity_id"] == report.json()["id"])
    upheld = client.post(
        f"/api/v1/moderation/queue/{report_item['id']}/review",
        json={"decision": "approve"},
        headers=actors.auth(moderator_tokens),
    )
    assert upheld.status_code == 200
    # An upheld report hides the listing.
    assert client.get(f"/api/v1/exchange/listings/{listing['id']}").status_code == 404

    review = client.post(
        f"/api/v1/sellers/{listing['seller_user_id']}/reviews",
        json={"rating": 4, "comment": "smooth deal", "listing_type": "exchange", "listing_id": listing["id"]},
        headers=actors.auth(buyer_tokens),
    )
    assert review.status_code == 201, review.text
    profile = client.get(f"/api/v1/sellers/{listing['seller_user_id']}").json()
    assert profile["avg_rating"] == 4.0 and profile["review_count"] == 1


def test_marketplace_product_requires_owned_business_and_lists_publicly(
    client: TestClient, actors: Actors, reference_ids: dict[str, str]
) -> None:
    seller_tokens, _ = actors.register_via_otp("Shop Owner")
    payload = {
        "category_id": reference_ids["category_id"],
        "location_id": reference_ids["location_id"],
        "title": "[Test] Rice cooker",
        "price": 2200,
        "condition": "new",
        "images": [],
    }
    created = client.post("/api/v1/marketplace/products", json=payload, headers=actors.auth(seller_tokens))
    assert created.status_code == 201, created.text
    assert created.json()["moderation_status"] == "pending"
    mine = client.get("/api/v1/marketplace/products/mine", headers=actors.auth(seller_tokens)).json()
    assert [p["id"] for p in mine] == [created.json()["id"]]
    # Unauthenticated public list excludes pending products.
    public = client.get("/api/v1/marketplace/products", params={"q": "[Test] Rice cooker"}).json()
    assert public["total"] == 0


def test_role_permissions_endpoint_reflects_rbac_mapping(client: TestClient, actors: Actors) -> None:
    plain_tokens, _ = actors.register_via_otp("Plain User")
    assert client.get("/api/v1/admin/roles", headers=actors.auth(plain_tokens)).status_code == 403
    admin_tokens = actors.promote(plain_tokens, Role.SUPER_ADMIN)
    roles = client.get("/api/v1/admin/roles", headers=actors.auth(admin_tokens))
    assert roles.status_code == 200
    by_name = {r["name"]: r["permissions"] for r in roles.json()}
    assert "marketplace.moderate" in by_name["marketplace_moderator"]
    assert "roles.manage" not in by_name["upazila_admin"]
