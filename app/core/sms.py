"""SMS gateway abstraction for phone OTP delivery (Section 10).

Which gateway is used comes from runtime settings (admin CMS -> env fallback).
The default `console` gateway logs the message and lets the API echo the code
back so the flow works with no provider account (demo mode). `HttpSmsGateway`
is a generic JSON-POST adapter - adjust `_build_payload` to the chosen
provider's API once one is picked; nothing else in the OTP flow changes.
"""

import logging
from typing import Protocol

import httpx

from app.core import runtime_settings
from app.core.config import settings

logger = logging.getLogger(__name__)


class SmsGateway(Protocol):
    name: str

    def send(self, phone: str, message: str) -> None: ...


class ConsoleSmsGateway:
    name = "console"

    def send(self, phone: str, message: str) -> None:
        # OTP codes must never be logged in production (Section 8.5 / 14.5);
        # this gateway is refused there by get_sms_gateway().
        logger.info("[SMS:console] to=%s message=%s", phone, message)


class HttpSmsGateway:
    name = "http"

    def __init__(self, url: str, api_key: str, sender_id: str):
        self._url = url
        self._api_key = api_key
        self._sender_id = sender_id

    def _build_payload(self, phone: str, message: str) -> dict[str, str]:
        return {"to": phone, "message": message, "sender_id": self._sender_id}

    def send(self, phone: str, message: str) -> None:
        response = httpx.post(
            self._url,
            json=self._build_payload(phone, message),
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=10,
        )
        response.raise_for_status()


def get_sms_gateway() -> SmsGateway:
    mode = runtime_settings.get("sms_gateway") or "console"
    if mode == "http":
        url = runtime_settings.get("sms_http_url")
        api_key = runtime_settings.get("sms_http_api_key")
        if not url or not api_key:
            raise RuntimeError("SMS gateway 'http' needs a gateway URL and API key (admin > Settings > SMS)")
        return HttpSmsGateway(url, api_key, runtime_settings.get("sms_sender_id") or "Upazila")
    if settings.is_production:
        raise RuntimeError("SMS gateway 'console' is not allowed in production - configure a real gateway")
    return ConsoleSmsGateway()


def sender_name() -> str:
    return runtime_settings.get("sms_sender_id") or "Upazila"
