from app.core.config import Settings


def test_database_url_accepts_render_postgres_urls():
    assert Settings(
        _env_file=None,
        database_url="postgres://user:password@host/app",
    ).database_url == "postgresql+psycopg2://user:password@host/app"

    assert Settings(
        _env_file=None,
        database_url="postgresql://user:password@host/app",
    ).database_url == "postgresql+psycopg2://user:password@host/app"
