"""Short-lived management sessions for private bibliography assets."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import UTC, datetime


class AdminSessionConfigurationError(RuntimeError):
    pass


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _configuration() -> tuple[str, bytes, int]:
    credential = os.environ.get("BIB_ADMIN_TOKEN", "")
    secret = os.environ.get("BIB_SESSION_SECRET", "").encode("utf-8")
    if not credential or len(secret) < 32:
        raise AdminSessionConfigurationError(
            "Private asset sessions are not configured"
        )
    ttl = int(os.environ.get("BIB_ADMIN_SESSION_TTL_SECONDS", "28800"))
    if ttl <= 0:
        raise AdminSessionConfigurationError(
            "BIB_ADMIN_SESSION_TTL_SECONDS must be positive"
        )
    return credential, secret, ttl


def create_session(credential: str) -> tuple[str, datetime] | None:
    expected, secret, ttl = _configuration()
    if not hmac.compare_digest(credential, expected):
        return None
    expires_at = int(time.time()) + ttl
    payload = json.dumps(
        {
            "exp": expires_at,
            "nonce": secrets.token_urlsafe(12),
            "scope": "source-assets",
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded_payload = _encode(payload)
    signature = hmac.new(
        secret, encoded_payload.encode("ascii"), hashlib.sha256
    ).digest()
    token = f"{encoded_payload}.{_encode(signature)}"
    return token, datetime.fromtimestamp(expires_at, UTC)


def verify_session(token: str) -> bool:
    try:
        _, secret, _ = _configuration()
        encoded_payload, encoded_signature = token.split(".", 1)
        expected = hmac.new(
            secret, encoded_payload.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_decode(encoded_signature), expected):
            return False
        payload = json.loads(_decode(encoded_payload))
        return payload.get("scope") == "source-assets" and int(
            payload.get("exp", 0)
        ) > int(time.time())
    except (ValueError, TypeError, json.JSONDecodeError):
        return False
