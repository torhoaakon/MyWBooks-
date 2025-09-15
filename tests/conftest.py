# tests/conftest.py
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

import mywbooks.models  # IMPORTANT: import models so tables are registered

# Import your app and models/db
from mywbooks.api.app import app
from mywbooks.db import Base  # declarative base in your db.py

# One shared in-memory SQLite for all sessions/connections
engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Create all tables once for the test DB
Base.metadata.create_all(bind=engine)


def _test_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _fake_current_user():
    return {
        "sub": "test-user-sub-123",
        "email": "tester@example.com",
        "iss": "https://test-issuer.example/auth/v1",
        "aud": "authenticated",
        "role": "authenticated",
    }


@pytest.fixture(scope="session")
def client():
    # 1) override DB dependency used by the books router:
    from mywbooks import db

    app.dependency_overrides[db.get_db] = _test_get_db

    # 2) override CurrentUser dependency:
    from mywbooks.api.auth import CurrentUser, verify_jwt

    app.dependency_overrides[verify_jwt] = lambda: _fake_current_user()
    return TestClient(app)


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Give tests a direct handle to the same in-memory DB the app uses."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
