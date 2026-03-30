from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

# Load variables from .env file
load_dotenv()

# Get the database URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")

# Create the connection to PostgreSQL
engine = create_engine(DATABASE_URL)

# Each API request gets its own database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class that all your models will inherit from
Base = declarative_base()


def get_db():
    """
    Provides a database session to each API endpoint.
    Automatically closes the connection when the request is done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
