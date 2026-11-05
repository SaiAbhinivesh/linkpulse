import os

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import cache, main, rate_limit
from api.db import Base, get_db
from api.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://linkpulse:linkpulse@localhost:5433/linkpulse_test",
)

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache, "redis_client", fake)
    monkeypatch.setattr(rate_limit, "redis_client", fake)
    return fake


@pytest.fixture(autouse=True)
def published_clicks(monkeypatch):
    events = []
    monkeypatch.setattr(main, "publish_click", lambda code, user_agent: events.append(code))
    return events


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
