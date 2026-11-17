from sqlalchemy.engine import make_url

from app.database import normalize_database_url


def test_render_postgres_url_selects_psycopg_driver():
    normalized = normalize_database_url(
        "postgresql://user:password@database.example:5432/internguard"
    )
    assert make_url(normalized).drivername == "postgresql+psycopg"
