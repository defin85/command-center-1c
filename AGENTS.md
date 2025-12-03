Always response on russian

# Repository Guidelines

## Project Structure & Module Organization
- `go-services/` — Go microservices (`api-gateway`, `worker`, `cluster-service`, `batch-service`); binaries land in `bin/`.
- `orchestrator/` — Django/DRF apps in `apps/`, settings in `config/`, Celery tasks alongside Django code.
- `frontend/` — React + TypeScript with sources in `src/`, assets in `public/`.
- `docs/` — Architecture, API contracts, and runbooks; start with `docs/START_HERE.md` and `docs/LOCAL_DEVELOPMENT_GUIDE.md`.
- Infra and tooling in `infrastructure/`, `docker-compose*.yml`, and `scripts/`; service-level tests live beside code, with shared fixtures in `tests/`.

## Build, Test, and Development Commands
- `make setup` — install Go, Python, frontend deps locally.
- `make dev` / `make dev-detached` — run the full stack via Docker Compose; `make restart` for quick reloads.
- `./scripts/dev/start-all.sh [--force-rebuild|--no-rebuild|--parallel-build]` — hybrid workflow for selective rebuilds.
- `make test` — Go (race + coverage), Python (pytest + coverage), and frontend test suite; `make lint` / `make format` for all stacks.
- `make build` builds images; `make logs`, `make stop`, `make clean`, and `make health` manage runtime state.

## Coding Style & Naming Conventions
- Go: `gofmt -s` and `golangci-lint`; packages lowercase, exported symbols PascalCase.
- Python: `black`, `isort`, `flake8`; 4-space indent, `snake_case` modules/functions, `UPPER_SNAKE_CASE` settings.
- Frontend: `npm run lint` / `npm run format`; components PascalCase, hooks `useX`, TypeScript types/interfaces PascalCase, files camel/kebab case under `src/`.
- Config: base env from `.env.local.example`; do not commit secrets or generated keys.

## Testing Guidelines
- Primary: `make test`. Targeted: `cd go-services/<svc> && go test -race -cover ./...`, `cd orchestrator && pytest`, `cd frontend && npm test -- --coverage`.
- Pytest matches `test*.py` / `Test*` / `test_*`; mark DB cases with `@pytest.mark.django_db`. Favor deterministic fixtures and contract tests (see `docs/OPENAPI_CONTRACT_CHECKLIST.md` when touching APIs).
- Keep or raise coverage on auth, task dispatch, and migration-sensitive flows.

## Commit & Pull Request Guidelines
- History favors conventional prefixes (`feat:`, `fix:`, `chore:`) with imperative phrasing; keep scope small and language consistent.
- PRs: summary, linked issue, test results (`make test` or scoped commands), screenshots/CLI output for UI or API changes, plus migrations/specs when relevant; call out breaking changes and env var additions.

## Security & Configuration Tips
- Never commit `.env*`, DB dumps, or `celerybeat-schedule.db`; rotate secrets and store them outside VCS.
- Run `make migrate` before sharing DB-dependent work; use `make clean` to purge local state when packaging changes.
- Ports and expectations live in `docs/PORTS_CONFIGURATION.md`; update docs and compose files when altering them.
