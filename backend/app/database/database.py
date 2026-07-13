import os
import logging
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

logger = logging.getLogger("app.database")

# Extract the database URL
db_url = settings_db_url = None

# Let's import settings dynamically or directly
from app.core.config import settings
db_url = settings.DATABASE_URL

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if db_url and db_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Ensure the database directory exists if using SQLite
if db_url.startswith("sqlite:///"):
    db_path = db_url.replace("sqlite:///", "")
    # Handle paths like ./data/assistant.db
    db_dir = os.path.dirname(os.path.abspath(db_path))
    if db_dir and not os.path.exists(db_dir):
        logger.info(f"Creating database folder at: {db_dir}")
        os.makedirs(db_dir, exist_ok=True)

# SQLite multi-thread connection arguments
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """Safely creates all database tables defined in models."""
    logger.info("Initializing database schemas...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schemas initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def check_db_connection() -> bool:
    """Verifies connection to the database by executing a simple query."""
    try:
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return True
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Database connectivity check failed: {e}")
        return False
