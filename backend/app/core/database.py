"""
Database connection and session management for SQL Server
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from urllib.parse import quote_plus
from app.core.config import settings
from app.database.schema import Base

_engine = None
_SessionLocal = None


def _build_connection_string() -> str:
    """Build SQL Server connection string from settings (validated)."""
    if not settings.DB_USERNAME or not settings.DB_PASSWORD:
        raise RuntimeError(
            "Database credentials are missing. Set DB_USERNAME and DB_PASSWORD in backend/.env "
            "(use backend/env.example as a template)."
        )
    if not settings.DB_SERVER or not settings.DB_NAME:
        raise RuntimeError(
            "Database server/name are missing. Set DB_SERVER and DB_NAME in backend/.env "
            "(use backend/env.example as a template)."
        )

    return (
        f"mssql+pyodbc://{settings.DB_USERNAME}:{quote_plus(settings.DB_PASSWORD)}"
        f"@{settings.DB_SERVER}/{settings.DB_NAME}"
        f"?driver={quote_plus(settings.DB_DRIVER)}"
        f"&TrustServerCertificate=yes"
    )


def get_engine():
    """Lazy-create SQLAlchemy engine (avoids startup hang / bad creds at import time)."""
    global _engine, _SessionLocal
    if _engine is None:
        connection_string = _build_connection_string()
        _engine = create_engine(
            connection_string,
            echo=settings.DEBUG,
            pool_pre_ping=True,
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        get_engine()
    return _SessionLocal


def get_db() -> Session:
    """Dependency for getting database session"""
    SessionLocal = _get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")


def get_db_url() -> str:
    """Get database connection URL for SQL agent"""
    return _build_connection_string()

