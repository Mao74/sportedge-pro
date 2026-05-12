# GitHub Actions — CI

`ci.yml` runs on every push / PR to `main` or `develop`:

- **Backend job**: spins up a Postgres 16 sidecar, installs `backend/`
  with dev extras, runs `alembic upgrade head`, then `pytest` + `ruff`.
- **Frontend job**: installs `frontend/` deps (prefers `npm ci` when a
  lockfile is present), runs `tsc --noEmit`, then a production
  `vite build`.

## First push

Once you've created the repo `Mao74/sportedge-pro` on GitHub:

```bash
cd "d:/myProjects/Sport-Edge Pro"
git init
git remote add origin git@github.com:Mao74/sportedge-pro.git
git checkout -b main
git add .
git commit -m "Initial commit — SportEdge Pro feature-complete"
git push -u origin main
```

The workflow will fire automatically and you'll see the run in the repo's
**Actions** tab.

## Notes

- `concurrency` cancels superseded runs on the same branch, so a fast
  push doesn't burn minutes on a stale commit.
- The frontend job's first run will be slow because there's no committed
  `package-lock.json` yet — when you commit one (after running
  `npm install` locally and pushing the resulting lockfile), `npm ci`
  kicks in for a deterministic, faster install.
- Test isolation in CI is the same as locally: the autouse `reset_db`
  fixture truncates + reseeds before each test.
