"""Authentication: email/password, JWT and Google OAuth."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    random_token,
    verify_password,
)
from app.models import User
from app.models.enums import Role
from app.schemas import TokenResponse, UserLogin, UserRead, UserRegister

log = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"


def _issue(user: User) -> TokenResponse:
    access = create_access_token(str(user.id), user.role)
    refresh = create_refresh_token(str(user.id))
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserRead.model_validate(user),
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/v1/auth",
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, response: Response, db: DbSession) -> TokenResponse:
    email = payload.email.lower().strip()
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=Role.USER,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = _issue(user)
    _set_refresh_cookie(response, token.refresh_token or "")
    return token


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, response: Response, db: DbSession) -> TokenResponse:
    email = payload.email.lower().strip()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    token = _issue(user)
    _set_refresh_cookie(response, token.refresh_token or "")
    return token


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, db: DbSession) -> TokenResponse:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token supplied")
    payload = decode_token(token, expected_type="refresh")
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = await db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    issued = _issue(user)
    _set_refresh_cookie(response, issued.refresh_token or "")
    return issued


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.get("/google/config", summary="Google OAuth configuration")
async def google_config() -> dict:
    return {
        "enabled": bool(settings.google_client_id and settings.google_client_secret),
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "scope": "openid email profile",
    }


@router.get("/google/url", summary="Google OAuth redirect URL")
async def google_url() -> dict:
    if not (settings.google_client_id and settings.google_client_secret):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Google sign-in is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )
    from urllib.parse import urlencode

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": random_token(16),
    }
    return {"url": f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"}


@router.post("/google", response_model=TokenResponse)
async def google_sign_in(
    request: Request, response: Response, db: DbSession
) -> TokenResponse:
    """Exchange a Google ID token for a session token."""
    if not (settings.google_client_id and settings.google_client_secret):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not configured on this deployment."
        )
    body = await request.json()
    id_token = body.get("id_token") or body.get("credential")
    if not id_token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "id_token is required")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": id_token, "client_id": settings.google_client_id},
            )
            resp.raise_for_status()
            info = resp.json()
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid Google token: {exc}") from exc

    email = (info.get("email") or "").lower()
    if not email or info.get("email_verified") not in ("true", True, "1"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Google account email is not verified")

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            google_id=info.get("sub"),
            full_name=info.get("name"),
            avatar_url=info.get("picture"),
            password_hash=None,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
    else:
        user.google_id = info.get("sub") or user.google_id
        user.avatar_url = info.get("picture") or user.avatar_url
        user.is_verified = True
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    token = _issue(user)
    _set_refresh_cookie(response, token.refresh_token or "")
    return token
