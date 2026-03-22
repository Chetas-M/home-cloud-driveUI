"""
Home Cloud Drive - Authentication Router
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from anyio import to_thread
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    authenticate_user,
    build_totp_uri,
    create_access_token,
    create_password_reset_token,
    create_temporary_login_token,
    generate_totp_secret,
    get_current_user,
    get_password_hash,
    get_session_by_id,
    get_user_by_email,
    get_user_by_username,
    verify_password,
    verify_password_reset_token,
    verify_temporary_login_token,
    verify_totp_code,
)
from app.config import get_settings
from app.database import get_db
from app.email import send_login_alert_email, send_password_reset_email
from app.limiter import limiter
from app.models import User, UserSession
from app.schemas import (
    ForgotPasswordRequest,
    PasswordChange,
    ResetPasswordConfirm,
    SessionResponse,
    Token,
    TwoFactorDisableRequest,
    TwoFactorEnableRequest,
    TwoFactorLoginRequest,
    TwoFactorSetupResponse,
    UserCreate,
    UserResponse,
)

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


async def send_password_reset_email_async(email: str, username: str, reset_url: str) -> None:
    """Run the blocking password reset email sender in a thread pool."""
    await to_thread.run_sync(send_password_reset_email, email, username, reset_url)


async def send_login_alert_email_async(
    email: str,
    username: str,
    device_name: str,
    ip_address: str,
    login_time: datetime,
    is_suspicious: bool,
) -> None:
    """Run the blocking login alert sender in a thread pool."""
    await to_thread.run_sync(
        send_login_alert_email,
        email,
        username,
        device_name,
        ip_address,
        login_time,
        is_suspicious,
    )


def build_password_reset_url(request: Request, token: str) -> str:
    """Build the frontend password reset URL from config or the current request."""
    if settings.password_reset_url:
        base_url = settings.password_reset_url
    else:
        # Fallback to the server-controlled base URL derived from the request,
        # and do not trust client-controlled headers like Origin.
        base_url = str(request.base_url).rstrip("/")
    return f"{urljoin(base_url.rstrip('/') + '/', '')}?reset_token={token}"


def get_client_ip(request: Request) -> str:
    """Extract the most useful client IP available for session tracking."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "Unknown IP"


def describe_device(user_agent: str | None) -> str:
    """Build a compact device label from the user-agent string."""
    if not user_agent:
        return "Unknown device"

    agent = user_agent.lower()
    browser = "Browser"
    platform = "Unknown OS"

    if "edg" in agent:
        browser = "Edge"
    elif "chrome" in agent and "edg" not in agent:
        browser = "Chrome"
    elif "firefox" in agent:
        browser = "Firefox"
    elif "safari" in agent and "chrome" not in agent:
        browser = "Safari"

    if "windows" in agent:
        platform = "Windows"
    elif "iphone" in agent or "ipad" in agent or "ios" in agent:
        platform = "iOS"
    elif "android" in agent:
        platform = "Android"
    elif "mac os x" in agent or "macintosh" in agent:
        platform = "macOS"
    elif "linux" in agent:
        platform = "Linux"

    return f"{browser} on {platform}"


async def create_user_session(
    request: Request,
    user: User,
    db: AsyncSession,
    background_tasks: BackgroundTasks | None = None,
) -> Token:
    """Create a tracked session and return the access token payload."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    user_agent = request.headers.get("user-agent", "")
    ip_address = get_client_ip(request)
    device_name = describe_device(user_agent)

    previous_known_result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
            UserSession.ip_address == ip_address,
            UserSession.device_name == device_name,
        )
    )
    is_suspicious = previous_known_result.scalars().first() is None

    session = UserSession(
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        device_name=device_name,
        created_at=now,
        last_seen_at=now,
        expires_at=expires_at,
        is_suspicious=is_suspicious,
    )
    db.add(session)
    await db.flush()

    access_token = create_access_token(
        data={"sub": user.id, "sid": session.id},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    if settings.smtp_enabled and background_tasks is not None:
        background_tasks.add_task(
            send_login_alert_email_async,
            user.email,
            user.username,
            device_name,
            ip_address,
            now,
            is_suspicious,
        )

    return Token(access_token=access_token)


def build_session_response(session: UserSession, current_session_id: str | None) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        ip_address=session.ip_address,
        user_agent=session.user_agent,
        device_name=session.device_name,
        created_at=session.created_at,
        last_seen_at=session.last_seen_at,
        expires_at=session.expires_at,
        revoked_at=session.revoked_at,
        is_suspicious=session.is_suspicious,
        is_current=session.id == current_session_id,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(request: Request, user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    if not settings.allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled. Contact administrator for access.",
        )

    existing_email = await get_user_by_email(db, user_data.email)
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    existing_username = await get_user_by_username(db, user_data.username)
    if existing_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    new_user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        storage_quota=settings.max_storage_bytes,
    )

    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login(
    request: Request,
    background_tasks: BackgroundTasks,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Login and get access token or a 2FA challenge."""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.two_factor_enabled:
        return Token(
            requires_2fa=True,
            temporary_token=create_temporary_login_token(user.id),
        )

    return await create_user_session(request, user, db, background_tasks)


