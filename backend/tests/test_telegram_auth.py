import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.api.telegram_auth import InitDataError, validate_init_data

BOT_TOKEN = "123456:TEST"


def _sign(fields: dict[str, str]) -> str:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    signed = {**fields, "hash": hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()}
    return urlencode(signed)


def _fields(auth_date: int | None = None) -> dict[str, str]:
    return {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAH",
        "user": json.dumps({"id": 42, "first_name": "Олена"}, ensure_ascii=False),
    }


def test_valid_init_data() -> None:
    user = validate_init_data(_sign(_fields()), BOT_TOKEN, max_age_seconds=3600)
    assert user["id"] == 42


def test_tampered_init_data() -> None:
    init_data = _sign(_fields()).replace("42", "43")
    with pytest.raises(InitDataError):
        validate_init_data(init_data, BOT_TOKEN, max_age_seconds=3600)


def test_expired_init_data() -> None:
    init_data = _sign(_fields(auth_date=int(time.time()) - 7200))
    with pytest.raises(InitDataError):
        validate_init_data(init_data, BOT_TOKEN, max_age_seconds=3600)
