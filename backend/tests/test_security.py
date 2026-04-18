from __future__ import annotations

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_roundtrip():
    hashed = hash_password('secret123')
    assert verify_password('secret123', hashed)


def test_token_roundtrip():
    token = create_access_token('42', extra={'role': 'admin'})
    payload = decode_access_token(token)
    assert payload['sub'] == '42'
    assert payload['role'] == 'admin'
