"""Bearer tokens — HMAC-SHA256 signed, stdlib only (no JWT library, no service).

Compact `<payload>.<signature>` where payload is url-safe-base64 JSON
`{"sub": user_id, "exp": epoch}` and the signature is HMAC-SHA256 over the payload
with the app secret. Verification is constant-time and checks expiry. This is a
minimal, self-hosted token — swap in a vetted JWT lib later without changing call
sites if desired.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


class TokenError(ValueError):
    """Raised for a malformed, tampered, or expired token."""


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload_b64: str, secret: str) -> str:
    return _b64(hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).digest())


def create_token(subject: str, secret: str, ttl_seconds: int) -> str:
    payload = {"sub": subject, "exp": int(time.time()) + ttl_seconds}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body}.{_sign(body, secret)}"


def verify_token(token: str, secret: str) -> str:
    """Return the token's subject (user id), or raise `TokenError`."""
    try:
        body, signature = token.split(".", 1)
    except (ValueError, AttributeError):
        raise TokenError("malformed token") from None
    if not hmac.compare_digest(signature, _sign(body, secret)):
        raise TokenError("bad signature")
    try:
        payload = json.loads(_unb64(body))
        if int(payload["exp"]) < time.time():
            raise TokenError("expired")
        return str(payload["sub"])
    except (ValueError, KeyError, TypeError):
        raise TokenError("invalid payload") from None
