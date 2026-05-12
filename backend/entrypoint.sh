#!/bin/sh
# Production entrypoint: run pending migrations, then exec the CMD.
# Stays minimal so a misconfigured app doesn't masquerade as a healthy DB.

set -eu

echo "[entrypoint] applying database migrations…"
alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"
