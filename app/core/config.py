from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "GENIA Scheduler MCP"
    API_V1_STR: str = "/api/v1"
    MCP_API_TOKEN_SECRET: str = "YOUR_SCHEDULER_MCP_SECRET_TOKEN_HERE" # TODO: Replace with a secure, generated token and manage via env var
    DATABASE_URL: str = "sqlite:///./scheduler.db" # Example, replace with actual DB URL (e.g., PostgreSQL)
    # Add other settings like LOG_LEVEL, etc.

    # APScheduler settings (if used directly)
    SCHEDULER_DATABASE_URL: str = "sqlite:///./scheduler_jobs.db" # For APScheduler's job store

    # Base URLs for other MCPs (to be called by the scheduler worker)
    # These should be populated from environment variables in a real deployment
    MCP_LINKEDIN_BASE_URL: str = "http://localhost:8002/api/v1" # Example
    MCP_X_BASE_URL: str = "http://localhost:8003/api/v1" # Example
    MCP_FACEBOOK_BASE_URL: str = "http://localhost:8004/api/v1" # Example
    MCP_INSTAGRAM_BASE_URL: str = "http://localhost:8005/api/v1" # Example
    MCP_WORDPRESS_BASE_URL: str = "http://localhost:8006/api/v1" # Example

    class Config:
        case_sensitive = True

settings = Settings()

