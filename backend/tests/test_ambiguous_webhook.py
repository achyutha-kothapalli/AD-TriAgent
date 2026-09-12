import hashlib
import hmac
import json

from app.main import _valid_ambiguous_signature


def test_valid_ambiguous_signature() -> None:
    body = b'{"event_id":"evt-1234"}'
    secret = "relay-secret"
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    assert _valid_ambiguous_signature(secret, body, f"sha256={signature}")


def test_invalid_ambiguous_signature_is_rejected() -> None:
    assert not _valid_ambiguous_signature("relay-secret", b"{}", "sha256=wrong")
    assert not _valid_ambiguous_signature(None, json.dumps({}).encode("utf-8"), None)
