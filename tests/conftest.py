"""Isolated API test setup.

Environment variables are set before importing the application so the SQLAlchemy
engine points at a disposable SQLite database. Startup seeding is disabled here;
the fixtures seed the synthetic dataset explicitly.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

TEST_DIR = Path(tempfile.mkdtemp(prefix="knowledgebridge-tests-"))
TEST_DB = TEST_DIR / "knowledgebridge_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test-only-jwt-secret"
os.environ["DEMO_PASSWORD"] = "TestDemoPass!2026"
os.environ["LLM_BASE_URL"] = ""
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_MODEL"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.config import settings  # noqa: E402
from backend.app.db import SessionLocal, init_db, session_scope  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.models import Project, User  # noqa: E402
from backend.app.seed import seed_demo  # noqa: E402
from backend.app.services.orchestrator import run_full_reconstruction  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    init_db()
    with session_scope() as db:
        result = seed_demo(db)
        run_full_reconstruction(db, result["project_id"], result["manager_id"])
    yield
    shutil.rmtree(TEST_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def seeded_ids():
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.key == "ATLAS").first()
        manager = db.query(User).filter(User.email == "manager@knowledgebridge.demo").first()
        engineer = db.query(User).filter(User.email == "engineer@knowledgebridge.demo").first()
        analyst = db.query(User).filter(User.email == "analyst@knowledgebridge.demo").first()
        auditor = db.query(User).filter(User.email == "auditor@knowledgebridge.demo").first()
        return {
            "project_id": project.id,
            "manager_id": manager.id,
            "engineer_id": engineer.id,
            "analyst_id": analyst.id,
            "auditor_id": auditor.id,
            "demo_password": settings.demo_password,
        }
    finally:
        db.close()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def auth_headers(client: TestClient, email: str, password: str | None = None) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password or settings.demo_password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def manager_headers(client, seeded_ids):
    return auth_headers(client, "manager@knowledgebridge.demo", seeded_ids["demo_password"])


@pytest.fixture(scope="session")
def engineer_headers(client, seeded_ids):
    return auth_headers(client, "engineer@knowledgebridge.demo", seeded_ids["demo_password"])


@pytest.fixture(scope="session")
def analyst_headers(client, seeded_ids):
    return auth_headers(client, "analyst@knowledgebridge.demo", seeded_ids["demo_password"])


@pytest.fixture(scope="session")
def auditor_headers(client, seeded_ids):
    return auth_headers(client, "auditor@knowledgebridge.demo", seeded_ids["demo_password"])
