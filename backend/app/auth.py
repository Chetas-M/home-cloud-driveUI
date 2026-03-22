"""
Home Cloud Drive - Authentication Utilities
"""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database import get_db
from app.models import User, UserSession
from app.schemas import TokenData

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def create_temporary_login_token(user_id: str) -> str:
    """Create a short-lived token used to complete a 2FA login challenge."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.two_factor_temp_token_expire_minutes)
    payload = {
        "sub": user_id,
        "type": "login_2fa",
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def verify_temporary_login_token(token: str) -> str:
    """Validate a temporary 2FA login token and return the user id."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired 2FA challenge",
        ) from exc

    if payload.get("type") != "login_2fa":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA challenge",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2FA challenge",
        )

    return user_id


def create_password_reset_token(user_id: str) -> str:
    """Create a short-lived password reset token for a user."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_expire_minutes)
    payload = {
        "sub": user_id,
        "type": "password_reset",
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def generate_totp_secret() -> str:
    """Generate a Base32-encoded TOTP secret."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def build_totp_uri(secret: str, email: str) -> str:
    """Build an otpauth URI compatible with authenticator apps."""
    issuer = "Home Cloud"
    label = f"{issuer}:{email}"
    return (
        f"otpauth://totp/{quote(label)}"
        f"?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    )


def _normalize_base32_secret(secret: str) -> bytes:
    normalized = secret.strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    return base64.b32decode(normalized + padding, casefold=True)


def _generate_totp_at(secret: str, for_time: datetime, interval_seconds: int = 30) -> str:
    counter = int(for_time.timestamp()) // interval_seconds
    key = _normalize_base32_secret(secret)
    counter_bytes = counter.to_bytes(8, "big")
    digest = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = (
        ((digest[offset] & 0x7F) << 24)
        | (digest[offset + 1] << 16)
        | (digest[offset + 2] << 8)
        | digest[offset + 3]
    )
    return str(binary % 1_000_000).zfill(6)


def verify_totp_code(secret: str, code: str, valid_window: int = 1) -> bool:
    """Verify a 6-digit TOTP code with a small time window for clock skew."""
    sanitized = "".join(ch for ch in code if ch.isdigit())
    if len(sanitized) != 6:
        return False

    now = datetime.now(timezone.utc)
    for offset in range(-valid_window, valid_window + 1):
        candidate_time = now + timedelta(seconds=offset * 30)
        if hmac.compare_digest(_generate_totp_at(secret, candidate_time), sanitized):
            return True
    return False


def verify_password_reset_token(token: str) -> str:
    """Validate a password reset token and return the user id."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset link",
        ) from exc

    if payload.get("type") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset link",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset link",
        )

    return user_id


async def _get_jwt_payload(
    token: str = Depends(oauth2_scheme),
) -> dict:
    """Decode the JWT and return its payload; raises 401 on invalid tokens."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        raise credentials_exception


async def get_current_session_id(
    payload: dict = Depends(_get_jwt_payload),
) -> str:
    """Extract and return the session ID from the current JWT payload."""
    session_id: str = payload.get("sid")
    if session_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session_id


async def get_current_user(
    payload: dict = Depends(_get_jwt_payload),
    session_id: str = Depends(get_current_session_id),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    token_data = TokenData(user_id=user_id)

    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    session_result = await db.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == user.id,
        )
    )
    current_session = session_result.scalar_one_or_none()

    if current_session is None or current_session.revoked_at is not None:
        raise credentials_exception

    if current_session.expires_at <= datetime.now(timezone.utc):
        raise credentials_exception

    current_session.last_seen_at = datetime.now(timezone.utc)
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def get_session_by_id(db: AsyncSession, session_id: str, user_id: str) -> Optional[UserSession]:
    result = await db.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that requires the current user to be an admin"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
