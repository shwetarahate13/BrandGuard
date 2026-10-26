"""Authentication API routes."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import User
from backend.app.schemas.schemas import DemoLoginRequest, LoginRequest, PasswordChangeRequest, TokenResponse, UserResponse
from backend.app.services.auth import (
    authenticate_user,
    clear_login_failures,
    create_access_token,
    get_current_user,
    login_lockout_remaining,
    record_login_failure,
    verify_password,
    hash_password,
)
from backend.app.config import get_settings
from backend.app.utils.audit import log_action

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate user and return JWT bearer token."""
    email = payload.email.strip().lower()
    client_ip = request.client.host if request.client else "unknown"
    lockout_remaining = login_lockout_remaining(email, client_ip)
    if lockout_remaining:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts. Try again later.",
            headers={"Retry-After": str(lockout_remaining)},
        )
    user = authenticate_user(db, email, payload.password)
    if not user:
        record_login_failure(email, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        record_login_failure(email, client_ip)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    clear_login_failures(email, client_ip)
    token = create_access_token(user_id=user.id, role=user.role.value)
    log_action(db, user_id=user.id, action="login", entity="user", entity_id=user.id)
    db.commit()
    return TokenResponse(access_token=token, token_type="bearer")


@router.post("/demo-login", response_model=TokenResponse)
def demo_login(payload: DemoLoginRequest, db: Session = Depends(get_db)):
    """Issue a demo account token only when demo mode is explicitly enabled."""
    if not get_settings().DEMO_MODE:
        raise HTTPException(status_code=404, detail="Not found")
    demo_emails = {
        "creator": "creator@nexora.dev",
        "manager": "manager@nexora.dev",
        "reviewer": "reviewer@nexora.dev",
        "admin": "admin@nexora.dev",
    }
    user = db.query(User).filter(User.email == demo_emails[payload.role], User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=503, detail="Demo users have not been seeded on this instance")
    return TokenResponse(access_token=create_access_token(user.id, user.role.value))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return currently authenticated user profile."""
    return current_user


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change the authenticated user's password after verifying the current one."""
    user = db.query(User).filter(User.id == current_user.id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User account is unavailable")
    if get_settings().DEMO_MODE and user.email in {
        "creator@nexora.dev", "manager@nexora.dev", "reviewer@nexora.dev", "admin@nexora.dev",
    }:
        raise HTTPException(status_code=403, detail="Shared demo account passwords cannot be changed")
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="Choose a new password different from the current password")

    user.password_hash = hash_password(payload.new_password)
    log_action(db, user_id=user.id, action="change_password", entity="user", entity_id=user.id)
    db.commit()
    return {"status": "ok", "message": "Password changed successfully"}
