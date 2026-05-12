# SportEdge Pro

Production-grade sports trading journal for a single Betfair Exchange trader.
Football-focused, schema sport-agnostic for future expansion.

> **Status — feature-complete (15 of 15 steps shipped).** Backend +
> frontend + Obsidian integration + production deployment artefacts. See
> [`CLAUDE.md`](CLAUDE.md) for the per-step build log and
> [`docs/implementation-plan.md`](docs/implementation-plan.md) for the
> design source of truth.

## Quick start

Prerequisites: **Docker Desktop** (with Docker Compose v2). On Windows, the
WSL2 backend is recommended.

```bash
# 1. Clone (or open) the project
cd sportedge-pro

# 2. Create your local env file
cp .env.example .env
# (edit .env with real values — at minimum POSTGRES_PASSWORD and JWT_SECRET_KEY)

# 3. Bring the stack up
docker compose up --build
```

When all three containers are healthy:

| URL | What you should see |
|---|---|
| <http://localhost> | Frontend bootstrap page, dark theme applied, "all systems nominal" |
| <http://localhost:8000/api/v1/health> | `{"status": "ok", "api": "ok", "database": "ok", ...}` |
| <http://localhost:8000/api/v1/docs> | Auto-generated OpenAPI / Swagger UI |

To shut everything down:

```bash
docker compose down            # keep the postgres volume
docker compose down -v         # also drop the postgres volume (fresh DB next time)
```

## Repository layout

```
sportedge-pro/
├── CLAUDE.md                  # project memory for Claude Code
├── docs/                      # detailed specs (architecture, frontend, strategies, …)
├── backend/                   # FastAPI + SQLAlchemy 2.0 async + Alembic
│   ├── app/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                  # Vite + React 18 + TypeScript strict + Tailwind v3.4
│   ├── src/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml         # dev stack (this file)
├── .env.example
└── README.md
```

## Tech stack (target)

- **Backend** Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · Alembic ·
  Pydantic v2 · asyncpg · structlog · python-jose · watchfiles
- **Database** PostgreSQL 16
- **Frontend** React 18 · TypeScript strict · Vite · Tailwind v3.4 ·
  Framer Motion · TanStack Query v5 · TanStack Table v8 · Zustand ·
  react-hook-form + zod · Recharts · Lucide
- **Testing** pytest + pytest-asyncio + httpx (backend) · Vitest +
  Testing Library (frontend)
- **Deployment** Docker Compose, self-hosted Hostinger VPS behind Nginx
  Proxy Manager (production artefacts in step 15)

## Development workflow

The dev stack uses live source mounts:

- `backend/app` and `backend/tests` are mounted into `/app/app` and
  `/app/tests`. Uvicorn runs with `--reload`.
- `frontend/src` and the config files are mounted into `/app/...`. Vite
  HMR is enabled with filesystem polling (required on Windows hosts).
- `node_modules` is kept inside the image so host-side installs don't
  conflict with the Linux-built dependencies.

### Running tests

Backend:

```bash
docker compose exec backend pytest
```

(The full test suite arrives over steps 2–7; for now the smoke test
verifies the FastAPI app factory and OpenAPI schema.)

Frontend tests are added in step 8 (Vitest + Testing Library).

### Working without Docker

Optional, but supported:

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate    # PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Frontend (in a second shell)
cd frontend
npm install
npm run dev
```

You'll need a local Postgres reachable at the values in your `.env`.

## Production deployment (Hostinger VPS + Nginx Proxy Manager)

The production stack is in `docker-compose.prod.yml`. It coexists with
other Docker apps on the same VPS by binding only on `127.0.0.1` and
letting **Nginx Proxy Manager (NPM)** terminate TLS on the public
subdomain.

### 1. Prerequisites on the VPS

- Docker Engine + Docker Compose v2 (`docker compose version`).
- A working Nginx Proxy Manager already running (typically on
  ports 80/443/81). NPM and SportEdge share the same Docker daemon
  but live on **different docker networks** — NPM connects to the
  SportEdge container by IP/hostname over its own bridge.
- A DNS A record `sportedge.mauriziomolinari.cloud → <VPS IP>` (or any
  subdomain you prefer — see `docs/deploy-hostinger.md` for the
  step-by-step Hostinger walkthrough).

### 2. Clone + configure

```bash
ssh root@<vps-ip>
mkdir -p /srv/sportedge && cd /srv/sportedge
git clone <your-repo-url> .

