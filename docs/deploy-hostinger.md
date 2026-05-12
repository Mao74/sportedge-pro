# Deploy su VPS Hostinger — guida step-by-step

Walkthrough per la setup target:

- **Dominio**: `mauriziomolinari.cloud`
- **Subdomain SportEdge**: `sportedge.mauriziomolinari.cloud`
- **VPS Hostinger**: IP `187.124.0.133` con Docker già installato
- **TLS**: terminato direttamente da **Caddy** dentro il container frontend,
  con cert Let's Encrypt rinnovato in automatico (no NPM, no reverse proxy
  esterno)
- **openclaw**: container `ghcr.io/hostinger/hvps-openclaw` è l'agent di
  gestione Hostinger della VPS — **non rimuoverlo**, usa la porta `54497`
  e non collide con 80/443

Tempo stimato: ~20 minuti, di cui ~2 minuti per il primo build e ~30s per
l'emissione del cert LE.

---

## 1. DNS — punta il subdomain alla VPS

Sul provider DNS dove gestisci `mauriziomolinari.cloud`:

1. Apri la zona DNS del dominio.
2. Aggiungi un record:

   | Field | Value |
   |---|---|
   | Type | `A` |
   | Host / Name | `sportedge` |
   | Points to / Value | `187.124.0.133` |
   | TTL | `300` (5 min — ti permette di correggere in fretta se sbagli) |

3. Salva.

Verifica propagazione (può richiedere 1-5 minuti):

```bash
dig +short sportedge.mauriziomolinari.cloud
# → deve stampare 187.124.0.133
```

Se non risolve dopo 10 minuti, forza la risoluzione contro un DNS pubblico:
`dig +short @8.8.8.8 sportedge.mauriziomolinari.cloud`. Caddy ha bisogno
che il record sia propagato prima di chiedere il cert a Let's Encrypt
(challenge HTTP-01 su porta 80).

---

## 2. Firewall — apri 80 + 443

Caddy ha bisogno che le porte 80 (challenge ACME + redirect → HTTPS) e
443 (TLS) siano raggiungibili dall'esterno.

```bash
ssh root@187.124.0.133

# Se ufw è attivo:
ufw status
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
# NON aprire altre porte. La 54497 (openclaw) è già aperta dall'agent
# Hostinger e non va toccata. Postgres e backend NON sono pubblicati.

# Se la VPS ha anche un firewall a livello Hostinger (pannello hPanel
# → VPS → Firewall), apri 80/tcp e 443/tcp lato cloud.
```

Verifica che nulla stia già occupando le porte:

```bash
ss -tlnp | grep -E ':(80|443) '
# → deve essere VUOTO. Se vedi nginx/apache/caddy in ascolto, fermalo
#   prima di andare avanti (systemctl stop nginx, ecc.)
```

---

## 3. Prepara la cartella sulla VPS

```bash
ssh root@187.124.0.133

mkdir -p /srv/sportedge
cd /srv/sportedge

# Clone via HTTPS (più semplice del SSH se non hai deploy key sul VPS):
git clone https://github.com/Mao74/sportedge-pro.git .

# Cartella per il vault Obsidian (volume mount)
mkdir -p obsidian-vault
```

---

## 4. Configura `.env.prod`

```bash
cp .env.prod.example .env.prod
nano .env.prod
```

Compila i campi **required**:

```ini
PUBLIC_DOMAIN=sportedge.mauriziomolinari.cloud
ACME_EMAIL=maurizio@mauriziomolinari.cloud

POSTGRES_DB=sportedge
POSTGRES_USER=sportedge
POSTGRES_PASSWORD=<genera con: openssl rand -base64 32>

JWT_SECRET_KEY=<genera con: openssl rand -hex 48>
JWT_ACCESS_TOKEN_TTL_MINUTES=120
JWT_REFRESH_TOKEN_TTL_DAYS=14

DEFAULT_USER_EMAIL=maurizio@mauriziomolinari.cloud
DEFAULT_USER_PASSWORD=<password iniziale — cambiala al primo login>
DEFAULT_STARTING_BANKROLL=1000.00

LOG_LEVEL=INFO
VITE_API_BASE_URL=/api/v1
OBSIDIAN_VAULT_PATH=/srv/sportedge/obsidian-vault
```

Genera i due segreti con un one-liner:

```bash
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32)"
echo "JWT_SECRET_KEY=$(openssl rand -hex 48)"
# copia le righe stampate dentro .env.prod
```

Sicurezza file:

```bash
chmod 600 .env.prod          # leggibile solo da root
```

---

## 5. Build + avvia lo stack

```bash
cd /srv/sportedge

docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build

# Verifica che i 3 servizi siano Up (postgres + backend + frontend)
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

Guarda il backend boot (l'entrypoint applica le migration prima di uvicorn):

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f backend
# Aspetta righe:
#   [entrypoint] applying database migrations…
#   INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial_schema
#   …
#   INFO  [alembic.runtime.migration] Running upgrade 0005 -> 0006_market_type
#   INFO  app.lifespan startup version=0.1.0 env=prod
# Ctrl-C per uscire dal tail.
```

Guarda Caddy ottenere il cert LE:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f frontend
# Cerca:
#   {"level":"info","msg":"obtaining certificate","identifier":"sportedge.mauriziomolinari.cloud"}
#   {"level":"info","msg":"certificate obtained successfully"}
# Se vedi "no challenge solver succeeded": il DNS non si è ancora
# propagato oppure 80/443 non sono raggiungibili dall'esterno.
```

Smoke check dal VPS:

```bash
curl -fsS http://localhost/healthz
# → "ok"

