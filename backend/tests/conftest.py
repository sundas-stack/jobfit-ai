"""Tests run against a real Postgres + pgvector, with the offline embedder and demo LLM.

Locally:  TEST_DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/jobfit_test pytest
In CI the database comes from a pgvector service container.
"""

import os

os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://jobfit:jobfit@localhost:5432/jobfit_test"
)
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["LLM_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import Base, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    init_db()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _clean():
    yield
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE analyses, chunks, documents RESTART IDENTITY CASCADE"))


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_ids(client):
    resume, job = client.post("/api/samples").json()
    return resume["id"], job["id"]
