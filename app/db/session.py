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
    # This function will be called on startup to create tables if they don't exist
    print("Attempting to drop and recreate scheduled_tasks table (using raw SQL to avoid circular import) to ensure schema update...")
    try:
        with engine.connect() as connection:
            # Drop the table using raw SQL if it exists
            # Using CASCADE to handle potential foreign key constraints if any were added, though unlikely for this table
            # For PostgreSQL, IF EXISTS is standard. For SQLite, this might behave differently or require specific pragmas if strict.
            # Given Render uses PostgreSQL, this should be fine.
            drop_command = text("DROP TABLE IF EXISTS scheduled_tasks CASCADE;")
            connection.execute(drop_command)
            connection.commit() # Explicitly commit DDL for some DBs/drivers
            print(f"Raw SQL executed: DROP TABLE IF EXISTS scheduled_tasks CASCADE;")
        
        # Create all tables defined in Base (including scheduled_tasks with the new schema)
        # This Base.metadata should now contain the updated ScheduledTaskTable definition from models.py
        Base.metadata.create_all(bind=engine)
        print("Base.metadata.create_all(bind=engine) called. Tables should be created/updated.")
    except Exception as e:
        print(f"Error during drop/create table with raw SQL: {e}")
        # Fallback: If drop failed but table might not exist, try create_all again.
        # This is less likely to be needed if DROP IF EXISTS works as expected.
        print("Fallback: Attempting Base.metadata.create_all again.")
        Base.metadata.create_all(bind=engine)

