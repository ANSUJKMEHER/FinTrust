from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

database_url = settings.SQLALCHEMY_DATABASE_URI

connect_args = {}
engine_kwargs = {
    "connect_args": connect_args,
    "pool_pre_ping": True,
    "echo": settings.DEBUG
}

if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
else:
    # Transaction pooling & PgBouncer hardening
    # 1. Disable server-side named prepared statements in psycopg2 to avoid
    #    "prepared statement does not exist" or statement collision errors across pooled transactions
    connect_args["prepare_threshold"] = None

    # 2. Reset connection on return to pool to ensure uncommitted transactions do not bleed
    engine_kwargs["pool_reset_on_return"] = "rollback"

    # 3. Connection pool sizing
    engine_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE
    })

engine = create_engine(
    database_url,
    **engine_kwargs
)

# Enforce foreign key constraints on SQLite connections for robust testing
if database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields an active database session and guarantees closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
