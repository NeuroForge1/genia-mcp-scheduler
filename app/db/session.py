# Database session management

import os
from sqlalchemy import create_engine, text # Added text for raw SQL
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings
# DO NOT import ScheduledTaskTable from app.db.models here to avoid circular import

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base() # This Base should be imported by app.db.models

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_db_and_tables():
    # The temporary logic for DROP TYPE and DROP TABLE has been removed.
    # Now, only Base.metadata.create_all(bind=engine) will be called.
    # This will create tables if they don't exist, but will not drop them
    # or their types on subsequent runs, preserving data.
    print("Attempting Base.metadata.create_all(bind=engine) to create tables if they do not exist...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Base.metadata.create_all(bind=engine) called. Tables should be created if they didn't exist.")
    except Exception as e:
        print(f"Error during Base.metadata.create_all(bind=engine): {e}")
        # Depending on the error, you might want to log it or handle it specifically.
        # For now, just printing the error.

