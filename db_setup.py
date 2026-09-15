import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

DATABASE_URL = "sqlite:///matches.db"

engine = create_engine(DATABASE_URL, echo=os.environ.get("SQL_ECHO", "false").lower() == "true")
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
if __name__ == "__main__":
    init_db()
