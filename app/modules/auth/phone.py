"""Bangladeshi mobile number normalisation for the OTP flow.

Stored form is E.164 (`+8801XXXXXXXXX`). Only BD mobiles are accepted for
now: OTP verification exists to gate local marketplace sellers (Section 10),
and every SMS gateway quote so far is domestic-only.
"""

import re

_BD_MOBILE = re.compile(r"^01[3-9]\d{8}$")


def normalize_bd_phone(raw: str) -> str:
    digits = re.sub(r"[\s\-()]", "", raw.strip())
    if digits.startswith("+880"):
        digits = digits[3:]
    elif digits.startswith("880"):
        digits = digits[2:]
    elif digits.startswith("+"):
        raise ValueError("only Bangladeshi mobile numbers are supported")

    if not _BD_MOBILE.match(digits):
        raise ValueError("enter a valid Bangladeshi mobile number, e.g. 01XXXXXXXXX")
    return f"+88{digits}"


def mask_phone(phone: str | None) -> str | None:
    """Section 14.4: never expose raw phone numbers publicly. `+8801712345678` -> `+88017****678`."""
    if not phone:
        return None
    if len(phone) < 8:
        return "*" * len(phone)
    return f"{phone[:6]}****{phone[-3:]}"
