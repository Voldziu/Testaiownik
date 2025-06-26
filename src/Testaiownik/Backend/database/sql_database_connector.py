# src/Backend/database/sql_database_connector.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./testaiownik.db")

engine = create_engine(
    DATABASE_URL,
    connect_args=(
        {
            "check_same_thread": False,
            "isolation_level": None,
        }
        if "sqlite" in DATABASE_URL
        else {}
    ),
)


SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=True
)
Base = declarative_base()


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
