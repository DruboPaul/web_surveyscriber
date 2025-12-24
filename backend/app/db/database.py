"""
Flexible Database Engine - SQLite Default + Optional External Database

Supports:
- SQLite (default, zero config) - stored in ~/.surveyscriber/history.db
- PostgreSQL (optional) - postgresql://user:pass@host:5432/dbname
- MySQL (optional) - mysql://user:pass@host:3306/dbname
"""

import os
import json
from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Settings file location (same as routes_settings.py)
SETTINGS_DIR = Path.home() / ".surveyscriber"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
DEFAULT_SQLITE_PATH = SETTINGS_DIR / "history.db"

Base = declarative_base()

# Global engine and session (lazy initialized)
_engine = None
_SessionLocal = None


def get_settings_database_url() -> str:
    """Load database_url from settings file if configured."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
                return settings.get("database_url", "")
        except (json.JSONDecodeError, IOError):
            pass
    return ""


def get_database_url() -> str:
    """
    Get the database URL to use.
    Priority:
    1. database_url from settings (if configured)
    2. Default SQLite database
    """
    # Check settings for external database
    settings_url = get_settings_database_url()
    if settings_url and settings_url.strip():
        return settings_url.strip()
    
    # Default: SQLite in user's home directory
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_SQLITE_PATH}"


def create_db_engine(database_url: str = None):
    """Create SQLAlchemy engine with appropriate settings for the database type."""
    if database_url is None:
        database_url = get_database_url()
    
    # Configure engine based on database type
    if database_url.startswith("sqlite"):
        # SQLite-specific settings
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},  # Allow multi-threaded access
            future=True
        )
        # Enable foreign keys for SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    else:
        # PostgreSQL/MySQL settings
        engine = create_engine(database_url, future=True, pool_pre_ping=True)
    
    return engine


def get_engine():
    """Get or create the database engine (lazy initialization)."""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_local():
    """Get or create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def reset_engine():
    """Reset engine and session (call when database_url changes in settings)."""
    global _engine, _SessionLocal
    if _engine:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def init_database():
    """Initialize database tables."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    print(f"[OK] Database initialized: {get_database_url()}")


def test_connection(database_url: str = None) -> dict:
    """Test database connection and return status."""
    try:
        url = database_url or get_database_url()
        test_engine = create_db_engine(url)
        
        # Try to connect
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        test_engine.dispose()
        
        # Determine database type
        if url.startswith("sqlite"):
            db_type = "SQLite"
        elif url.startswith("postgresql"):
            db_type = "PostgreSQL"
        elif url.startswith("mysql"):
            db_type = "MySQL"
        else:
            db_type = "Unknown"
        
        return {
            "success": True,
            "message": f"Connected to {db_type} successfully",
            "database_type": db_type,
            "url_masked": mask_database_url(url)
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection failed: {str(e)}",
            "database_type": None,
            "url_masked": None
        }


def mask_database_url(url: str) -> str:
    """Mask sensitive parts of database URL for display."""
    if not url:
        return ""
    if url.startswith("sqlite"):
        return url
    # Mask password in URL: postgresql://user:password@host -> postgresql://user:***@host
    try:
        if "@" in url and ":" in url:
            prefix, rest = url.split("://", 1)
            if "@" in rest:
                auth, host = rest.rsplit("@", 1)
                if ":" in auth:
                    user, _ = auth.split(":", 1)
                    return f"{prefix}://{user}:***@{host}"
        return url
    except:
        return "***"


# Legacy compatibility - these are used by existing code
def get_legacy_engine():
    """Legacy: Get engine for backwards compatibility."""
    return get_engine()


# For backwards compatibility with existing imports
engine = property(lambda self: get_engine())
SessionLocal = property(lambda self: get_session_local())
