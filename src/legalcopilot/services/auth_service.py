"""Authentication service — password hashing, JWT token management."""

import datetime
import logging
from typing import Optional

import bcrypt
import jwt

from legalcopilot.config import settings

logger = logging.getLogger(__name__)

# Token expiry
ACCESS_TOKEN_EXPIRY_HOURS = 1
REFRESH_TOKEN_EXPIRY_DAYS = 7


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        logger.warning("Password verification failed — invalid hash format")
        return False


def create_access_token(user_id: str, firm_id: str, role: str, email: str) -> str:
    """Create a JWT access token."""
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": user_id,
        "firm_id": firm_id,
        "role": role,
        "email": email,
        "iat": now,
        "exp": now + datetime.timedelta(hours=ACCESS_TOKEN_EXPIRY_HOURS),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str, firm_id: str) -> str:
    """Create a JWT refresh token (longer-lived, fewer claims)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": user_id,
        "firm_id": firm_id,
        "iat": now,
        "exp": now + datetime.timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns None if invalid/expired."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("Invalid token: %s", e)
        return None
