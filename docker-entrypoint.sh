#!/bin/sh
set -e

# RUN_MIGRATIONS is set to "false" on the celery worker service in
# docker-compose.yml so two containers don't race to run migrations on
# startup - only the backend api container does it.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "Running database migrations..."
    alembic upgrade head

    echo "Ensuring first admin (central body) account exists..."
    python -m scripts.seed_admin
fi

exec "$@"
