# API router for task scheduling endpoints

from fastapi import APIRouter, Depends, HTTPException, status
import json # Added for JSON deserialization
from typing import List, Optional, Dict, Any # Added Any

from app.models.task import (
    CreateScheduledTaskRequest,
    ScheduledTaskResponse,
    ScheduledTaskListResponse,
    MCPResponse,
    ScheduledTaskStatus,
    TargetPlatform,
    PlatformIdentifier, # Added for constructing response
    ScheduledTaskPayload  # Added for constructing response
)
from app.db.models import ScheduledTaskTable # Import the ORM model
from app.services.scheduler_service import SchedulerService # This service will handle the business logic
from app.core.config import settings # For dependency injection or direct use if needed
# Assuming verify_mcp_api_token is defined in main.py or a shared auth module
# from app.main import verify_mcp_api_token # This creates a circular dependency, better to move verify_mcp_api_token

# Placeholder for the authentication dependency if moved
# from app.core.auth import verify_mcp_api_token

# For now, we'll define a placeholder for the dependency for structure
# In a real app, this would be properly managed in an auth.py or similar
async def placeholder_auth_dependency():
    # This would contain the logic from verify_mcp_api_token
    # print("Placeholder auth: In a real app, token would be verified here.")
    return True

router = APIRouter()

# Helper function to convert ORM model to Pydantic response model
def convert_task_orm_to_pydantic(db_task: ScheduledTaskTable) -> ScheduledTaskResponse:
    # Deserialize JSON fields first
    try:
        task_payload_data = json.loads(db_task.task_payload_json)
        user_platform_tokens_data = json.loads(db_task.user_platform_tokens_json)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON for task {db_task.task_id}: {e}")
        # Handle error appropriately, maybe raise HTTPException or return a default
        # For now, let's try to proceed with empty dicts if deserialization fails for payload parts
        task_payload_data = {}
        user_platform_tokens_data = {}

    platform_identifier_obj = PlatformIdentifier(
        platform_name=db_task.platform_name,
        account_id=db_task.account_id
    )

    # Construct ScheduledTaskPayload from the deserialized task_payload_data and user_platform_tokens_data
    # The service layer stores task_in.task_payload.model_dump_json() in task_payload_json
    # and json.dumps(task_in.task_payload.user_platform_tokens) in user_platform_tokens_json.
    # So, task_payload_data should contain mcp_target_endpoint and mcp_request_body.
    task_payload_obj = ScheduledTaskPayload(
        mcp_target_endpoint=task_payload_data.get("mcp_target_endpoint", ""),
        mcp_request_body=task_payload_data.get("mcp_request_body", {}),
        user_platform_tokens=user_platform_tokens_data # This was stored separately
    )
    
    execution_result_data = None
    if db_task.execution_result_json:
        try:
            execution_result_data = json.loads(db_task.execution_result_json)
        except json.JSONDecodeError:
            execution_result_data = {"error": "Failed to parse execution_result_json"}

    return ScheduledTaskResponse(
        task_id=db_task.task_id,
        genia_user_id=db_task.genia_user_id,
        platform_identifier=platform_identifier_obj,
        scheduled_at_utc=db_task.scheduled_at_utc,
        task_payload=task_payload_obj,
        status=db_task.status,
        created_at_utc=db_task.created_at_utc,
        updated_at_utc=db_task.updated_at_utc,
        execution_result=execution_result_data
    )

@router.post("/tasks", response_model=MCPResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_in: CreateScheduledTaskRequest,
    scheduler_service: SchedulerService = Depends(SchedulerService) 
):
    if not task_in.genia_user_id:
        raise HTTPException(status_code=400, detail="genia_user_id is required")

    created_task_orm = await scheduler_service.create_task(task_in=task_in)
    if not created_task_orm:
        raise HTTPException(status_code=500, detail="Failed to create task in DB")
    
    # Convert ORM to Pydantic for response
    response_data = convert_task_orm_to_pydantic(created_task_orm)

    return MCPResponse(
        success=True,
        message="Scheduled task created successfully.",
        data=response_data
    )

@router.get("/tasks", response_model=MCPResponse)
async def list_tasks(
    genia_user_id: Optional[str] = None,
    status_filter: Optional[ScheduledTaskStatus] = None, 
    platform: Optional[TargetPlatform] = None,
    scheduler_service: SchedulerService = Depends(SchedulerService)
):
    tasks_orm = await scheduler_service.get_tasks(
        genia_user_id=genia_user_id,
        status=status_filter,
        platform_name=platform
    )
    response_tasks = [convert_task_orm_to_pydantic(t) for t in tasks_orm]
    return MCPResponse(
        success=True,
        message="Tasks retrieved successfully.",
        data=ScheduledTaskListResponse(tasks=response_tasks, total=len(response_tasks))
    )

@router.get("/tasks/{task_id}", response_model=MCPResponse)
async def get_task(
    task_id: str,
    scheduler_service: SchedulerService = Depends(SchedulerService)
):
    task_orm = await scheduler_service.get_task_by_id(task_id=task_id)
    if not task_orm:
        raise HTTPException(status_code=404, detail="Task not found")
    
    response_data = convert_task_orm_to_pydantic(task_orm)
    return MCPResponse(
        success=True,
        message="Task retrieved successfully.",
        data=response_data
    )

@router.delete("/tasks/{task_id}", response_model=MCPResponse, status_code=status.HTTP_200_OK)
async def delete_task(
    task_id: str,
    scheduler_service: SchedulerService = Depends(SchedulerService)
):
    success = await scheduler_service.delete_task(task_id=task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or could not be deleted")
    return MCPResponse(
        success=True,
        message="Task cancelled successfully."
    )

