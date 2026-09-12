import os
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import get_settings

settings = get_settings()

# TEST ISOLATION SAFEGUARD:
# If pytest or any test runner is active, NEVER allow connecting to the development database ipo_intelligence.db
db_url = settings.database_url
is_testing = "pytest" in sys.modules or bool(os.environ.get("PYTEST_CURRENT_TEST")) or os.environ.get("TESTING") == "1"

if is_testing and "ipo_intelligence.db" in str(db_url):
    backend_dir = Path(__file__).resolve().parent.parent
    test_db = backend_dir / "test_suite.db"
    db_url = f"sqlite:///{test_db.as_posix()}"

engine_kwargs = {"connect_args": {"check_same_thread": False}} if db_url.startswith("sqlite") else {}
engine = create_engine(db_url, future=True, pool_pre_ping=True, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

