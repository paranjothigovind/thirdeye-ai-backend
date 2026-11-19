"""Test configuration and database isolation."""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Signing secrets have no built-in default; give the tests throwaway values (never real ones).
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-real-use-0123456789")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret-not-for-real-use-0123456789")

from app.core.database import Base, get_db
from app.main import app

from app.models import course  # noqa: F401
from app.models import plan  # noqa: F401
from app.models import subscription  # noqa: F401
from app.models import user  # noqa: F401


TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "thirdeye_test.db")
DEV_DB_PATH = os.path.abspath("thirdeye.db")

assert os.path.abspath(TEST_DB_PATH) != DEV_DB_PATH, "Test DB must not be the development DB"

TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"


@pytest.fixture(scope="session")
def test_engine():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    engine = create_engine(
        TEST_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except PermissionError:
            pass




@pytest.fixture(scope="session")
def TestingSessionLocal(test_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def override_get_db(test_engine, TestingSessionLocal):
    def _get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def reset_test_tables(test_engine):
    with test_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    yield


@pytest.fixture(autouse=True)
def reset_usage_limits():
    """Start every test with empty rate-limit and token counters."""
    from app.core.usage import reset_usage_store

    reset_usage_store()
    yield
    reset_usage_store()
