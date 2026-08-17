"""Redeemable discount codes: short alphanumeric code + QR encoding it.

No external redemption service for the demo -- codes are held in an
in-memory registry keyed by code, looked up by the checkout UI on redeem.
"""
import base64
import io
import random
import string
from dataclasses import dataclass

import qrcode

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 6

_active_codes: dict[str, dict] = {}


@dataclass
class DiscountCode:
    code: str
    qr_data_uri: str


def _new_code() -> str:
    while True:
        code = "".join(random.choices(_CODE_ALPHABET, k=_CODE_LENGTH))
        if code not in _active_codes:
            return code


def _qr_data_uri(payload: str) -> str:
    img = qrcode.make(payload)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def generate_discount_code(item_name: str, discount_pct: float, final_price: float) -> DiscountCode:
    code = _new_code()
    _active_codes[code] = {
        "item_name": item_name,
        "discount_pct": discount_pct,
        "final_price": final_price,
    }
    return DiscountCode(code=code, qr_data_uri=_qr_data_uri(code))


def redeem_discount_code(code: str) -> dict | None:
    return _active_codes.get(code)
