# Service layer for scheduler business logic

import datetime
import uuid
import json # For serializing/deserializing JSON fields for DB
import logging # Added for more detailed logging
from typing import List, Optional, Dict, Any

import httpx # For making async HTTP calls to other MCPs
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.base import JobLookupError

from app.models.task import (
    CreateScheduledTaskRequest,
    ScheduledTaskStatus,
    TargetPlatform,
    ScheduledTaskResponse,
    PlatformIdentifier,
    ScheduledTaskPayload
)
from app.db.models import ScheduledTaskTable # SQLAlchemy model
from app.db.session import get_db, engine # SQLAlchemy session and engine
from app.core.config import settings

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("APScheduler: Initializing jobstores...")
jobstores = {
    'default': SQLAlchemyJobStore(engine=engine) # Use the same engine as the app for jobs table
}
logger.info(f"APScheduler: Jobstores initialized: {jobstores}")

logger.info("APScheduler: Creating AsyncIOScheduler instance...")
scheduler = AsyncIOScheduler(jobstores=jobstores)
logger.info(f"APScheduler: AsyncIOScheduler instance created. Current state: running={scheduler.running}")

class SchedulerService:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db
        logger.info(f"SchedulerService __init__ called. APScheduler current state: running={scheduler.running}")
        if not scheduler.running:
            logger.info("APScheduler: Scheduler is not running. Attempting to start...")
            try:
                scheduler.start()
                logger.info("APScheduler: scheduler.start() called successfully. Current state: running={scheduler.running}")
            except Exception as e:
                logger.error(f"APScheduler: Error during scheduler.start(): {e}", exc_info=True)
                if "SchedulerInstance" not in str(e):
                    logger.warning(f"APScheduler: Error starting APScheduler that is not 'SchedulerInstance' related: {e}")
                elif not scheduler.running:
                    logger.warning(f"APScheduler: Instance found but reported as not running. Current state: running={scheduler.running}. This might indicate an issue.")
                else:
                    logger.info("APScheduler: Instance likely already started by another worker/process.")
        else:
            logger.info("APScheduler: Scheduler was already running when SchedulerService was initialized.")

    async def create_task(self, task_in: CreateScheduledTaskRequest) -> Optional[ScheduledTaskTable]:
        task_id = str(uuid.uuid4())
        logger.info(f"SchedulerService: create_task called for task_id (generated): {task_id}, type: {task_in.task_type}")
        
        # Ensure platform_name is the lowercase string value from the Enum
        platform_name_value = task_in.platform_identifier.platform_name.value
        logger.info(f"SchedulerService: Value of platform_name from Enum for DB insertion: {platform_name_value}")

        db_task = ScheduledTaskTable(
            task_id=task_id,
            genia_user_id=task_in.genia_user_id,
            platform_name=platform_name_value, # Use the direct lowercase string value from Enum
            account_id=task_in.platform_identifier.account_id,
            scheduled_at_utc=task_in.scheduled_at_utc,
            task_payload_json=task_in.task_payload.model_dump_json(),
            user_platform_tokens_json=json.dumps(task_in.task_payload.user_platform_tokens),
            status=ScheduledTaskStatus.PENDING,
            created_at_utc=datetime.datetime.utcnow(),
            updated_at_utc=datetime.datetime.utcnow(),
            execution_result_json=None,
            task_type=task_in.task_type
        )
        self.db.add(db_task)
        self.db.commit()
        self.db.refresh(db_task)
        logger.info(f"SchedulerService: Task {task_id} saved to DB.")
        
        try:
            logger.info(f"APScheduler: Attempting to add job {task_id} for {db_task.scheduled_at_utc}. Current state: running={scheduler.running}")
            scheduler.add_job(
                func=self.execute_scheduled_task_job, 
                trigger='date',
                run_date=db_task.scheduled_at_utc,
                args=[task_id],
                id=task_id,
                replace_existing=True,
                misfire_grace_time=3600
            )
            logger.info(f"APScheduler: Job {task_id} added successfully to scheduler for {db_task.scheduled_at_utc}")
        except Exception as e:
            logger.error(f"APScheduler: Error adding job {task_id} to scheduler: {e}", exc_info=True)
            # Consider marking task as FAILED_TO_SCHEDULE or raising an error
            pass

        return db_task

    async def get_tasks(
        self,
        genia_user_id: Optional[str] = None,
        status: Optional[ScheduledTaskStatus] = None,
        platform_name: Optional[TargetPlatform] = None
    ) -> List[ScheduledTaskTable]:
        query = self.db.query(ScheduledTaskTable)
        if genia_user_id:
            query = query.filter(ScheduledTaskTable.genia_user_id == genia_user_id)
        if status:
            query = query.filter(ScheduledTaskTable.status == status)
        if platform_name:
            # When querying, ensure we also use the lowercase value if the input is an Enum member
            query = query.filter(ScheduledTaskTable.platform_name == platform_name.value)
        return query.all()

    async def get_task_by_id(self, task_id: str) -> Optional[ScheduledTaskTable]:
        return self.db.query(ScheduledTaskTable).filter(ScheduledTaskTable.task_id == task_id).first()

    async def update_task_status_in_db(self, task_id: str, status: ScheduledTaskStatus, result: Optional[Dict[str, Any]] = None, db_session: Optional[Session] = None) -> Optional[ScheduledTaskTable]:
        current_db = db_session if db_session else self.db
        logger.info(f"SchedulerService: Updating task {task_id} status to {status} in DB.")
        task = current_db.query(ScheduledTaskTable).filter(ScheduledTaskTable.task_id == task_id).first()
        if task:
            task.status = status
            task.updated_at_utc = datetime.datetime.utcnow()
            if result:
                task.execution_result_json = json.dumps(result)
            current_db.commit()
            current_db.refresh(task)
            logger.info(f"SchedulerService: Task {task_id} status updated successfully.")
            return task
        logger.warning(f"SchedulerService: Task {task_id} not found for status update.")
        return None

    async def delete_task(self, task_id: str) -> bool:
        logger.info(f"SchedulerService: Attempting to delete task {task_id}.")
        task = await self.get_task_by_id(task_id)
        if task:
            try:
                logger.info(f"APScheduler: Attempting to remove job {task_id}. Current state: running={scheduler.running}")
                scheduler.remove_job(task_id)
                logger.info(f"APScheduler: Job {task_id} removed successfully.")
            except JobLookupError:
                logger.warning(f"APScheduler: Job {task_id} not found for removal (already run or failed to schedule).")
            except Exception as e:
                logger.error(f"APScheduler: Error removing job {task_id}: {e}", exc_info=True)

            self.db.delete(task)
            self.db.commit()
            logger.info(f"SchedulerService: Task {task_id} deleted from DB.")
            return True
        logger.warning(f"SchedulerService: Task {task_id} not found for deletion.")
        return False

    @staticmethod
    async def execute_scheduled_task_job(task_id: str):
        from app.db.session import SessionLocal 
        db_session_for_job = SessionLocal()
        temp_service_instance = SchedulerService(db=db_session_for_job)
        logger.info(f"APScheduler: execute_scheduled_task_job started for task_id: {task_id} at {datetime.datetime.utcnow()}")
        try:
            await temp_service_instance._execute_task_logic(task_id, db_session_for_job)
        except Exception as e:
            logger.error(f"APScheduler: Unhandled exception in execute_scheduled_task_job for task_id {task_id}: {e}", exc_info=True)
            await temp_service_instance.update_task_status_in_db(task_id, ScheduledTaskStatus.FAILED, result={"error": f"Job execution wrapper error: {str(e)}"}, db_session=db_session_for_job)
        finally:
            db_session_for_job.close()
            logger.info(f"APScheduler: DB session closed for task_id: {task_id} after job execution.")

    async def _execute_task_logic(self, task_id: str, db_session: Session):
        logger.info(f"SchedulerService: _execute_task_logic started for task_id: {task_id}.")
        task = db_session.query(ScheduledTaskTable).filter(ScheduledTaskTable.task_id == task_id).first()

        if not task:
            logger.warning(f"SchedulerService: Task {task_id} not found in DB during _execute_task_logic.")
            return
        if task.status != ScheduledTaskStatus.PENDING and task.status != ScheduledTaskStatus.RUNNING:
            logger.warning(f"SchedulerService: Task {task_id} not in PENDING/RUNNING state. Current status: {task.status}. Skipping execution.")
            return

        await self.update_task_status_in_db(task_id, ScheduledTaskStatus.RUNNING, db_session=db_session)

        task_payload_dict = json.loads(task.task_payload_json)
        mcp_target_endpoint_path = task_payload_dict.get("mcp_target_endpoint")
        mcp_request_body = task_payload_dict.get("mcp_request_body")
        # user_platform_tokens = task_payload_dict.get("user_platform_tokens") # May be needed for some MCPs

        # platform_name in DB is already lowercase. Convert to TargetPlatform Enum for logic.
        platform_enum_member = TargetPlatform(task.platform_name) # This will work if task.platform_name is 'email', 'whatsapp' etc.
        target_mcp_base_url = self._get_mcp_base_url(platform_enum_member) # Get base URL from config

        if not target_mcp_base_url:
            logger.error(f"SchedulerService: Target MCP base URL not configured for platform {task.platform_name} (task {task_id}).")
            await self.update_task_status_in_db(task_id, ScheduledTaskStatus.FAILED, result={"error": f"Target MCP base URL not configured for platform {task.platform_name}"}, db_session=db_session)
            return
        
        full_target_url = f"{target_mcp_base_url.rstrip('/')}/{mcp_target_endpoint_path.lstrip('/')}"
        logger.info(f"SchedulerService: Calling target MCP for task {task_id}. URL: {full_target_url}")

        headers = {
            "Authorization": f"Bearer {settings.MCP_API_TOKEN_SECRET}", # This MCP's token to call other MCPs
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(full_target_url, json=mcp_request_body, headers=headers)
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                
                execution_result = response.json()
                await self.update_task_status_in_db(task_id, ScheduledTaskStatus.COMPLETED, result=execution_result, db_session=db_session)
                logger.info(f"SchedulerService: Task {task_id} executed successfully by target MCP. Result: {execution_result}")
        
        except httpx.HTTPStatusError as http_err:
            error_content = http_err.response.text
            logger.error(f"SchedulerService: HTTP error calling target MCP for task {task_id}: {http_err}. Response: {error_content}", exc_info=True)
            await self.update_task_status_in_db(task_id, ScheduledTaskStatus.FAILED, result={"error": f"HTTP error: {http_err}", "details": error_content}, db_session=db_session)
        except httpx.RequestError as req_err:
            logger.error(f"SchedulerService: Request error calling target MCP for task {task_id}: {req_err}", exc_info=True)
            await self.update_task_status_in_db(task_id, ScheduledTaskStatus.FAILED, result={"error": f"Request error: {str(req_err)}"}, db_session=db_session)
        except Exception as e:
            logger.error(f"SchedulerService: Unexpected error calling target MCP for task {task_id}: {e}", exc_info=True)
            await self.update_task_status_in_db(task_id, ScheduledTaskStatus.FAILED, result={"error": f"Unexpected error: {str(e)}"}, db_session=db_session)

    def _get_mcp_base_url(self, platform: TargetPlatform) -> Optional[str]:
        # platform is now an Enum member, e.g. TargetPlatform.EMAIL
        # settings should ideally store keys like "MCP_EMAIL_BASE_URL"
        # The TargetPlatform enum values are 'email', 'linkedin', etc. (lowercase)
        # So we need to map them correctly to settings attributes.

        if platform == TargetPlatform.EMAIL:
            return settings.MCP_EMAIL_BASE_URL
        elif platform == TargetPlatform.LINKEDIN:
            return settings.MCP_LINKEDIN_BASE_URL
        elif platform == TargetPlatform.X_TWITTER:
            return settings.MCP_X_BASE_URL
        elif platform == TargetPlatform.FACEBOOK:
            return settings.MCP_FACEBOOK_BASE_URL
        elif platform == TargetPlatform.INSTAGRAM:
            return settings.MCP_INSTAGRAM_BASE_URL
        elif platform == TargetPlatform.WORDPRESS:
            return settings.MCP_WORDPRESS_BASE_URL
        logger.warning(f"SchedulerService: No base URL configured for platform: {platform.value}")
        return None

def get_scheduler_service(db: Session = Depends(get_db)) -> SchedulerService:
    return SchedulerService(db=db)

logger.info("APScheduler: scheduler_service.py module loaded.")

