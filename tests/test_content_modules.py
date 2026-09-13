"""Coverage for the "simple content" modules (markets, places, government
services, faqs, news) that had none before - only hospitals/businesses were
exercised (test_phase3.py), and even those didn't cover update or draft
visibility. This is the safety net for the item-3 module-duplication
refactor (extracting the shared tenant-scoping helpers these modules all
duplicate into app/core/content_scope.py)."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.rbac import Role
from app.db.models import Faq, Market, NewsArticle, Place, Service, Tenant
from tests.conftest import Actors


def _delete(model, ids: list[str]) -> None:
    if not ids:
        return
    db = SessionLocal()
    try:
        db.query(model).filter(model.id.in_([uuid.UUID(i) for i in ids])).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_market_admin_crud_and_public_visibility(
    client: TestClient, actors: Actors, reference_ids: dict[str, str]
) -> None:
    admin = actors.promote(actors.register_via_otp("Market Editor")[0], Role.SUPER_ADMIN)
    run = actors.run_id
    created_ids: list[str] = []
    try:
        created = client.post(
            "/api/v1/markets",
            json={
                "location_id": reference_ids["location_id"],
                "name_bn": f"[Test {run}] বাজার",
                "type": "general",
            },
            headers=actors.auth(admin),
        )
        assert created.status_code == 201, created.text
        market_id = created.json()["id"]
        created_ids.append(market_id)

        listed = client.get("/api/v1/markets", params={"page_size": 60}).json()["items"]
        assert market_id in {m["id"] for m in listed}

        fetched = client.get(f"/api/v1/markets/{market_id}").json()
        assert fetched["name"] == f"[Test {run}] বাজার"

        admin_view = client.get(f"/api/v1/markets/admin/{market_id}", headers=actors.auth(admin)).json()
        assert admin_view["name_bn"] == f"[Test {run}] বাজার"

        updated = client.patch(
            f"/api/v1/markets/{market_id}", json={"name_en": "Updated Market"}, headers=actors.auth(admin)
        )
        assert updated.status_code == 200, updated.text

        refetched = client.get(f"/api/v1/markets/{market_id}", headers={"Accept-Language": "en"})
        assert refetched.json()["name"] == "Updated Market"

        assert client.get(f"/api/v1/markets/admin/{uuid.uuid4()}", headers=actors.auth(admin)).status_code == 404
    finally:
        _delete(Market, created_ids)


def test_place_draft_status_hides_from_public_view(
    client: TestClient, actors: Actors, reference_ids: dict[str, str]
) -> None:
    admin = actors.promote(actors.register_via_otp("Place Editor")[0], Role.SUPER_ADMIN)
    run = actors.run_id
    slug = f"test-place-{run}"
    created_ids: list[str] = []
    try:
        created = client.post(
            "/api/v1/places",
            json={
                "location_id": reference_ids["location_id"],
                "name_bn": f"[Test {run}] স্থান",
                "slug": slug,
                "category": "park",
            },
            headers=actors.auth(admin),
        )
        assert created.status_code == 201, created.text
        place_id = created.json()["id"]
        created_ids.append(place_id)
        assert created.json()["status"] == "published"

        assert client.get(f"/api/v1/places/{slug}").status_code == 200

        drafted = client.patch(f"/api/v1/places/{place_id}", json={"status": "draft"}, headers=actors.auth(admin))
        assert drafted.status_code == 200 and drafted.json()["status"] == "draft"

        # Draft is invisible publicly (by slug and in the list) but still visible to admin.
        assert client.get(f"/api/v1/places/{slug}").status_code == 404
        listed = client.get("/api/v1/places", params={"page_size": 60}).json()["items"]
        assert place_id not in {p["id"] for p in listed}
        assert client.get(f"/api/v1/places/admin/{place_id}", headers=actors.auth(admin)).status_code == 200
    finally:
        _delete(Place, created_ids)


def test_government_service_admin_crud(
    client: TestClient, actors: Actors, reference_ids: dict[str, str]
) -> None:
    admin = actors.promote(actors.register_via_otp("Service Editor")[0], Role.SUPER_ADMIN)
    run = actors.run_id
    created_ids: list[str] = []
    try:
        created = client.post(
            "/api/v1/services",
            json={
                "location_id": reference_ids["location_id"],
                "category_id": reference_ids["service_category_id"],
                "name_bn": f"[Test {run}] সেবা",
            },
            headers=actors.auth(admin),
        )
        assert created.status_code == 201, created.text
        service_id = created.json()["id"]
        created_ids.append(service_id)

        assert client.get(f"/api/v1/services/{service_id}").status_code == 200
        listed = client.get("/api/v1/services", params={"page_size": 60}).json()["items"]
        assert service_id in {s["id"] for s in listed}

        updated = client.patch(
            f"/api/v1/services/{service_id}", json={"fee": 150.0}, headers=actors.auth(admin)
        )
        assert updated.status_code == 200 and updated.json()["fee"] == 150.0
        assert client.get(f"/api/v1/services/admin/{uuid.uuid4()}", headers=actors.auth(admin)).status_code == 404
    finally:
        _delete(Service, created_ids)


def test_faq_draft_status_hides_from_public_list(
    client: TestClient, actors: Actors
) -> None:
    admin = actors.promote(actors.register_via_otp("Faq Editor")[0], Role.SUPER_ADMIN)
    run = actors.run_id
    created_ids: list[str] = []
    try:
        published = client.post(
            "/api/v1/faqs",
            json={"question_bn": f"[Test {run}] প্রশ্ন?", "answer_bn": "উত্তর।"},
            headers=actors.auth(admin),
        )
        assert published.status_code == 201, published.text
        created_ids.append(published.json()["id"])

        draft = client.post(
            "/api/v1/faqs",
            json={"question_bn": f"[Test {run}] খসড়া?", "answer_bn": "খসড়া উত্তর।", "status": "draft"},
            headers=actors.auth(admin),
        )
        assert draft.status_code == 201, draft.text
        created_ids.append(draft.json()["id"])

        listed = {f["id"] for f in client.get("/api/v1/faqs").json()}
        assert published.json()["id"] in listed
        assert draft.json()["id"] not in listed

        admin_view = client.get(f"/api/v1/faqs/admin/{draft.json()['id']}", headers=actors.auth(admin))
        assert admin_view.status_code == 200 and admin_view.json()["status"] == "draft"
    finally:
        _delete(Faq, created_ids)


def test_news_draft_status_hides_from_public_view(
    client: TestClient, actors: Actors, reference_ids: dict[str, str]
) -> None:
    admin = actors.promote(actors.register_via_otp("News Editor")[0], Role.SUPER_ADMIN)
    run = actors.run_id
    created_ids: list[str] = []
    try:
        published_slug = f"test-news-published-{run}"
        published = client.post(
            "/api/v1/news",
            json={
                "source_id": reference_ids["news_source_id"],
                "title": f"[Test {run}] প্রকাশিত খবর",
                "slug": published_slug,
                "status": "published",
            },
            headers=actors.auth(admin),
        )
        assert published.status_code == 201, published.text
        created_ids.append(published.json()["id"])

        draft_slug = f"test-news-draft-{run}"
        draft = client.post(
            "/api/v1/news",
            json={
                "source_id": reference_ids["news_source_id"],
                "title": f"[Test {run}] খসড়া খবর",
                "slug": draft_slug,
            },
            headers=actors.auth(admin),
        )
        assert draft.status_code == 201, draft.text
        assert draft.json()["status"] == "draft"
        created_ids.append(draft.json()["id"])

        assert client.get(f"/api/v1/news/{published_slug}").status_code == 200
        assert client.get(f"/api/v1/news/{draft_slug}").status_code == 404
        listed = {a["id"] for a in client.get("/api/v1/news", params={"page_size": 60}).json()["items"]}
        assert published.json()["id"] in listed
        assert draft.json()["id"] not in listed
    finally:
        _delete(NewsArticle, created_ids)


def test_anonymous_tenant_isolation_across_content_modules(client: TestClient) -> None:
    """Formalizes the header-based tenant resolution added for item 2: content
    belonging to another tenant is invisible without X-Tenant-Slug and visible
    with it, while the current single-tenant deployment (no header) is
    unaffected - same scenario verified ad-hoc during that work, now permanent."""
    db = SessionLocal()
    other_tenant = Tenant(id=uuid.uuid4(), name="Isolation Test Tenant", slug=f"isotest-{uuid.uuid4().hex[:8]}", status="active")
    db.add(other_tenant)
    db.flush()
    other_faq = Faq(tenant_id=other_tenant.id, question_bn="প্রশ্ন?", answer_bn="উত্তর।", status="published")
    db.add(other_faq)
    db.commit()
    other_faq_id = str(other_faq.id)
    try:
        no_header = {f["id"] for f in client.get("/api/v1/faqs").json()}
        assert other_faq_id not in no_header

        with_header = {
            f["id"] for f in client.get("/api/v1/faqs", headers={"X-Tenant-Slug": other_tenant.slug}).json()
        }
        assert other_faq_id in with_header
    finally:
        db.delete(other_faq)
        db.delete(other_tenant)
        db.commit()
        db.close()
