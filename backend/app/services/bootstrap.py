"""One-time creation of the first real workspace administrator."""
import re

from sqlalchemy.orm import Session

from backend.app.models.models import User, UserRole
from backend.app.services.auth import hash_password


def create_initial_admin(db: Session, name: str, email: str, password: str) -> User:
    """Create an admin only when no account exists in the migrated database."""
    if db.query(User.id).first() is not None:
        raise ValueError("Initial admin setup is only allowed when the database has no users")

    normalized_name = name.strip()
    normalized_email = email.strip().lower()
    if not normalized_name:
        raise ValueError("Name is required")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
        raise ValueError("Enter a valid email address")

    user = User(
        name=normalized_name,
        email=normalized_email,
        password_hash=hash_password(password),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
