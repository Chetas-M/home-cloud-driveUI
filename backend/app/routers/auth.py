"""
Home Cloud Drive - Authentication Router
"""
from datetime import timedelta
from urllib.parse import urljoin
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.limiter import limiter
from app.models import User
from app.schemas import (
    UserCreate,
    UserResponse,
    UserLogin,
    Token,
    PasswordChange,
    ForgotPasswordRequest,
    ResetPasswordConfirm,
)
from app.auth import (
    get_password_hash,
    create_access_token,
    create_password_reset_token,
    get_current_user,
    get_user_by_email,
    get_user_by_username,
    authenticate_user,
    verify_password_reset_token,
)
from app.config import get_settings
from app.email import send_password_reset_email
from anyio import to_thread

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


async def send_password_reset_email_async(email: str, username: str, reset_url: str) -> None:
    """Run the blocking password reset email sender in a thread pool."""
    await to_thread.run_sync(send_password_reset_email, email, username, reset_url)


def build_password_reset_url(request: Request, token: str) -> str:
    """Build the frontend password reset URL from config or the current request."""
    if settings.password_reset_url:
        base_url = settings.password_reset_url
    else:
        # Fallback to the server-controlled base URL derived from the request,
        # and do not trust client-controlled headers like Origin.
        base_url = str(request.base_url).rstrip("/")
    return f"{urljoin(base_url.rstrip('/') + '/', '')}?reset_token={token}"

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(request: Request, user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user"""
    # Check if registration is enabled
    if not settings.allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled. Contact administrator for access."
        )
    
    # Check if email already exists
    existing_email = await get_user_by_email(db, user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username already exists
    existing_username = await get_user_by_username(db, user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create new user
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
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """Login and get access token"""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )
    
    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return current_user


@router.patch("/password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change the current user's password"""
    from app.auth import verify_password

    # Verify current password
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Prevent reusing the same password
    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
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

    return {
        "detail": "If an account exists for that email, a password reset link has been sent."
    }


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

    from app.auth import verify_password

    if verify_password(data.new_password, result.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from your current password",
        )

    result.password_hash = get_password_hash(data.new_password)

    return {"detail": "Password reset successfully. You can now sign in."}

