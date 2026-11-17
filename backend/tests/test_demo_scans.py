from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from app.auth import router as auth_router
from app.database import Base, get_db
from app.routes import router


def test_demo_scans_are_labeled_idempotent_and_show_each_risk_level():
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

    with TestClient(app) as client:
        assert client.get("/api/auth/me").json()["is_guest"] is True
        created = client.post("/api/demo-scans")
        assert created.status_code == 200
        assert created.json() == {"created": True, "count": 3}

        scans = client.get("/api/scans").json()
        assert len(scans) == 3
        assert {scan["risk_category"] for scan in scans} == {"LOW", "MEDIUM", "HIGH"}
        assert all(scan["sample_data"] for scan in scans)
        by_category = {scan["risk_category"]: scan for scan in scans}
        assert any("interview" in reason.lower() for reason in by_category["LOW"]["risk_explanation"])
        assert any(
            "upfront payment request" in reason.lower()
            for reason in by_category["MEDIUM"]["risk_explanation"]
        )
        assert any(
            phrase in " ".join(by_category["HIGH"]["risk_explanation"]).lower()
            for phrase in ("guaranteed placement", "security deposit", "sensitive information")
        )

        scan_id = by_category["HIGH"]["scan_id"]
        report_url = f"/api/scans/{scan_id}/report.pdf"
        opened_report = client.get(report_url, params={"inline": "true"})
        assert opened_report.status_code == 200
        assert opened_report.headers["content-type"] == "application/pdf"
        assert opened_report.headers["content-disposition"].startswith("inline;")
        assert opened_report.content.startswith(b"%PDF-")
        downloaded_report = client.get(report_url)
        assert downloaded_report.headers["content-disposition"].startswith("attachment;")

        dashboard = client.get("/api/dashboard").json()
        assert dashboard["sample_data"] is True
        assert dashboard["sample_scan_count"] == 3

        second_request = client.post("/api/demo-scans")
        assert second_request.json() == {"created": False, "count": 0}
        assert len(client.get("/api/scans").json()) == 3

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
