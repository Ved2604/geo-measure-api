from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# The whole database is stored in this one file in the project folder
DATABASE_URL = "sqlite:///geo.db"

# check_same_thread=False lets FastAPI use the connection from different threads
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """Parent class for all table classes."""


def get_db():
    """Gives each request its own database session and always closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()