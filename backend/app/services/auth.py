"""Authentication service: password hashing, JWT, dependencies."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import defaultdict, deque
import threading
import time
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.models.models import User, UserRole

security = HTTPBearer(auto_error=False)
_login_failures: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_login_lock = threading.Lock()
LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60
LOGIN_LOCKOUT_SECONDS = 15 * 60


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    pwd_bytes = password.encode("utf-8")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    if len(pwd_bytes) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password using bcrypt."""
    pwd_bytes = plain.encode("utf-8")
    if len(pwd_bytes) > 72:
        return False
    hashed_bytes = hashed.encode("utf-8")
    try:
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(user_id: str, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def login_lockout_remaining(email: str, client_ip: str, now: float | None = None) -> int:
    """Return seconds remaining in an IP/email lockout, or zero if unlocked."""
    timestamp = time.monotonic() if now is None else now
    key = (client_ip, email.strip().casefold())
    with _login_lock:
        failures = _login_failures[key]
        while failures and timestamp - failures[0] >= LOGIN_FAILURE_WINDOW_SECONDS:
            failures.popleft()
        if len(failures) < LOGIN_FAILURE_LIMIT:
            return 0
        remaining = LOGIN_LOCKOUT_SECONDS - (timestamp - failures[-1])
        if remaining <= 0:
            failures.clear()
            return 0
        return max(1, int(remaining))


def record_login_failure(email: str, client_ip: str, now: float | None = None) -> None:
    timestamp = time.monotonic() if now is None else now
    key = (client_ip, email.strip().casefold())
    with _login_lock:
        failures = _login_failures[key]
        while failures and timestamp - failures[0] >= LOGIN_FAILURE_WINDOW_SECONDS:
            failures.popleft()
        failures.append(timestamp)


def clear_login_failures(email: str, client_ip: str) -> None:
    with _login_lock:
        _login_failures.pop((client_ip, email.strip().casefold()), None)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(*roles: UserRole):
    """FastAPI dependency factory for role-based access control."""
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(r.value for r in roles)}",
            )
        return current_user
    return role_checker
