import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///matches.db")
# Some hosted Postgres providers still expose the legacy scheme.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine_options = {
    "echo": os.environ.get("SQL_ECHO", "false").lower() == "true",
    "pool_pre_ping": True,
}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def init_db():
    Base.metadata.create_all(bind=engine)
if __name__ == "__main__":
    init_db()
