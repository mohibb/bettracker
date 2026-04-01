import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from factories import TestingSessionLocal, engine


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_db():
    """Drop and recreate all tables before every test for a clean slate."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    from app.routers import cart as cart_module
    cart_module._cart.clear()
    cart_module._cart_created_at = None


@pytest.fixture()
def client():
    return TestClient(app)
