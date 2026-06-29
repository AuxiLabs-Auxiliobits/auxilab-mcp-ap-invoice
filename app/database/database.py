from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# SQLite database file
DATABASE_URL = "sqlite:///vendor_master.db"

# Database Engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Session Factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base Class for Models
Base = declarative_base()


def get_db():
    """
    Dependency to get database session.
    Automatically closes the connection.
    """

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()