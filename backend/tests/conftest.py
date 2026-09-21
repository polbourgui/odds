import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (ensures all models are registered on Base.metadata)
from app.db.base import Base


@pytest.fixture
def db_session():
    # StaticPool + check_same_thread=False: FastAPI's TestClient runs
    # requests in a worker thread, but an in-memory SQLite DB only exists on
    # the connection that created it, so the same connection must be reused
    # across threads for API-level tests.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()
