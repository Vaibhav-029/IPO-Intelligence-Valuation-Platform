import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

# 1. Resolve absolute path to test_suite.db regardless of invocation directory
BACKEND_DIR = Path(__file__).resolve().parent.parent
TEST_DB_PATH = BACKEND_DIR / "test_suite.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH.as_posix()}"

# 2. Set environment variables early and configure sys.path
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = TEST_DB_URL
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 3. Clear settings cache so any calls to get_settings() pick up the test database URL
from app.core.config import get_settings
get_settings.cache_clear()

# 4. Rebind app.db engine and SessionLocal to guarantee test isolation
import app.db
test_engine_kwargs = {"connect_args": {"check_same_thread": False}}
test_engine = create_engine(TEST_DB_URL, future=True, pool_pre_ping=True, **test_engine_kwargs)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

app.db.engine = test_engine
app.db.SessionLocal = TestSessionLocal

# 5. If app.main was already imported, update its references as well
if "app.main" in sys.modules:
    import app.main
    app.main.engine = test_engine

# 6. Safety listener: prevent ANY connection under test from opening ipo_intelligence.db
@event.listens_for(Engine, "connect")
def verify_test_isolation(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        databases = cursor.execute("PRAGMA database_list").fetchall()
        for db_info in databases:
            file_path = str(db_info[2]) if len(db_info) > 2 and db_info[2] else ""
            if "ipo_intelligence.db" in file_path.lower():
                raise RuntimeError(
                    f"CRITICAL SAFETY VIOLATION: Test connection opened to development database! Path: {file_path}"
                )
    finally:
        cursor.close()

