# Database session management

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_db_and_tables():
    # This function will be called on startup to create tables if they don't exist
    print(f"DIAGNOSTIC_LOG: DATABASE_URL from settings: {settings.DATABASE_URL}")
    print(f"DIAGNOSTIC_LOG: SCHEDULER_DATABASE_URL from settings: {settings.SCHEDULER_DATABASE_URL}")
    # Also print directly from environment variables for comparison, if they exist
    db_url_env = os.getenv("DATABASE_URL")
    scheduler_db_url_env = os.getenv("SCHEDULER_DATABASE_URL")
    print(f"DIAGNOSTIC_LOG: DATABASE_URL from os.getenv: {db_url_env}")
    print(f"DIAGNOSTIC_LOG: SCHEDULER_DATABASE_URL from os.getenv: {scheduler_db_url_env}")
    Base.metadata.create_all(bind=engine)

