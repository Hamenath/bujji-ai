import pytest
from sqlalchemy import text
from app.database.database import engine, init_db, check_db_connection
from app.database.models import SystemCheck

def test_database_connection():
    """Verifies that the SQLAlchemy engine can establish a connection and run SELECT 1."""
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar()
        assert result == 1

def test_check_db_connection_helper():
    """Verifies that our check_db_connection helper functions correctly under healthy conditions."""
    assert check_db_connection() is True

def test_database_initialization():
    """Verifies that running database initialization does not throw any exceptions."""
    try:
        init_db()
    except Exception as e:
        pytest.fail(f"init_db() crashed with exception: {e}")

def test_database_crud_operations(db_session):
    """Verifies that we can insert and retrieve records using the declarative models."""
    # Create
    db_record = SystemCheck(status="test_healthy")
    db_session.add(db_record)
    db_session.commit()
    db_session.refresh(db_record)
    
    assert db_record.id is not None
    assert db_record.status == "test_healthy"
    assert db_record.checked_at is not None

    # Read
    queried_record = db_session.query(SystemCheck).filter(SystemCheck.id == db_record.id).first()
    assert queried_record is not None
    assert queried_record.status == "test_healthy"
