import os
import sys

# Add project root to Python path to allow imports like 'from app.core...'
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

print(f"Current working directory: {os.getcwd()}")
print(f"Python path: {sys.path}")

# Set dummy environment variables required by app.core.config
# These are for local testing of db creation logic only.
print("Setting environment variables for local test...")
os.environ["DATABASE_URL"] = "sqlite:///./test_local_db_recreation.db"
os.environ["SCHEDULER_DATABASE_URL"] = "sqlite:///./test_local_db_recreation.db"
os.environ["MCP_API_TOKEN_SECRET"] = "test_secret_token_for_local_test"
os.environ["MCP_EMAIL_BASE_URL"] = "http://localhost:8001"
os.environ["MCP_LINKEDIN_BASE_URL"] = "http://localhost:8002"
os.environ["MCP_X_BASE_URL"] = "http://localhost:8003"
os.environ["MCP_FACEBOOK_BASE_URL"] = "http://localhost:8004"
os.environ["MCP_INSTAGRAM_BASE_URL"] = "http://localhost:8005"
os.environ["MCP_WORDPRESS_BASE_URL"] = "http://localhost:8006"
print("Environment variables set.")

try:
    print("Attempting to import create_db_and_tables from app.db.session...")
    from app.db.session import create_db_and_tables, engine
    from app.db.models import Base # This ensures Base.metadata is populated
    from sqlalchemy import inspect

    print("Successfully imported required modules.")
    print("Starting local test of create_db_and_tables function...")

    create_db_and_tables()

    print("Local test of create_db_and_tables function finished.")
    print("Checking database schema...")

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables found in the local SQLite database: {tables}")

    if "scheduled_tasks" in tables:
        print("SUCCESS: The 'scheduled_tasks' table was created in the local SQLite database.")
        columns = inspector.get_columns('scheduled_tasks')
        print("Columns in 'scheduled_tasks':")
        for column in columns:
            print(f"  - {column['name']}: {column['type']}")
    else:
        print("FAILURE: The 'scheduled_tasks' table was NOT created in the local SQLite database.")

except ImportError as e:
    print(f"ImportError during local test: {e}")
    print("This might be due to issues with the Python path or module dependencies not being found.")
    print("Ensure the script is run from the project root or the path is correctly set.")
except Exception as e:
    print(f"An unexpected error occurred during the local test: {e}")
    import traceback
    traceback.print_exc()

finally:
    if os.path.exists("./test_local_db_recreation.db"):
        print("Cleaning up local test database file: ./test_local_db_recreation.db")
        os.remove("./test_local_db_recreation.db")
        print("Local test database file removed.")

