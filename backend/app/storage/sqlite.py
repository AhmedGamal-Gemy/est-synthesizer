import aiosqlite
from backend.app.config import settings

async def init_db():
    """Initializes the SQLite database with necessary tables."""
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS generation_jobs (
                id TEXT PRIMARY KEY,
                status TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS test_inventory (
                id TEXT PRIMARY KEY,
                title TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS question_feedback (
                id TEXT PRIMARY KEY,
                test_id TEXT,
                question_id TEXT,
                flag TEXT,
                comment TEXT
            )
        """)
        await db.commit()

async def create_job(job_id: str):
    """Creates a new generation job record."""
    raise NotImplementedError("create_job not implemented")

async def update_job_status(job_id: str, status: str):
    """Updates the status of an existing generation job."""
    raise NotImplementedError("update_job_status not implemented")

async def save_feedback(feedback):
    """Saves user feedback for a question."""
    raise NotImplementedError("save_feedback not implemented")

async def get_feedback_by_test(test_id: str):
    """Retrieves all feedback for a specific test."""
    raise NotImplementedError("get_feedback_by_test not implemented")

async def list_tests():
    """Lists all tests in the inventory."""
    raise NotImplementedError("list_tests not implemented")
