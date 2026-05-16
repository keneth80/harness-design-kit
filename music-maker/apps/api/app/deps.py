"""Dependency wiring: DB session, current user (JWT)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.models.user import User


async def db_session() -> AsyncIterator[AsyncSession]:
    async for s in get_session():
        yield s


def _decode_jwt(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_signing_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token",
        ) from exc


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(get_settings),
) -> User:
    """Resolve the current user from a Bearer JWT.

    Tests may override this dependency via `app.dependency_overrides`.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer_token"
        )
    token = authorization.split(" ", 1)[1].strip()
    payload = _decode_jwt(token, settings)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="malformed_token"
        )
    try:
        uid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="malformed_user_id"
        ) from exc
    result = await session.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found"
        )
    return user
