from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_phase10_routes_are_registered():
    source = (ROOT / "app/api/router.py").read_text()
    assert "background_jobs.router" in source

def test_celery_registers_evaluation_and_email_tasks():
    source = (ROOT / "app/core/celery_app.py").read_text()
    assert "app.workers.evaluation_tasks" in source
    assert "app.workers.email_tasks" in source

def test_compose_contains_redis_and_worker():
    source = (ROOT / "docker-compose.yml").read_text()
    assert "  redis:" in source
    assert "  worker:" in source
    assert "celery -A app.core.celery_app.celery_app worker" in source

def test_background_job_migration_follows_phase8():
    source = (ROOT / "alembic/versions/d4e5f6a7b8c9_phase10_background_jobs.py").read_text()
    assert 'down_revision: Union[str, None] = "c3d4e5f6a7b8"' in source
    assert '"background_jobs"' in source
