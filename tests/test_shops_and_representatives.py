"""New-feature checks: shop create -> moderation -> public visibility (mirrors
the exchange/marketplace flow in test_phase2_flows.py), and the representative
directory's admin-create / self-edit / ownership guard."""

from fastapi.testclient import TestClient

from app.core.rbac import Role
from tests.conftest import Actors


def test_shop_lifecycle_with_moderation(client: TestClient, actors: Actors, reference_ids: dict[str, str]) -> None:
    shopkeeper_tokens, _ = actors.register_via_otp("Shopkeeper One")
    moderator_tokens = actors.promote(actors.register_via_otp("Shop Mod One")[0], Role.MARKETPLACE_MODERATOR)

    payload = {
        "market_id": reference_ids["market_id"],
        "category_id": reference_ids["shop_category_id"],
        "name": "[Test] Rahim Pharmacy",
        "description": "integration-test shop",
        "contact_phone": "+8801700000000",
    }
    created = client.post("/api/v1/shops", json=payload, headers=actors.auth(shopkeeper_tokens))
    assert created.status_code == 201, created.text
    shop = created.json()
    assert shop["moderation_status"] == "pending"
    assert shop["market_id"] == reference_ids["market_id"]

    # Pending shops are invisible publicly, but visible to the owner.
    public = client.get("/api/v1/shops", params={"market_id": reference_ids["market_id"]}).json()
    assert all(item["id"] != shop["id"] for item in public["items"])
    assert client.get(f"/api/v1/shops/{shop['id']}").status_code == 404
    assert client.get(f"/api/v1/shops/{shop['id']}", headers=actors.auth(shopkeeper_tokens)).status_code == 200

    queue = client.get(
        "/api/v1/moderation/queue", params={"entity_type": "shop"}, headers=actors.auth(moderator_tokens)
    )
    assert queue.status_code == 200, queue.text
    item = next(i for i in queue.json()["items"] if i["entity_id"] == shop["id"])
    assert item["listing"]["title"] == payload["name"]

    reviewed = client.post(
        f"/api/v1/moderation/queue/{item['id']}/review",
        json={"decision": "approve", "note": "looks fine"},
        headers=actors.auth(moderator_tokens),
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "approved"

    detail = client.get(f"/api/v1/shops/{shop['id']}")
    assert detail.status_code == 200 and detail.json()["moderation_status"] == "approved"

    public_after = client.get("/api/v1/shops", params={"market_id": reference_ids["market_id"]}).json()
    assert shop["id"] in {item["id"] for item in public_after["items"]}

    # Only a moderator can feature a shop, not the shopkeeper themselves.
    self_feature = client.patch(
        f"/api/v1/shops/{shop['id']}", json={"is_featured": True}, headers=actors.auth(shopkeeper_tokens)
    )
    assert self_feature.status_code == 403
    mod_feature = client.patch(
        f"/api/v1/shops/{shop['id']}", json={"is_featured": True}, headers=actors.auth(moderator_tokens)
    )
    assert mod_feature.status_code == 200, mod_feature.text
    assert mod_feature.json()["is_featured"] is True

    featured = client.get(
        "/api/v1/shops", params={"market_id": reference_ids["market_id"], "featured_only": True}
    ).json()
    assert shop["id"] in {item["id"] for item in featured["items"]}


def test_representative_admin_create_and_self_edit(
    client: TestClient, actors: Actors, reference_ids: dict[str, str]
) -> None:
    citizen_tokens, _ = actors.register_via_otp("Future Chairman")
    other_tokens, _ = actors.register_via_otp("Someone Else")
    admin_tokens = actors.promote(actors.register_via_otp("Rep Admin")[0], Role.SUPER_ADMIN)
    citizen_me = client.get("/api/v1/auth/me", headers=actors.auth(citizen_tokens)).json()

    payload = {
        "user_id": citizen_me["id"],
        "location_id": reference_ids["union_id"],
        "position": "chairman",
        "bio": "integration-test chairman",
    }
    created = client.post("/api/v1/representatives", json=payload, headers=actors.auth(admin_tokens))
    assert created.status_code == 201, created.text
    rep = created.json()
    assert rep["full_name"] == "Future Chairman"
    assert rep["phone"] is not None  # deliberately unmasked (citizen-contact directory)
    assert rep["position"] == "chairman"

    # A second chairman for the same union is rejected.
    dup = client.post("/api/v1/representatives", json=payload, headers=actors.auth(admin_tokens))
    assert dup.status_code == 409

    # Public, unauthenticated read.
    listed = client.get("/api/v1/representatives", params={"location_id": reference_ids["union_id"]})
    assert listed.status_code == 200
    assert rep["id"] in {r["id"] for r in listed.json()["items"]}

    # Someone else cannot edit the profile.
    forbidden = client.patch(
        f"/api/v1/representatives/{rep['id']}", json={"bio": "hijacked"}, headers=actors.auth(other_tokens)
    )
    assert forbidden.status_code == 403

    # The linked account can edit their own bio.
    self_edit = client.patch(
        f"/api/v1/representatives/{rep['id']}", json={"bio": "updated bio"}, headers=actors.auth(citizen_tokens)
    )
    assert self_edit.status_code == 200, self_edit.text
    assert self_edit.json()["bio"] == "updated bio"

    # The linked account cannot reassign its own location/position/status -
    # only a CONTENT_MANAGE actor can (same endpoint, permission-gated server-side).
    assert (
        client.patch(
            f"/api/v1/representatives/{rep['id']}",
            json={"status": "inactive"},
            headers=actors.auth(citizen_tokens),
        ).status_code
        == 403
    )
    admin_reassign = client.patch(
        f"/api/v1/representatives/{rep['id']}", json={"status": "inactive"}, headers=actors.auth(admin_tokens)
    )
    assert admin_reassign.status_code == 200, admin_reassign.text
    assert admin_reassign.json()["status"] == "inactive"
