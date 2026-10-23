import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    return TestClient(app)
