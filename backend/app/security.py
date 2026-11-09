"""Password hashing and JWT helpers.

Passwords use PBKDF2-HMAC-SHA256 with a per-user random salt. This avoids a
native bcrypt dependency while keeping the demo reproducible on minimal hosts.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from .config import settings

PBKDF2_ITERATIONS = 240_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode(),
        base64.urlsafe_b64encode(derived).decode(),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, email: str, system_role: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "system_role": system_role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
        "iss": "knowledgebridge",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        issuer="knowledgebridge",
        options={"require": ["exp", "iat", "sub"]},
    )


def create_password_reset_token(email: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": email,
        "purpose": "password_reset",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
        "iss": "knowledgebridge",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_password_reset_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer="knowledgebridge",
            options={"require": ["exp", "iat", "sub"]},
        )
        if payload.get("purpose") != "password_reset":
            return None
        return str(payload.get("sub"))
    except (jwt.PyJWTError, ValueError, TypeError):
        return None
