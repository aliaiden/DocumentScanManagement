"""
Database Connection & Session Management
Connects to Azure SQL Server (via pymssql / ODBC) with seamless fallback to SQLite.
"""

import logging
import urllib.parse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.config import settings

logger = logging.getLogger("document_scan_app.database")

Base = declarative_base()

ACTIVE_DB_TYPE = "Unknown"
DB_CONNECTION_ERROR = None


def create_db_engine():
    global ACTIVE_DB_TYPE, DB_CONNECTION_ERROR

    # 1. Check if Azure SQL is configured
    if settings.is_azure_sql_configured():
        try:
            if settings.AZURE_SQL_CONNECTION_STRING:
                conn_str = settings.AZURE_SQL_CONNECTION_STRING
                # If it's an ODBC string, format for SQLAlchemy
                if "Driver=" in conn_str or "DRIVER=" in conn_str:
                    params = urllib.parse.quote_plus(conn_str)
                    db_url = f"mssql+pyodbc:///?odbc_connect={params}"
                else:
                    db_url = conn_str
            else:
                user = urllib.parse.quote_plus(settings.AZURE_SQL_USER or "")
                password = urllib.parse.quote_plus(settings.AZURE_SQL_PASSWORD or "")
                server = settings.AZURE_SQL_SERVER
                port = settings.AZURE_SQL_PORT
                database = settings.AZURE_SQL_DATABASE
                db_url = f"mssql+pymssql://{user}:{password}@{server}:{port}/{database}?charset=utf8"

            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                connect_args={"timeout": 15} if "pymssql" in db_url else {}
            )
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            ACTIVE_DB_TYPE = "Azure SQL Server"
            logger.info(f"Successfully connected to Azure SQL Server: {settings.AZURE_SQL_SERVER}/{settings.AZURE_SQL_DATABASE}")
            return engine
        except Exception as e:
            DB_CONNECTION_ERROR = str(e)
            logger.warning(f"Could not connect to Azure SQL Server: {e}")
            if not settings.FALLBACK_TO_LOCAL_SQLITE:
                raise e

    # 2. Fallback to Local SQLite
    ACTIVE_DB_TYPE = "SQLite (Local Dev Mode)"
    sqlite_path = settings.BASE_DIR / "app_data.db"
    db_url = f"sqlite:///{sqlite_path}"
    logger.info(f"Using SQLite database at {sqlite_path}")
    return create_engine(db_url, connect_args={"check_same_thread": False})


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI Dependency for database session"""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    import backend.models  # Ensure models are imported
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database tables initialized under: {ACTIVE_DB_TYPE}")


# Ensure tables are created upon engine setup
try:
    init_db()
except Exception as _e:
    logger.warning(f"Note: automatic table creation deferred: {_e}")


def get_db_status() -> dict:
    """Return database health & type status"""
    is_azure = "Azure SQL" in ACTIVE_DB_TYPE
    return {
        "active_type": ACTIVE_DB_TYPE,
        "is_azure": is_azure,
        "server": settings.AZURE_SQL_SERVER if is_azure else "Local SQLite File",
        "database": settings.AZURE_SQL_DATABASE if is_azure else "app_data.db",
        "error": DB_CONNECTION_ERROR if not is_azure and settings.is_azure_sql_configured() else None,
        "configured_in_env": settings.is_azure_sql_configured()
    }
