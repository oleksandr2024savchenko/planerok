"""Validation of Telegram Mini App initData.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InitDataError(ValueError):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int) -> dict:
    fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise InitDataError("hash is missing")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise InitDataError("hash mismatch")

    try:
        auth_date = int(fields.get("auth_date", "0"))
    except ValueError as exc:
        raise InitDataError("invalid auth_date") from exc
    if max_age_seconds and time.time() - auth_date > max_age_seconds:
        raise InitDataError("initData expired")

    try:
        user = json.loads(fields["user"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise InitDataError("user is missing") from exc
    if not isinstance(user, dict) or "id" not in user:
        raise InitDataError("user id is missing")
    return user
