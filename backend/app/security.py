import os
import jwt
from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash

SECRET_KEY = os.environ["JWT_SECRET_KEY"]
ALGORITHM = "HS256"

password_hash = PasswordHash.recommended()


def hash_password(password):
    return password_hash.hash(password)


def verify_password(password, hashed_password):
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id):
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id):
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])