"""The user id ALWAYS comes from the verified login token, never from LLM text."""
from dataclasses import dataclass

import jwt  # PyJWT
from fastapi import Header, HTTPException

from app.config import settings


@dataclass(frozen=True)
class AuthedUser:
    user_id: str
    token: str  # forwarded to backend tool endpoints so the backend re-checks it


def get_current_user(authorization: str = Header(default="")) -> AuthedUser:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
                             options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    if payload.get("type") != "access":  # the backend issues "access" and "refresh" tokens
        raise HTTPException(status_code=401, detail="Access token required")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token has no subject")
    return AuthedUser(user_id=str(user_id), token=token)