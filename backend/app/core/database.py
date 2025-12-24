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

# Knowledge Base Database (Regulatory Data Mart) connections
_kb_engine = None
_KB_SessionLocal = None


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


def _build_kb_connection_string() -> str:
    """Build SQL Server connection string for Knowledge Base database (regulatory data mart)."""
    # Use KB-specific settings if provided, otherwise fall back to main DB settings
    kb_server = settings.KB_DB_SERVER or settings.DB_SERVER
    kb_name = settings.KB_DB_NAME or settings.DB_NAME
    kb_username = settings.KB_DB_USERNAME or settings.DB_USERNAME
    kb_password = settings.KB_DB_PASSWORD or settings.DB_PASSWORD
    kb_driver = settings.KB_DB_DRIVER or settings.DB_DRIVER
    
    if not kb_username or not kb_password:
        raise RuntimeError(
            "Knowledge Base database credentials are missing. Set KB_DB_USERNAME and KB_DB_PASSWORD "
            "(or DB_USERNAME and DB_PASSWORD) in backend/.env"
        )
    if not kb_server or not kb_name:
        raise RuntimeError(
            "Knowledge Base database server/name are missing. Set KB_DB_SERVER and KB_DB_NAME "
            "(or DB_SERVER and DB_NAME) in backend/.env"
        )

    return (
        f"mssql+pyodbc://{kb_username}:{quote_plus(kb_password)}"
        f"@{kb_server}/{kb_name}"
        f"?driver={quote_plus(kb_driver)}"
        f"&TrustServerCertificate=yes"
    )


def get_kb_engine():
    """Lazy-create SQLAlchemy engine for Knowledge Base database (regulatory data mart)."""
    global _kb_engine, _KB_SessionLocal
    if _kb_engine is None:
        connection_string = _build_kb_connection_string()
        _kb_engine = create_engine(
            connection_string,
            echo=settings.DEBUG,
            pool_pre_ping=True,
        )
        _KB_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_kb_engine)
    return _kb_engine


def _get_kb_session_factory():
    """Get session factory for Knowledge Base database."""
    global _KB_SessionLocal
    if _KB_SessionLocal is None:
        get_kb_engine()
    return _KB_SessionLocal


def get_kb_db() -> Session:
    """Dependency for getting Knowledge Base database session (regulatory data mart)."""
    SessionLocal = _get_kb_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_kb_db_url() -> str:
    """Get Knowledge Base database connection URL."""
    return _build_kb_connection_string()

