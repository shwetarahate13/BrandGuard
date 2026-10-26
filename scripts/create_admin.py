"""Interactively create the first real admin after running Alembic migrations."""
import getpass

from backend.app.database import get_session_factory
from backend.app.models.models import User
from backend.app.services.bootstrap import create_initial_admin


def main() -> None:
    session_factory = get_session_factory()
    with session_factory() as db:
        if db.query(User.id).first() is not None:
            raise SystemExit("Admin bootstrap refused: this database already has users.")

        print("Create the first BrandGuard administrator. Password input is hidden.")
        name = input("Admin name: ").strip()
        email = input("Admin email: ").strip()
        password = getpass.getpass("Password (12+ characters): ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise SystemExit("Passwords did not match; no account was created.")

        try:
            admin = create_initial_admin(db, name, email, password)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

        print(f"Created initial admin account for {admin.email}.")


if __name__ == "__main__":
    main()
