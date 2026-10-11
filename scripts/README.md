# scripts/

One-off operational scripts (seeding data, manual migrations, verification
scripts, DB inspection helpers) live here - never loose in `app/` or in the
`backend/` root. Run them with `python -m scripts.<name>` so they share the
same `app.core.config` settings as the real app instead of hardcoding values.

## seed_admin.py

Creates the first admin (central body) account from `FIRST_ADMIN_*` in
`.env`, if no admin exists yet. Idempotent - safe to run on every deploy.
This runs automatically on container start (see `docker-entrypoint.sh`),
so you normally don't need to run it by hand.

    python -m scripts.seed_admin
