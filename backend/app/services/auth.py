import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_db_connection

logger = logging.getLogger("rxos.auth")

security = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "8"))

if os.getenv("APP_ENV", "development").lower() == "production" and (
    JWT_SECRET == "dev-secret-change-in-production" or len(JWT_SECRET) < 32
):
    raise RuntimeError("JWT_SECRET must be configured with at least 32 characters in production")


def create_access_token(user_id: str, email: str, role: str = "user") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if not payload.get("sub") or not payload.get("email"):
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = decode_token(credentials.credentials)

    # Tokens only identify the session. Account status and authorization are
    # loaded on every request so deactivation and role changes take effect
    # immediately instead of waiting for an old JWT to expire.
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id, email, role, is_active, token_valid_after FROM "User" WHERE id = %s;',
            (payload["sub"],),
        )
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="User account no longer exists")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="User account is deactivated")
    token_issued_at = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
    valid_after = user.get("token_valid_after") or datetime(1970, 1, 1)
    if valid_after.tzinfo is None:
        valid_after = valid_after.replace(tzinfo=timezone.utc)
    if token_issued_at < valid_after:
        raise HTTPException(status_code=401, detail="Session is no longer valid")

    return {
        "user_id": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
    }


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def require_role(*allowed_roles):
    async def role_checker(user: dict = Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user['role']}' is not authorized. Required: {', '.join(allowed_roles)}",
            )
        return user
    return role_checker
