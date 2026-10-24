"""Authentication API routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.models import User
from backend.app.schemas.schemas import LoginRequest, TokenResponse, UserResponse
from backend.app.services.auth import authenticate_user, create_access_token, get_current_user
from backend.app.utils.audit import log_action

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return JWT bearer token."""
    user = authenticate_user(db, payload.email.strip().lower(), payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    token = create_access_token(user_id=user.id, role=user.role.value)
    log_action(db, user_id=user.id, action="login", entity="user", entity_id=user.id)
    db.commit()
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return currently authenticated user profile."""
    return current_user
