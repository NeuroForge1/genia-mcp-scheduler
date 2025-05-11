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
    print("Attempting to update ENUM type and recreate scheduled_tasks table...")
    try:
        with engine.connect() as connection:
            # 1. Attempt to ALTER TYPE to add 'email'. 
            # This should be idempotent or handle errors if the value already exists.
            # PostgreSQL will raise an error if the type doesn't exist, or if the value already exists.
            # We will try to add it, and if it fails because it exists, that's okay.
            # If it fails because the TYPE doesn't exist, create_all below should handle it.
            try:
                alter_enum_command = text("ALTER TYPE targetplatform ADD VALUE IF NOT EXISTS 'email';") # IF NOT EXISTS is for PG 9.6+
                # For older PG or more robust, might need to query pg_enum first or catch specific exception
                # Render likely uses a recent PG version.
                print(f"Attempting to execute: {alter_enum_command}")
                connection.execute(alter_enum_command)
                connection.commit()
                print("ALTER TYPE targetplatform ADD VALUE IF NOT EXISTS 'email' executed.")
            except Exception as e_alter:
                print(f"Notice: Could not execute ALTER TYPE targetplatform ADD VALUE IF NOT EXISTS 'email': {e_alter}. This might be okay if the type or value already exists, or if the type will be created by create_all.")
                # Rollback any transaction that might have started due to the error
                if connection.in_transaction():
                    connection.rollback()

            # 2. Drop the table using raw SQL if it exists
            drop_command = text("DROP TABLE IF EXISTS scheduled_tasks CASCADE;")
            print(f"Attempting to execute: {drop_command}")
            connection.execute(drop_command)
            connection.commit()
            print(f"Raw SQL executed: DROP TABLE IF EXISTS scheduled_tasks CASCADE;")
        
        # 3. Create all tables defined in Base (including scheduled_tasks with the new schema)
        # This Base.metadata should now contain the updated ScheduledTaskTable definition from models.py
        # and the ENUM type 'targetplatform' should exist (either pre-existing or created by create_all)
        # and hopefully now includes 'email'.
        print("Attempting Base.metadata.create_all(bind=engine)...")
        Base.metadata.create_all(bind=engine)
        print("Base.metadata.create_all(bind=engine) called. Tables should be created/updated.")

    except Exception as e:
        print(f"Error during DB setup (ALTER TYPE, DROP TABLE, CREATE ALL): {e}")
        # Fallback: If main block failed, try create_all again as a last resort.
        print("Fallback: Attempting Base.metadata.create_all again.")
        Base.metadata.create_all(bind=engine)

