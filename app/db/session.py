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
    print("Attempting to DROP ENUM type, DROP TABLE, and then recreate all...")
    try:
        with engine.connect() as connection:
            # 1. Drop the ENUM type targetplatform if it exists
            # CASCADE will also drop any columns using this type (like in scheduled_tasks)
            drop_enum_command = text("DROP TYPE IF EXISTS targetplatform CASCADE;")
            print(f"Attempting to execute: {drop_enum_command}")
            connection.execute(drop_enum_command)
            connection.commit()
            print(f"Raw SQL executed: DROP TYPE IF EXISTS targetplatform CASCADE;")

            # 2. Drop the table scheduled_tasks if it exists (might be redundant if CASCADE worked on ENUM)
            # but good to have as a safeguard or if ENUM didn't exist.
            drop_table_command = text("DROP TABLE IF EXISTS scheduled_tasks CASCADE;")
            print(f"Attempting to execute: {drop_table_command}")
            connection.execute(drop_table_command)
            connection.commit()
            print(f"Raw SQL executed: DROP TABLE IF EXISTS scheduled_tasks CASCADE;")
        
        # 3. Create all tables defined in Base. 
        # SQLAlchemy will now create the ENUM type 'targetplatform' based on the Python Enum (which is lowercase)
        # and then create the 'scheduled_tasks' table with the column using this newly created ENUM type.
        print("Attempting Base.metadata.create_all(bind=engine) to recreate ENUM and tables...")
        Base.metadata.create_all(bind=engine)
        print("Base.metadata.create_all(bind=engine) called. ENUM and tables should be recreated with correct schema.")

    except Exception as e:
        print(f"Error during DB setup (DROP TYPE, DROP TABLE, CREATE ALL): {e}")
        # Fallback: If main block failed, try create_all again as a last resort.
        # This might not help if the ENUM is still in a conflicting state, but it's a last attempt.
        print("Fallback: Attempting Base.metadata.create_all again.")
        Base.metadata.create_all(bind=engine)

