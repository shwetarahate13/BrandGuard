"""Database engine and session management."""
import logging
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from backend.app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is not None:
        return _engine

    settings = get_settings()
    url = settings.database_url_sync

    connect_args = {}
    kwargs = {}

    if settings.is_sqlite:
        connect_args["check_same_thread"] = False
        kwargs["pool_pre_ping"] = True
    else:
        # PostgreSQL connection pooling for local or remote servers.
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 2
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 300
    # Retry a transient database connection failure before reporting startup failure.
    max_retries = 3
    for attempt in range(max_retries):
        try:
            _engine = create_engine(url, connect_args=connect_args, **kwargs)
            with _engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection established")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(f"DB connection attempt {attempt + 1} failed, retrying in {wait}s: {e}")
                time.sleep(wait)
            else:
                logger.error(f"Could not connect to database after {max_retries} attempts")
                raise

    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal


def get_db():
    """FastAPI dependency that yields a DB session."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
