# Pydantic models and potentially ORM models for Scheduled Tasks

import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, HttpUrl, Field, model_validator, ConfigDict

# Re-using TargetPlatform Enum from technical specifications (assuming it's defined or will be defined in a shared location)
class TargetPlatform(str, Enum):
    LINKEDIN = "linkedin"
    X_TWITTER = "x_twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    WORDPRESS = "wordpress"
    EMAIL = "email" # Added for Email MCP

class ScheduledTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PlatformIdentifier(BaseModel):
    platform_name: TargetPlatform
    account_id: str # ID of the account specific to that platform (e.g., LinkedIn URN, X user ID, FB Page ID, or GENIA user ID for generic email)

class ScheduledTaskPayload(BaseModel):
    # This payload will be specific for each MCP of platform
    mcp_target_endpoint: str # e.g., "/linkedin/publish", "/x/tweet", "/email/send"
    mcp_request_body: Dict[str, Any] # The body of the request for the target MCP
    user_platform_tokens: Dict[str, Any] # Tokens for the specific platform, or could be empty for internal MCP calls

class CreateScheduledTaskRequest(BaseModel):
    genia_user_id: str # ID of the GENIA user to associate the task
    platform_identifier: PlatformIdentifier
    scheduled_at_utc: datetime.datetime # Publication date and time in UTC
    task_payload: ScheduledTaskPayload
    task_type: str = Field(default="generic_task") # Added to help categorize tasks if needed beyond platform

class ScheduledTaskBase(CreateScheduledTaskRequest):
    task_id: str = Field(..., examples=["task_123"])
    status: ScheduledTaskStatus = ScheduledTaskStatus.PENDING
    created_at_utc: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at_utc: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

class ScheduledTaskInDB(ScheduledTaskBase):
    # For SQLAlchemy or other ORM, this would be the table model
    # For now, using it as a Pydantic model representing DB structure
    execution_result_json: Optional[str] = None # Store execution result as JSON string

class ScheduledTaskResponse(ScheduledTaskBase):
    model_config = ConfigDict(from_attributes=True)
    execution_result: Optional[Dict[str, Any]] = None

# For responses that include a list of tasks
class ScheduledTaskListResponse(BaseModel):
    tasks: List[ScheduledTaskResponse]
    total: int

# For general MCP responses (can be moved to a shared models location)
class MCPResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    error_code: Optional[str] = None

