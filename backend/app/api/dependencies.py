from sqlalchemy.orm import Session
from fastapi import Depends
from app.database.database import get_db

# We can re-export or add standard API-wide dependencies here.
# For example, if we need standard user authentication dependencies in the future.