cp .env.prod.example .env.prod
# Generate strong secrets:
#   openssl rand -base64 32   → POSTGRES_PASSWORD
#   openssl rand -hex 48      → JWT_SECRET_KEY
nano .env.prod                       # fill in every required value
```

The Obsidian vault path defaults to `/srv/sportedge/obsidian-vault`. If
you want notes to round-trip with a laptop, point `OBSIDIAN_VAULT_PATH`
at a folder synced via Syncthing/iCloud/OneDrive.

### 3. Build and start

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f backend
```

The backend's entrypoint runs `alembic upgrade head` automatically
before starting uvicorn, so the first boot creates the schema and seeds
the default user from `.env.prod`.

### 4. Wire up Nginx Proxy Manager

In the NPM web UI:

1. **Hosts → Proxy Hosts → Add Proxy Host**
2. **Domain Names**: `sportedge.mauriziomolinari.cloud`
3. **Scheme**: `http`
4. **Forward Hostname / IP**: `127.0.0.1`
5. **Forward Port**: the value of `FRONTEND_PROXY_PORT` from your
   `.env.prod` (default `8080`).
6. **Block Common Exploits**: on
7. **Websockets Support**: on (needed for live HMR-style updates if you
   ever add SSE endpoints)
8. **SSL** tab: **Request a new SSL Certificate** with Let's Encrypt,
   force SSL on, HSTS on.
9. Save.

NPM will fetch a cert and start serving the public subdomain. The
SportEdge container itself never touches port 443.

### 5. Coexistence with other Docker apps

- Each app binds on its own loopback port; pick a free
  `FRONTEND_PROXY_PORT` per `.env.prod` to avoid collisions.
- Postgres has **no published port** in `docker-compose.prod.yml` — the
  database is reachable only over the `sportedge-net` docker network.
- Logs rotate at 10 MB × 5 files per service so the VPS disk doesn't
  fill up silently.

### 6. Updating

```bash
cd /srv/sportedge
git pull
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

The new backend image runs migrations on startup; rolling back to the
previous image works because Alembic migrations are idempotent and
implement both `up` and `down`.

### 7. Backups

The Postgres data is on the named volume `sportedge-postgres-data`. A
minimal nightly dump:

```bash
# /etc/cron.daily/sportedge-backup
docker compose --env-file /srv/sportedge/.env.prod \
  -f /srv/sportedge/docker-compose.prod.yml \
  exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | \
  gzip > /var/backups/sportedge-$(date +%F).sql.gz
find /var/backups -name 'sportedge-*.sql.gz' -mtime +30 -delete
```

The Obsidian vault is just a folder on disk — back it up with the rest
of `/srv/sportedge` (rsync to off-site is enough).

For the **full Hostinger-specific walkthrough** (DNS record, NPM proxy
host, Let's Encrypt cert, smoke checks), see
[`docs/deploy-hostinger.md`](docs/deploy-hostinger.md).

## Documentation

Detailed specs live in [`docs/`](docs/):

| File | Purpose |
|---|---|
| [`architecture.md`](docs/architecture.md) | Data model, API surface, configuration |
| [`strategies.md`](docs/strategies.md) | Built-in templates, PnL math, what-if widget |
| [`frontend.md`](docs/frontend.md) | Visual language, primitives, page specs |
| [`obsidian.md`](docs/obsidian.md) | Filesystem integration with Obsidian vaults |
| [`implementation-plan.md`](docs/implementation-plan.md) | The 15-step build sequence |

## License

Private project. All rights reserved.
