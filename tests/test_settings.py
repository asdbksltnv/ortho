import pytest

from app.main import create_app
from app.settings import Settings, get_settings, normalize_database_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ],
)
def test_database_url_normalized(raw: str, expected: str) -> None:
    assert normalize_database_url(raw) == expected
    assert Settings(database_url=raw).database_url == expected


def test_demo_mode_disables_storage() -> None:
    assert Settings(demo_mode=True, storage_backend="s3").effective_storage_backend == "disabled"
    assert Settings(demo_mode=False, storage_backend="s3").effective_storage_backend == "s3"


def test_production_requires_real_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "change-me")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        create_app()
    get_settings.cache_clear()


def test_docs_disabled_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 48)
    get_settings.cache_clear()
    assert create_app().openapi_url is None
    get_settings.cache_clear()
