"""Shared FastAPI dependencies."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models import User
from app.models.enums import Role

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    refresh_token: Annotated[str | None, Cookie(alias="refresh_token")] = None,
) -> User:
    token: str | None = None
    if credentials is not None:
        token = credentials.credentials
    elif refresh_token:
        token = refresh_token

    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    payload = decode_token(token, expected_type="access")
    if payload is None:
        payload = decode_token(token, expected_type="refresh")
    if payload is None or not payload.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token subject") from None

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


async def get_current_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


async def get_optional_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User | None:
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials, expected_type="access")
    if payload is None or not payload.get("sub"):
        return None
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        return None
    user = await db.get(User, user_id)
    return user if user and user.is_active else None


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
AdminUser = Annotated[User, Depends(get_current_admin)]


class Pagination:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1, le=10000)] = 1,
        per_page: Annotated[int, Query(ge=1, le=100)] = 25,
    ) -> None:
        self.page = page
        self.per_page = per_page

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


PaginationDep = Annotated[Pagination, Depends(Pagination)]
