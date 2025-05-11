# SQLAlchemy models for the database

from sqlalchemy import Column, String, DateTime, Text, Enum as SQLAlchemyEnum, JSON
from sqlalchemy.dialects.postgresql import UUID # If using PostgreSQL for UUID type
import uuid # For default UUID generation if not handled by DB
import datetime

from app.db.session import Base # Import Base from your session.py
from app.models.task import ScheduledTaskStatus, TargetPlatform # Re-use Pydantic enums for consistency

class ScheduledTaskTable(Base):
    __tablename__ = "scheduled_tasks"

    # task_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4) # For PostgreSQL
    task_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())) # For SQLite compatibility
    genia_user_id = Column(String, index=True, nullable=False)
    
    platform_name = Column(SQLAlchemyEnum(TargetPlatform), nullable=False)
    account_id = Column(String, nullable=False) # Account ID on the target platform

    scheduled_at_utc = Column(DateTime, nullable=False, index=True)
    status = Column(SQLAlchemyEnum(ScheduledTaskStatus), nullable=False, default=ScheduledTaskStatus.PENDING, index=True)
    
    task_payload_json = Column(Text, nullable=False) 
    user_platform_tokens_json = Column(Text, nullable=False) 

    created_at_utc = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at_utc = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    execution_result_json = Column(Text, nullable=True) 

    task_type = Column(String, nullable=True, index=True, default="generic_task") # Added task_type field

    def __repr__(self):
        return f"<ScheduledTaskTable(task_id=\\'{self.task_id}\\' status=\\'{self.status}\\' type=\\'{self.task_type}\\')>"

