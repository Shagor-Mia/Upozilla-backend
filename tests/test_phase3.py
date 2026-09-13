"""Phase 3 backend checks: near-me radius queries, the app-version meta gate,
and business verification (badge) with its audit trail."""

import uuid

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.rbac import Role
from app.db.models import AuditLog, Business, Hospital
from tests.conftest import Actors

# Homna upazila centre (Cumilla). Distances below are relative to this point.
ORIGIN = {"lat": 23.6833, "lng": 90.7833}


def _delete(model, ids: list[str]) -> None:
    if not ids:
        return
    db = SessionLocal()
    try:
        db.query(model).filter(model.id.in_([uuid.UUID(i) for i in ids])).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_near_me_filters_sorts_and_reports_distance(
    client: TestClient, actors: Actors, reference_ids: dict[str, str]
) -> None:
    tokens, _ = actors.register_via_otp("Near Me Editor")
    admin = actors.promote(tokens, Role.SUPER_ADMIN)
    run = actors.run_id
    created: list[str] = []

    def add(name: str, lat: float | None, lng: float | None) -> str:
        response = client.post(
            "/api/v1/hospitals",
            json={
                "location_id": reference_ids["location_id"],
                "name_bn": f"[Test {run}] {name}",
                "type": "clinic",
                "latitude": lat,
                "longitude": lng,
            },
            headers=actors.auth(admin),
        )
        assert response.status_code == 201, response.text
        created.append(response.json()["id"])
        return response.json()["id"]

    try:
        far_id = add("Far clinic", 23.7500, 90.7833)  # ~7.4 km north
        near_id = add("Near clinic", 23.6900, 90.7833)  # ~0.7 km north
        add("No coordinates clinic", None, None)
        add("Very far clinic", 24.5000, 90.7833)  # ~91 km

        # Default listing: unchanged shape, distance is null.
        plain = client.get("/api/v1/hospitals").json()["items"]
        by_id = {h["id"]: h for h in plain}
        assert all(h["distance_km"] is None for h in plain)
        assert near_id in by_id and far_id in by_id

        # Radius 10 km: nearest first, the no-coordinate and 91 km rows are dropped.
        near = client.get(
            "/api/v1/hospitals", params={**ORIGIN, "radius_km": 10, "page_size": 60}
        ).json()["items"]
        test_rows = [h for h in near if h["name"].startswith(f"[Test {run}]")]
        assert [h["id"] for h in test_rows] == [near_id, far_id]
        assert 0.5 < test_rows[0]["distance_km"] < 1.0
        assert 7.0 < test_rows[1]["distance_km"] < 8.0
        assert all(h["distance_km"] is not None for h in near)
        assert near == sorted(near, key=lambda h: h["distance_km"])

        # Radius 2 km: only the near one survives.
        tight = client.get(
            "/api/v1/hospitals", params={**ORIGIN, "radius_km": 2, "page_size": 60}
        ).json()["items"]
        assert [h["id"] for h in tight if h["name"].startswith(f"[Test {run}]")] == [near_id]

        # Validation: radius above the cap and half-specified coordinates are rejected.
        assert client.get("/api/v1/hospitals", params={**ORIGIN, "radius_km": 500}).status_code == 422
        assert client.get("/api/v1/hospitals", params={"lat": 200, "lng": 90}).status_code == 422
        # lat without lng falls back to the plain listing rather than erroring.
        assert client.get("/api/v1/hospitals", params={"lat": 23.7}).status_code == 200
    finally:
        _delete(Hospital, created)


def test_meta_exposes_app_version_gate(client: TestClient) -> None:
    response = client.get("/api/v1/meta")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["api_version"] == "v1"
    for key in ("min_supported_app_version", "latest_app_version"):
        parts = body[key].split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts), body[key]


def test_business_verification_requires_permission_and_is_audited(
    client: TestClient, actors: Actors, reference_ids: dict[str, str]
) -> None:
    owner_tokens, _ = actors.register_via_otp("Shop Owner")
    run = actors.run_id
    business_ids: list[str] = []
    try:
        created = client.post(
            "/api/v1/businesses",
            json={
                "location_id": reference_ids["location_id"],
                "name_bn": f"[Test {run}] Corner Shop",
                "slug": f"test-corner-shop-{run}",
                "category": "grocery",
            },
            headers=actors.auth(owner_tokens),
        )
        assert created.status_code == 201, created.text
        business_id = created.json()["id"]
        business_ids.append(business_id)
        assert created.json()["is_verified"] is False

        # A plain user (even the owner) can neither list for verification nor verify.
        assert client.get("/api/v1/admin/businesses", headers=actors.auth(owner_tokens)).status_code == 403
        denied = client.patch(
            f"/api/v1/admin/businesses/{business_id}/verification",
            json={"is_verified": True},
            headers=actors.auth(owner_tokens),
        )
        assert denied.status_code == 403

        verifier_tokens, _ = actors.register_via_otp("Badge Verifier")
        verifier = actors.promote(verifier_tokens, Role.BUSINESS_VERIFIER)
        listed = client.get("/api/v1/admin/businesses", headers=actors.auth(verifier))
        assert listed.status_code == 200, listed.text
        assert business_id in {b["id"] for b in listed.json()}

        verified = client.patch(
            f"/api/v1/admin/businesses/{business_id}/verification",
            json={"is_verified": True},
            headers=actors.auth(verifier),
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["is_verified"] is True

        # Public directory reflects the badge.
        public = client.get(f"/api/v1/businesses/test-corner-shop-{run}").json()
        assert public["is_verified"] is True

        db = SessionLocal()
        try:
            audit = (
                db.query(AuditLog)
                .filter(AuditLog.entity_type == "business", AuditLog.entity_id == uuid.UUID(business_id))
                .order_by(AuditLog.created_at.desc())
                .first()
            )
            assert audit is not None and audit.action == "business.verified"
        finally:
            db.close()

        missing = client.patch(
            f"/api/v1/admin/businesses/{uuid.uuid4()}/verification",
            json={"is_verified": True},
            headers=actors.auth(verifier),
        )
        assert missing.status_code == 404
    finally:
        _delete(Business, business_ids)
