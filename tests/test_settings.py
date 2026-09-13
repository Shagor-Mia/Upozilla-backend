"""Admin-editable integration settings: DB value overrides env, secrets stay
write-only, public endpoint exposes only public keys."""

from fastapi.testclient import TestClient

from app.core import runtime_settings
from app.core.database import SessionLocal
from app.core.rbac import Role
from app.db.models.settings import PlatformSetting
from tests.conftest import Actors

TEST_KEYS = ["sms_sender_id", "turnstile_secret_key", "gtm_id"]


def _cleanup() -> None:
    db = SessionLocal()
    try:
        db.query(PlatformSetting).filter(PlatformSetting.key.in_(TEST_KEYS)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    runtime_settings.invalidate()


def test_settings_roundtrip_and_secret_masking(client: TestClient, actors: Actors) -> None:
    _cleanup()
    try:
        plain_tokens, _ = actors.register_via_otp("Settings Plain")
        assert client.get("/api/v1/admin/settings", headers=actors.auth(plain_tokens)).status_code == 403
        admin_tokens = actors.promote(plain_tokens, Role.SUPER_ADMIN)

        updated = client.put(
            "/api/v1/admin/settings",
            json={"values": {"sms_sender_id": "TestSender", "turnstile_secret_key": "super-secret", "gtm_id": "GTM-TEST123"}},
            headers=actors.auth(admin_tokens),
        )
        assert updated.status_code == 200, updated.text
        by_key = {item["key"]: item for item in updated.json()}
        assert by_key["sms_sender_id"]["value"] == "TestSender" and by_key["sms_sender_id"]["source"] == "database"
        # Secret is reported as configured but its value is never echoed back.
        assert by_key["turnstile_secret_key"]["is_configured"] is True
        assert by_key["turnstile_secret_key"]["value"] is None

        public = client.get("/api/v1/settings/public").json()
        assert public["gtm_id"] == "GTM-TEST123"
        assert "turnstile_secret_key" not in public
        assert runtime_settings.get("turnstile_secret_key") == "super-secret"

        # Validation: unknown key and bad select value are rejected.
        assert client.put("/api/v1/admin/settings", json={"values": {"nope": "x"}}, headers=actors.auth(admin_tokens)).status_code == 400
        assert (
            client.put("/api/v1/admin/settings", json={"values": {"sms_gateway": "carrier-pigeon"}}, headers=actors.auth(admin_tokens)).status_code
            == 400
        )

        # Clearing falls back to the environment default.
        cleared = client.put("/api/v1/admin/settings", json={"values": {"sms_sender_id": ""}}, headers=actors.auth(admin_tokens))
        sender = next(i for i in cleared.json() if i["key"] == "sms_sender_id")
        assert sender["source"] == "environment" and sender["value"] == "Upazila"
    finally:
        _cleanup()