@router.post("/login/2fa", response_model=Token)
@limiter.limit("10/minute")
async def login_with_two_factor(
    request: Request,
    payload: TwoFactorLoginRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Complete a login challenge with a valid TOTP code."""
    user_id = verify_temporary_login_token(payload.temporary_token)
    user = await db.get(User, user_id)

    if not user or not user.two_factor_enabled or not user.two_factor_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA is not enabled for this account")

    if not verify_totp_code(user.two_factor_secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid 2FA code")

    return await create_user_session(request, user, db, background_tasks)


async def get_current_session_id(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> str | None:
    """
    Extract the current session ID from the validated access token.

    Relies on get_current_user to ensure the request is authenticated,
    then decodes the JWT to retrieve the 'sid' claim. Returns None for
    legacy tokens that pre-date session tracking.
    """
    from jose import jwt

    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "", 1).strip()

    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    return payload.get("sid")


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    session_id: str | None = Depends(get_current_session_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the current session."""
    if session_id is not None:
        session = await get_session_by_id(db, session_id, current_user.id)
        if session and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)

    return {"detail": "Signed out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info."""
    return current_user


@router.get("/sessions", response_model=list[SessionResponse])
async def get_sessions(
    current_user: User = Depends(get_current_user),
    current_session_id: str | None = Depends(get_current_session_id),
    db: AsyncSession = Depends(get_db),
):
    """Return active and recent sessions for the current user."""
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == current_user.id)
        .order_by(desc(UserSession.last_seen_at))
    )
    sessions = result.scalars().all()
    return [build_session_response(session, current_session_id) for session in sessions]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke one of the current user's sessions."""
    session = await get_session_by_id(db, session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)

    return {"detail": "Session revoked"}


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_two_factor(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or refresh a pending TOTP secret for the current user."""
    if current_user.two_factor_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA is already enabled")

    current_user.two_factor_pending_secret = generate_totp_secret()
    await db.flush()

    return TwoFactorSetupResponse(
        secret=current_user.two_factor_pending_secret,
        otpauth_url=build_totp_uri(current_user.two_factor_pending_secret, current_user.email),
    )


@router.post("/2fa/enable", response_model=UserResponse)
async def enable_two_factor(
    payload: TwoFactorEnableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enable TOTP-based 2FA after confirming the setup code."""
    pending_secret = current_user.two_factor_pending_secret
    if not pending_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start 2FA setup before verifying a code")

    if not verify_totp_code(pending_secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid 2FA code")

    current_user.two_factor_secret = pending_secret
    current_user.two_factor_pending_secret = None
    current_user.two_factor_enabled = True
    await db.flush()
    await db.refresh(current_user)
    return current_user


@router.post("/2fa/disable", response_model=UserResponse)
async def disable_two_factor(
    payload: TwoFactorDisableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable 2FA after verifying password and current TOTP code."""
    if not current_user.two_factor_enabled or not current_user.two_factor_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA is not enabled")

    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    if not verify_totp_code(current_user.two_factor_secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid 2FA code")

    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    current_user.two_factor_pending_secret = None
    await db.flush()
    await db.refresh(current_user)
    return current_user


@router.patch("/password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    current_user.password_hash = get_password_hash(data.new_password)
    await db.flush()

    return {"detail": "Password changed successfully"}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Send a password reset link to the user if reset email is configured."""
    if not settings.password_reset_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email is not configured for this server",
        )

    user = await get_user_by_email(db, data.email)
    if user:
        token = create_password_reset_token(user.id)
        reset_url = build_password_reset_url(request, token)
        background_tasks.add_task(
            send_password_reset_email_async,
            user.email,
            user.username,
            reset_url,
        )

    return {"detail": "If an account exists for that email, a password reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    data: ResetPasswordConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Reset a user's password using a valid password reset token."""
    user_id = verify_password_reset_token(data.token)

    result = await db.get(User, user_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset link",
        )

    if verify_password(data.new_password, result.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from your current password",
        )

    result.password_hash = get_password_hash(data.new_password)

    return {"detail": "Password reset successfully. You can now sign in."}
