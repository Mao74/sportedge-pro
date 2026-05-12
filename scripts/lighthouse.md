# Lighthouse audit — running it locally

Lighthouse is a Chromium-based audit tool. Run it against the **production**
build of the frontend (not the dev server, which has unminified bundles +
HMR overhead).

## One-time setup

```bash
npm install -g lighthouse@^12
# or use npx: `npx lighthouse@latest …`
```

## Steps

```bash
# 1. Build the production frontend image + serve it
cd "d:/myProjects/Sport-Edge Pro"
cp .env.prod.example .env.prod.test
docker compose --env-file .env.prod.test -f docker-compose.prod.yml up -d --build

# 2. Wait for healthchecks, then login to set a session cookie / token. The
#    dashboard is auth-protected so an unauthenticated Lighthouse run only
#    audits the login page. For a real audit:
#    - Log in via the browser
#    - Copy the access token from localStorage `sportedge:auth`
#    - Inject it as a header in the Lighthouse run, OR run with a fresh
#      profile that's already logged in (chrome-flags --user-data-dir).

# 3. Run Lighthouse against the production URL
#    In dry-run mode the prod stack exposes Caddy on http://localhost (port
#    80). For dry-run set PUBLIC_DOMAIN=localhost in .env.prod.test so Caddy
#    skips the LE challenge.
lighthouse http://localhost/login \
    --output html \
    --output-path ./scripts/lighthouse-login.html \
    --chrome-flags="--headless"

lighthouse http://localhost/ \
    --output html \
    --output-path ./scripts/lighthouse-dashboard.html \
    --chrome-flags="--headless --user-data-dir=/tmp/lh-profile" \
    --extra-headers '{"Authorization":"Bearer <paste-your-access-token>"}'

# 4. Open the HTML reports
start ./scripts/lighthouse-login.html
start ./scripts/lighthouse-dashboard.html

# 5. Tear down
docker compose --env-file .env.prod.test -f docker-compose.prod.yml down
rm .env.prod.test
```

## Targets

Per `CLAUDE.md`'s quality bar, on the dashboard page (after login):

| Category | Target |
|---|---|
| Performance | ≥ 90 |
| Accessibility | ≥ 90 |
| Best Practices | ≥ 90 |
| SEO | (not a hard target — single-user app, no public indexing) |

## Known things already in place (won't regress these)

- `<html lang="it">` + `<meta name="description">` + `theme-color` for dark/light
- Skeleton loaders matched to layout (zero CLS during initial fetch)
- Vite hashed assets with `Cache-Control: public, max-age=31536000, immutable`
  served by Caddy in prod
- Caddy compresses with `gzip` + `zstd`
- Skip-link to `<main id="main-content">`
- `aria-live` on toast region; `role="region"` + `aria-label`
- Icon-only buttons all carry `aria-label`
- Focus rings on every interactive primitive
- Color-coded P/L uses tone classes ≥ AA contrast (verified against
  the design tokens in `frontend/src/styles/global.css`)
