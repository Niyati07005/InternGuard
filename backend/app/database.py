from pathlib import Path
import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
environment = os.getenv("ENVIRONMENT", "development").lower()


def normalize_database_url(value: str) -> str:
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


database_url = os.getenv("DATABASE_URL", "").strip()
if not database_url:
    if environment == "production":
        raise RuntimeError("DATABASE_URL is required in production; configure persistent PostgreSQL.")
    database_url = f"sqlite:///{(DATA_DIR / 'internguard.db').as_posix()}"
elif environment == "production" and not database_url.startswith(
    ("postgres://", "postgresql://", "postgresql+psycopg://")
):
    raise RuntimeError("Production DATABASE_URL must point to persistent PostgreSQL.")
database_url = normalize_database_url(database_url)

engine_options = {"pool_pre_ping": True}
if database_url.startswith("sqlite:"):
    engine_options["connect_args"] = {"check_same_thread": False}
engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_database():
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "scans" in tables:
        columns = {column["name"] for column in inspector.get_columns("scans")}
        if "owner_user_id" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE scans ADD COLUMN owner_user_id INTEGER REFERENCES users(id)")
                )
                connection.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_scans_owner_user_id ON scans (owner_user_id)")
                )
    if "users" in tables:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_guest" not in user_columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE users ADD COLUMN is_guest BOOLEAN NOT NULL DEFAULT FALSE")
                )
