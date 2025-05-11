# Service layer for scheduler business logic

import datetime
import uuid
import json # For serializing/deserializing JSON fields for DB
from typing import List, Optional, Dict, Any

from fastapi import Depends
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

# Initialize APScheduler
# This should ideally be managed at the application level (e.g., in main.py or a dedicated scheduler_setup.py)
# but for service encapsulation, we can have it here or pass it.
jobstores = {
    'default': SQLAlchemyJobStore(engine=engine) # Use the same engine as the app for jobs table
}
scheduler = AsyncIOScheduler(jobstores=jobstores)

class SchedulerService:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db
        if not scheduler.running:
            try:
                scheduler.start()
                print("APScheduler started.")
            except Exception as e:
                # Handle cases where scheduler might be already started in a different context (e.g. multiple workers)
                # This is a simple check; more robust handling might be needed in a multi-worker setup.
                if "SchedulerInstance" not in str(e): # Avoid logging if it's about instance already created
                    print(f"Error starting APScheduler: {e}")
                elif not scheduler.running: # If it claimed instance exists but not running, try again or raise
                    print(f"APScheduler instance found but not running. Attempting to start again or check config.")
                    # Potentially raise an error or log critical failure

    async def create_task(self, task_in: CreateScheduledTaskRequest) -> Optional[ScheduledTaskTable]:
        task_id = str(uuid.uuid4())
        
        db_task = ScheduledTaskTable(
            task_id=task_id,
            genia_user_id=task_in.genia_user_id,
            platform_name=task_in.platform_identifier.platform_name,
            account_id=task_in.platform_identifier.account_id,
            scheduled_at_utc=task_in.scheduled_at_utc,
            task_payload_json=task_in.task_payload.model_dump_json(),
            user_platform_tokens_json=json.dumps(task_in.task_payload.user_platform_tokens), # Assuming tokens are part of payload for now
            status=ScheduledTaskStatus.PENDING,
            created_at_utc=datetime.datetime.utcnow(),
            updated_at_utc=datetime.datetime.utcnow(),
            execution_result_json=None
        )
        self.db.add(db_task)
        self.db.commit()
        self.db.refresh(db_task)
        
        try:
            scheduler.add_job(
                func=self.execute_scheduled_task_job, # Wrapper to get new DB session
                trigger='date',
                run_date=db_task.scheduled_at_utc,
                args=[task_id],
                id=task_id,
                replace_existing=True,
                misfire_grace_time=3600 # Allow 1 hour for misfired jobs to still run
            )
            print(f"Task {task_id} scheduled in APScheduler for {db_task.scheduled_at_utc}")
        except Exception as e:
            print(f"Error scheduling task {task_id} with APScheduler: {e}")
            # Potentially roll back task creation or mark as failed to schedule
            # For now, we'll let the task be in DB but not scheduled by APScheduler
            # This indicates a problem with the scheduler setup or job store.
            # Consider raising an HTTPException here to inform the client.
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
            query = query.filter(ScheduledTaskTable.platform_name == platform_name)
        return query.all()

    async def get_task_by_id(self, task_id: str) -> Optional[ScheduledTaskTable]:
        return self.db.query(ScheduledTaskTable).filter(ScheduledTaskTable.task_id == task_id).first()

    async def update_task_status_in_db(self, task_id: str, status: ScheduledTaskStatus, result: Optional[Dict[str, Any]] = None, db_session: Optional[Session] = None) -> Optional[ScheduledTaskTable]:
        # Use provided db_session if available (e.g., from a job context), otherwise use self.db
        current_db = db_session if db_session else self.db
        
        task = current_db.query(ScheduledTaskTable).filter(ScheduledTaskTable.task_id == task_id).first()
        if task:
            task.status = status
            task.updated_at_utc = datetime.datetime.utcnow()
            if result:
                task.execution_result_json = json.dumps(result)
            current_db.commit()
            current_db.refresh(task)
            return task
        return None

    async def delete_task(self, task_id: str) -> bool:
        task = await self.get_task_by_id(task_id)
        if task:
            try:
                scheduler.remove_job(task_id)
                print(f"Job {task_id} removed from APScheduler.")
            except JobLookupError:
                print(f"Job {task_id} not found in APScheduler for removal (might have already run or failed to schedule).")
            except Exception as e:
                print(f"Error removing job {task_id} from APScheduler: {e}")
                # Decide if this is critical. If the job is not in scheduler, we can still delete from DB.

            self.db.delete(task)
            self.db.commit()
            return True
        return False

    @staticmethod
    async def execute_scheduled_task_job(task_id: str):
        # This static method is called by APScheduler. It needs its own DB session.
        # It's a common pattern for background jobs to manage their own resources.
        from app.db.session import SessionLocal # Import here to avoid circular dependencies at module level
        
        db_session_for_job = SessionLocal()
        # Create a temporary service instance with the new session for this job execution
        # This is a simplified way; a more robust DI system might be used for background tasks.
        temp_service_instance = SchedulerService(db=db_session_for_job) 
        
        try:
            print(f"APScheduler executing task_id: {task_id} at {datetime.datetime.utcnow()}")
            await temp_service_instance._execute_task_logic(task_id, db_session_for_job)
        except Exception as e:
            print(f"Unhandled exception in execute_scheduled_task_job for task_id {task_id}: {e}")
            # Ensure task is marked as FAILED even if _execute_task_logic fails before updating status
            await temp_service_instance.update_task_status_in_db(task_id, ScheduledTaskStatus.FAILED, result={"error": f"Job execution wrapper error: {str(e)}"}, db_session=db_session_for_job)
        finally:
            db_session_for_job.close()
            print(f"DB session closed for task_id: {task_id}")

    async def _execute_task_logic(self, task_id: str, db_session: Session):
        # This method contains the core logic for task execution, using the provided db_session
        task = db_session.query(ScheduledTaskTable).filter(ScheduledTaskTable.task_id == task_id).first()

        if not task:
            print(f"Task {task_id} not found in DB during execution.")
            return
        if task.status != ScheduledTaskStatus.PENDING and task.status != ScheduledTaskStatus.RUNNING: # Allow re-running if stuck in RUNNING
            print(f"Task {task_id} not in PENDING/RUNNING state. Current status: {task.status}. Skipping execution.")
            return

        await self.update_task_status_in_db(task_id, ScheduledTaskStatus.RUNNING, db_session=db_session)

        task_payload_dict = json.loads(task.task_payload_json)
        # user_tokens_dict = json.loads(task.user_platform_tokens_json) # Assuming tokens are in task_payload_dict.mcp_request_body.user_platform_tokens
        
        mcp_target_path = task_payload_dict.get("mcp_target_endpoint")
        mcp_request_body = task_payload_dict.get("mcp_request_body")

        print(f"Simulating call to target MCP for task {task_id}: Endpoint {mcp_target_path}")
        # Actual HTTP call to other MCPs would go here
        # Example:
        # from httpx import AsyncClient
        # target_mcp_base_url = self._get_mcp_base_url(task.platform_name) # Get base URL from config based on platform
        # if not target_mcp_base_url:
        #     await self.update_task_status_in_db(task_id, ScheduledTaskStatus.FAILED, result={"error": "Target MCP base URL not configured"}, db_session=db_session)
        #     return
        # full_target_url = f"{target_mcp_base_url.rstrip('/')}/{mcp_target_path.lstrip('/')}"
        # try:
        #     async with AsyncClient() as client:
        #         headers = {"Authorization": f"Bearer {settings.MCP_API_TOKEN_SECRET}"} # This is the token this MCP uses to call others
        #         response = await client.post(full_target_url, json=mcp_request_body, headers=headers, timeout=30.0)
        #         response.raise_for_status()
        #         execution_result = response.json()
        #         await self.update_task_status_in_db(task_id, ScheduledTaskStatus.COMPLETED, result=execution_result, db_session=db_session)
        #         print(f"Task {task_id} executed by target MCP, result: {execution_result}")
        # except Exception as e:
        #     print(f"Error calling target MCP for task {task_id}: {e}")
        #     await self.update_task_status_in_db(task_id, ScheduledTaskStatus.FAILED, result={"error": str(e)}, db_session=db_session)

        # Placeholder for actual execution logic - simulating success
        import time
        time.sleep(1) # Simulate work
        mock_result = {"status": "successfully executed by target MCP (simulated)", "details": f"Called {mcp_target_path}"}
        await self.update_task_status_in_db(task_id, ScheduledTaskStatus.COMPLETED, result=mock_result, db_session=db_session)
        print(f"Task {task_id} marked as COMPLETED (simulated) in DB.")

    def _get_mcp_base_url(self, platform: TargetPlatform) -> Optional[str]:
        if platform == TargetPlatform.LINKEDIN:
            return settings.MCP_LINKEDIN_BASE_URL
        elif platform == TargetPlatform.X_TWITTER:
            return settings.MCP_X_BASE_URL
        # ... add other platforms
        return None

# FastAPI dependency injector function
def get_scheduler_service(db: Session = Depends(get_db)) -> SchedulerService:
    return SchedulerService(db=db)

# Ensure scheduler is shutdown gracefully (e.g., in main.py @app.on_event("shutdown"))
# def shutdown_scheduler():
#     if scheduler.running:
#         scheduler.shutdown(wait=False)
#         print("APScheduler has been shut down.")

