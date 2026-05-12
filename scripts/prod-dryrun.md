# Production stack — dry-run locally (no VPS, no domain)

The goal: validate `docker-compose.prod.yml` + production Dockerfiles end-to-end
on your laptop before pushing the same artefacts to the Hostinger VPS.

This is what the VPS deploy will do, minus the **public DNS + Let's Encrypt
challenge** (Caddy can't get a real cert for `localhost` — it will fall back
to its internal CA, which produces self-signed certs the browser doesn't
trust). For dry-run we therefore hit Caddy over plain HTTP on port 80.

## Steps

```bash
# 1. Make sure Docker Desktop is running
docker info --format "{{.ServerVersion}}"

# 2. Copy the prod env template and fill in real values
cd "d:/myProjects/Sport-Edge Pro"
cp .env.prod.example .env.prod
# Open .env.prod and replace:
#   PUBLIC_DOMAIN         — for dry-run set to "localhost"
#   ACME_EMAIL            — any address (won't be used over HTTP)
#   POSTGRES_PASSWORD     — strong random (openssl rand -base64 32)
#   JWT_SECRET_KEY        — strong random (openssl rand -hex 48)
#   DEFAULT_USER_EMAIL    — your email
#   DEFAULT_USER_PASSWORD — your initial password (change after first login)
# Leave VITE_API_BASE_URL=/api/v1 (same-origin via Caddy).

# 3. Stop the dev stack first so ports 80/443 + 5433 don't clash
docker compose down

# 4. Bring up the prod stack
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build

# 5. Watch the backend log — entrypoint.sh runs `alembic upgrade head`
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f backend
# Expect lines like:
#   [entrypoint] applying database migrations…
#   INFO  [alembic.runtime.migration] Running upgrade 0005 -> 0006_market_type
#   INFO  app.lifespan startup version=0.1.0 env=prod
# Press Ctrl-C to stop tailing once you see startup.

# 6. Smoke-check from the host (HTTP, no TLS in dry-run)
curl -fsS http://localhost/healthz
# → "ok"

# 7. Login round-trip
curl -fsS -X POST http://localhost/api/v1/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email":"you@domain.tld","password":"your-prod-password"}' \
    | head -c 80
# → {"access_token":"eyJhbGc…

# 8. Browser smoke
# Open http://localhost in a private window. Login, then visit /settings —
# Bankroll + Preferences + Import/Export + Obsidian panels should render
# against the production bundle.

# 9. Tear down
docker compose --env-file .env.prod -f docker-compose.prod.yml down
rm .env.prod          # don't leave secrets in working dir
```

> Tip — `PUBLIC_DOMAIN=localhost` makes Caddy fall back to its internal
> CA (no LE challenge attempt). For an even closer-to-prod dry-run, point
> a `*.localhost` subdomain via your `/etc/hosts` and set
> `PUBLIC_DOMAIN=sportedge.localtest.me` (resolves to 127.0.0.1) — still
> no LE cert, but you get the right host header end-to-end.

## What this dry-run validates

| Concern | Verified |
|---|---|
| `Dockerfile.prod` builds (no compile errors, no missing deps) | ✓ |
| Non-root user `sportedge` runs the backend | ✓ |
| Alembic migrations run on first boot via `entrypoint.sh` | ✓ |
| Caddy serves the SPA + proxies `/api/*` correctly | ✓ |
| Frontend binds 80 + 443 (public) — postgres + backend stay internal | ✓ |
| Postgres has no host port → can't reach from outside | ✓ |
| Healthchecks pass on all three services | ✓ |

## What this dry-run does NOT cover

- Real Let's Encrypt cert acquisition: requires a public DNS record + port
  80 reachable from the LE servers. Tested only on the VPS.
- DNS / public subdomain: `localhost` only.
- Real-world inotify on a Linux VPS filesystem (the dev WSL2 case may
  hit the DrvFs polling fallback — see `app/services/obsidian/watcher.py`).
- VPS-side log rotation / disk usage / cron-based pg_dump backups (see
  `docs/deploy-hostinger.md` for the cron template).

## When you have a domain + VPS

Same `docker-compose.prod.yml` + `.env.prod` work on the VPS, just with
`PUBLIC_DOMAIN=sportedge.mauriziomolinari.cloud` and a real `ACME_EMAIL`.
Caddy auto-fetches the LE cert on first start. Follow
`docs/deploy-hostinger.md` for the full walkthrough, or run
`.\deploy.ps1 -Mode init` from the repo root on Windows to orchestrate
it end-to-end.
