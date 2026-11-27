"""The advisor must accept only the backend's ACCESS tokens (same shape as backend/app/security.py)."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from app.auth import get_current_user
from app.config import settings


def make(**over):
    payload = {"sub": "7", "type": "access", "exp": datetime.now(timezone.utc) + timedelta(minutes=15)}
    payload.update(over)
    return "Bearer " + jwt.encode({k: v for k, v in payload.items() if v is not None}, settings.jwt_secret, algorithm="HS256")


def test_valid_access_token_gives_user_id_from_sub():
    u = get_current_user(make())
    assert u.user_id == "7" and u.token


@pytest.mark.parametrize("header", [
    make(type="refresh"),                                                # refresh token must NOT work
    make(exp=datetime.now(timezone.utc) - timedelta(minutes=1)),         # expired
    make(exp=None),                                                      # no expiry
    make(sub=None),                                                      # no subject
    "Bearer " + jwt.encode({"sub": "7", "type": "access", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "x" * 40, algorithm="HS256"),  # wrong secret
    "",                                                                  # missing header
    "Token abc",                                                         # wrong scheme
])
def test_bad_tokens_rejected(header):
    with pytest.raises(HTTPException) as e:
        get_current_user(header)
    assert e.value.status_code == 401