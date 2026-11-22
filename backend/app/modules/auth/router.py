from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.auth.models import AuthSession, User, UserSettings
from app.modules.auth.schemas import (
    Credentials,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.modules.auth.security import (
    limiter,
    new_token,
    password_hasher,
    token_hash,
    verify_password,
)

router = APIRouter(prefix="/api/v1", tags=["accounts"])
bearer = HTTPBearer(auto_error=False)
Database = Annotated[Session, Depends(get_session)]


def unauthorized():
    return HTTPException(
        401,
        "Invalid credentials or expired session",
        headers={"WWW-Authenticate": "Bearer"},
    )


def login_allowed(user):
    return (
        user is not None
        and user.deleted_at is None
        and (
            user.registration_source == "NATIVE"
            or (user.password_hash is not None and user.email_verified_at is not None)
        )
    )


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email_normalized,
        registration_source=user.registration_source,
        role=user.role,
        timezone=user.timezone,
        locale=user.locale,
        tracking_start_date=user.tracking_start_date,
        email_verified=user.email_verified_at is not None,
    )


def limit_request(request: Request, action: str, maximum: int):
    host = request.client.host if request.client else "unknown"
    limiter.check(f"{action}:ip:{host}", maximum, 60)


def issue_tokens(db: Session, user: User, current: AuthSession | None = None):
    now = datetime.now(UTC)
    access, refresh = new_token("a_"), new_token("r_")
    if current is None:
        current = AuthSession(user_id=user.id, expires_at=now + timedelta(days=30))
        db.add(current)
    current.access_token_hash = token_hash(access)
    current.refresh_token_hash = token_hash(refresh)
    current.access_expires_at = min(now + timedelta(minutes=15), current.expires_at)
    current.last_seen_at = now
    db.flush()
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=max(0, int((current.access_expires_at - now).total_seconds())),
        user=user_response(user),
    )


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
def register(data: RegisterRequest, request: Request, db: Database):
    limit_request(request, "register", 5)
    user = User(
        email_normalized=str(data.email),
        password_hash=password_hasher.hash(data.password.get_secret_value()),
        registration_source="NATIVE",
        role="USER",
        timezone=data.timezone,
        tracking_start_date=data.tracking_start_date,
    )
    try:
        db.add(user)
        db.flush()
        db.add(UserSettings(user_id=user.id))
        tokens = issue_tokens(db, user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Unable to create an account with these details"
        ) from exc
    return tokens


@router.post("/auth/login", response_model=TokenResponse)
def login(data: Credentials, request: Request, db: Database):
    limit_request(request, "login", 10)
    limiter.check("login:email:" + token_hash(str(data.email)), 10, 300)
    user = db.scalar(select(User).where(User.email_normalized == str(data.email)))
    valid = verify_password(
        data.password.get_secret_value(), user.password_hash if user else None
    )
    if not valid or not login_allowed(user):
        raise unauthorized()
    tokens = issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, request: Request, db: Database):
    limit_request(request, "refresh", 60)
    token = data.refresh_token.get_secret_value()
    if not token.startswith("r_"):
        raise unauthorized()
    current = db.scalar(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == token_hash(token))
        .with_for_update()
    )
    now = datetime.now(UTC)
    if current is None or current.revoked_at is not None or current.expires_at <= now:
        raise unauthorized()
    user = db.get(User, current.user_id)
    if not login_allowed(user):
        raise unauthorized()
    tokens = issue_tokens(db, user, current)
    db.commit()
    return tokens


@router.post("/auth/logout", status_code=204)
def logout(data: RefreshRequest, request: Request, db: Database):
    """Revoke the presented session even when its access token has expired."""
    limit_request(request, "logout", 60)
    token = data.refresh_token.get_secret_value()
    if token.startswith("r_"):
        current = db.scalar(
            select(AuthSession)
            .where(AuthSession.refresh_token_hash == token_hash(token))
            .with_for_update()
        )
        if current is not None and current.revoked_at is None:
            current.revoked_at = datetime.now(UTC)
            db.commit()
    return Response(status_code=204)


def current_user(
    db: Database,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    token = credentials.credentials
    if len(token) != 45 or not token.startswith("a_"):
        raise unauthorized()
    now = datetime.now(UTC)
    user = db.scalar(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.access_token_hash == token_hash(token),
            AuthSession.access_expires_at > now,
            AuthSession.expires_at > now,
            AuthSession.revoked_at.is_(None),
        )
    )
    if not login_allowed(user):
        raise unauthorized()
    return user


def require_admin(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != "ADMIN":
        raise HTTPException(403, "Administrator role required")
    return user


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(current_user)]):
    return user_response(user)
