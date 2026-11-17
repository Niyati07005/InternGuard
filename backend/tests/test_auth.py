from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from app.auth import router as auth_router
from app.database import Base, get_db
from app.routes import router


def test_user_sessions_and_scan_history_are_isolated():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-session-secret")
    app.include_router(auth_router)
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as first_user:
        guest = first_user.get("/api/auth/me").json()
        assert guest["is_guest"] is True
        assert guest["email"] is None

        scan = first_user.post(
            "/api/analyze",
            json={
                "job_title": "Software Intern",
                "company_name": "Northstar Labs",
                "job_description": (
                    "Work with an engineering team on a supervised ten week project. "
                    "Candidates complete an interview and no fee is required."
                ),
                "recruitment_message": "",
                "application_url": "",
            },
        )
        assert scan.status_code == 200
        scan_id = scan.json()["scan_id"]
        assert first_user.post("/api/demo-scans").json() == {"created": False, "count": 0}

        registration = first_user.post(
            "/api/auth/register",
            json={"email": "first@example.com", "password": "a-secure-password"},
        )
        assert registration.status_code == 201
        assert registration.json()["user"]["email"] == "first@example.com"
        assert [row["scan_id"] for row in first_user.get("/api/scans").json()] == [scan_id]

        with TestClient(app) as second_user:
            second_registration = second_user.post(
                "/api/auth/register",
                json={"email": "second@example.com", "password": "another-secure-password"},
            )
            assert second_registration.status_code == 201
            assert second_user.get("/api/scans").json() == []
            assert second_user.get(f"/api/scans/{scan_id}").status_code == 404
            assert second_user.post(
                "/api/auth/login",
                json={"email": "first@example.com", "password": "incorrect-password"},
            ).status_code == 401
            second_user.post("/api/auth/logout")
            login = second_user.post(
                "/api/auth/login",
                json={"email": "first@example.com", "password": "a-secure-password"},
            )
            assert login.status_code == 200
            assert [row["scan_id"] for row in second_user.get("/api/scans").json()] == [scan_id]

        assert first_user.post("/api/auth/logout").status_code == 200
        assert first_user.get("/api/auth/me").json()["is_guest"] is True
        assert first_user.get("/api/scans").json() == []

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
