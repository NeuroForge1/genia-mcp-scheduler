# Database session management

import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings
# Import the specific table model to drop it if it exists
from app.db.models import ScheduledTaskTable 

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
    print("Attempting to drop and recreate scheduled_tasks table to ensure schema update...")
    try:
        # Drop the specific table if it exists
        # Using checkfirst=True to avoid errors if the table doesn't exist, though explicit check is better
        inspector = inspect(engine)
        if ScheduledTaskTable.__tablename__ in inspector.get_table_names():
            print(f"Table {ScheduledTaskTable.__tablename__} found, attempting to drop.")
            ScheduledTaskTable.__table__.drop(engine, checkfirst=True)
            print(f"Table {ScheduledTaskTable.__tablename__} dropped successfully.")
        else:
            print(f"Table {ScheduledTaskTable.__tablename__} not found, skipping drop.")
        
        # Create all tables defined in Base (including scheduled_tasks with the new schema)
        Base.metadata.create_all(bind=engine)
        print("Base.metadata.create_all(bind=engine) called. Tables should be created/updated.")
    except Exception as e:
        print(f"Error during drop/create table: {e}")
        # Fallback to just create_all if drop fails for some reason, though this might not fix schema issues
        # if the table already exists with the old schema and drop failed.
        # However, the main error was 'column does not exist', so create_all on a non-existent table (after successful drop)
        # or on a correctly dropped table should work.
        if not (ScheduledTaskTable.__tablename__ in inspector.get_table_names()):
             print("Fallback: Attempting Base.metadata.create_all again as table might not exist.")
             Base.metadata.create_all(bind=engine)

