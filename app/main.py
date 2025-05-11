# Main application file for Scheduler MCP

from fastapi import FastAPI, Depends
import uvicorn

from app.core.config import settings
from app.api.api_router import router as api_router # Corrected import for the router
from app.core.auth import verify_mcp_api_token # Import the auth function
from app.db.session import create_db_and_tables # For DB initialization
from app.services.scheduler_service import scheduler # To shutdown APScheduler

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Apply the authentication middleware to the main API router
app.include_router(
    api_router, 
    prefix=settings.API_V1_STR, 
    dependencies=[Depends(verify_mcp_api_token)], # Apply auth to all routes in api_router
    tags=["Scheduler Tasks"] # Add a tag for OpenAPI docs
)

@app.on_event("startup")
async def startup_event():
    print("Scheduler MCP starting up...")
    # Create database tables if they don't exist
    # This is a synchronous operation, so it's fine here or called from an async context if needed by ORM
    create_db_and_tables()
    print("Database tables checked/created.")
    # APScheduler is started when SchedulerService is first instantiated, 
    # but we can add a log here or ensure it's running.
    if scheduler.running:
        print("APScheduler is running.")
    else:
        print("APScheduler is NOT running. Check SchedulerService instantiation.")
        # Attempt to start it if it wasn't (though service instantiation should handle it)
        try:
            if not scheduler.running:
                 scheduler.start()
                 print("APScheduler started on app startup.")
        except Exception as e:
            print(f"Could not start APScheduler on app startup: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    print("Scheduler MCP shutting down...")
    if scheduler.running:
        scheduler.shutdown(wait=False) # Set wait=False for faster shutdown if needed, or True to wait for jobs
        print("APScheduler has been shut down.")

@app.get("/ping", tags=["Health Check"])
async def pong():
    """
    Sanity check.
    """
    return {"ping": "pong!"}

# The uvicorn.run call should ideally be outside the app/main.py for production,
# typically in a run.py or managed by a process manager like Gunicorn.
# For development, it's fine here.
if __name__ == "__main__":
    # Ensure the port is configurable, e.g., from an environment variable or settings
    # For now, hardcoding to 8001 as an example for this MCP
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True) # reload=True for development