# Lato esterno (sostituisce la chiamata HTTPS — il primo cert può
# richiedere qualche secondo dopo lo start):
curl -fsS https://sportedge.mauriziomolinari.cloud/api/v1/health
# → {"status":"ok","api":"ok","database":"ok","version":"0.1.0"}
```

---

## 6. Verifica finale da fuori la VPS

Dal tuo laptop:

```bash
curl -sS -o /dev/null -w "HTTP %{http_code}\n" https://sportedge.mauriziomolinari.cloud
# → HTTP 200

curl -sS -X POST https://sportedge.mauriziomolinari.cloud/api/v1/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email":"maurizio@mauriziomolinari.cloud","password":"<la-tua-password>"}' \
    | head -c 80
# → {"access_token":"eyJhbGciOi…
```

Apri **https://sportedge.mauriziomolinari.cloud** nel browser → login → dashboard.

---

## 7. Backup automatico Postgres

Aggiungi su `/etc/cron.daily/sportedge-backup` (chmod +x):

```sh
#!/bin/sh
set -eu
ENV_FILE=/srv/sportedge/.env.prod
COMPOSE=/srv/sportedge/docker-compose.prod.yml
DEST_DIR=/var/backups/sportedge
mkdir -p "$DEST_DIR"

set -a; . "$ENV_FILE"; set +a

STAMP=$(date +%F)
docker compose --env-file "$ENV_FILE" -f "$COMPOSE" \
    exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
    | gzip > "$DEST_DIR/sportedge-${STAMP}.sql.gz"

# Tieni 30 giorni di backup
find "$DEST_DIR" -name 'sportedge-*.sql.gz' -mtime +30 -delete
```

Off-site (consigliato): copia `/var/backups/sportedge/*.sql.gz` su un cloud
storage qualunque (rclone, restic, syncthing — a scelta).

Backup vault Obsidian: la cartella `/srv/sportedge/obsidian-vault` è solo
file markdown — rsync o restic su off-site con la stessa logica.

---

## 8. Update workflow

Quando spingi nuove versioni:

```bash
ssh root@187.124.0.133
cd /srv/sportedge
git pull
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f backend
# Verifica che le migration scorrano clean, poi Ctrl-C.
```

Niente downtime visibile per il frontend (Caddy ricarica il bundle al
boot, i cert sopravvivono nel volume `sportedge-caddy-data`). Il backend
ha 2 worker uvicorn → durante il restart il client riceve brevemente
503; quasi sempre <5 secondi.

> Lo script `deploy.ps1` nella root del repo orchestra automaticamente
> `git push` locale + `git pull` + `docker compose up -d --build` sul VPS.
> Vedi sezione successiva.

---

## 9. Script `deploy.ps1` (dal tuo laptop Windows)

Per il workflow di tutti i giorni c'è uno script PowerShell che fa
push + ssh + pull + rebuild + smoke in un comando:

```powershell
# Primo deploy (chiede conferma su .env.prod):
.\deploy.ps1 -Mode init

# Update successivo (git push → pull → rebuild):
.\deploy.ps1

# Solo logs del backend in tail:
.\deploy.ps1 -Mode logs

# Status containers:
.\deploy.ps1 -Mode status
```

Vedi `deploy.ps1` per i dettagli; usa la tua chiave SSH `~/.ssh/id_ed25519`
(o quella configurata in `~/.ssh/config` per host `sportedge-vps`).

---

## 10. Troubleshooting comune

| Sintomo | Probabile causa | Fix |
|---|---|---|
| Caddy: `no challenge solver succeeded` | DNS non propagato OR :80 chiuso sul firewall | `dig sportedge.mauriziomolinari.cloud`; verifica ufw + firewall Hostinger |
| Caddy: `failed to obtain certificate` (rate limit) | Riavviato troppe volte mentre il cert era già ok | `docker compose -f docker-compose.prod.yml restart frontend`; LE ha rate limit di 5 cert/settimana per hostname |
| `502 Bad Gateway` sul subdomain | container backend down | `docker compose logs -f backend`, controlla migration |
| Login OK ma `/api/v1/health` 503 | DB unhealthy o ancora in migration | `logs -f backend`, poi `logs -f postgres` |
| Disco pieno dopo settimane | backup non ruotati | controlla `/var/backups/sportedge` + `docker system df` |
| Watcher Obsidian non triggera | vault path NON bind-mounted | verifica `OBSIDIAN_VAULT_PATH` in `.env.prod` |
| `address already in use` su 80/443 | nginx/apache di sistema attivo | `systemctl stop nginx apache2`, poi ridai `docker compose up` |

---

## 11. Note su openclaw (DO NOT REMOVE)

Sul VPS gira un container `openclaw-wjmp-openclaw-1` da
`ghcr.io/hostinger/hvps-openclaw:latest` con porta `54497` pubblicata.
**Non rimuoverlo**: è l'agent di gestione della VPS Hostinger (monitoring,
metriche, console web di hPanel). Non interferisce con SportEdge perché:

- non lega 80/443
- è su una bridge network separata da `sportedge-net`
- la porta 54497 è dedicata e non riusata da nessuno

Se ti chiedi cosa è quel container, è semplicemente "Hostinger watching
the VPS"; lascialo dov'è.

---

## TL;DR — comandi one-shot

Dal VPS, dopo DNS A record + firewall 80/443 aperti:

```bash
ssh root@187.124.0.133
mkdir -p /srv/sportedge && cd /srv/sportedge
git clone https://github.com/Mao74/sportedge-pro.git .
cp .env.prod.example .env.prod && nano .env.prod   # compila i segreti
chmod 600 .env.prod
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
curl -fsS https://sportedge.mauriziomolinari.cloud/api/v1/health
```

Browser: **https://sportedge.mauriziomolinari.cloud** → login → done.
