# Project Context

## Purpose
CommandCenter1C is a microservices control plane for centralized management and bulk operations across hundreds of 1C:Enterprise databases (target scale: 700+ 1C:Accounting 3.0 infobases). It provides orchestration, templates, and real-time monitoring for operations executed in parallel.

## Tech Stack
- Go 1.24: API Gateway + Worker services in `go-services/` (Gin, Redis client, Watermill, Prometheus, OpenTelemetry)
- Python 3.13 (see `.tool-versions`): Django + DRF (Orchestrator), Channels (WebSocket), drf-spectacular (OpenAPI), SimpleJWT, Jinja2
- Frontend: Node.js 20, React 18 + TypeScript (Vite), Ant Design / Pro Components, React Query, Zustand, Socket.IO client
- Data/Infra: PostgreSQL 15, Redis 7 (queue/pubsub/streams), ClickHouse (optional analytics), Docker Compose, Kubernetes manifests in `infrastructure/`
- Observability: Prometheus + Grafana, OpenTelemetry; Jaeger used in some dev setups
- Contract-first API: OpenAPI specs in `contracts/**` + code generation (Go/Python/TypeScript clients/types)

## Project Conventions

### Code Style
- Single source of truth for tool versions: `.tool-versions` (asdf/mise)
- Documentation is mostly in Russian; key entry points: `README.md`, `docs/START_HERE.md`, `docs/ROADMAP.md`, `.claude/rules/*`
- Go:
  - Formatting: `gofmt` (see `make format-go`)
  - Checks: `go vet` / `golangci-lint` (see `Makefile`, `scripts/dev/lint.sh`)
  - Prefer building binaries via `scripts/dev/*` (avoid `go run` in dev)
  - Structure: `cmd/` entrypoint + `internal/` for private code; shared code only in `go-services/shared/`
- Python (Orchestrator):
  - Primary linter: `ruff` (`scripts/dev/lint.sh` runs `ruff check .`)
  - Tests: `pytest` (see `orchestrator/pytest.ini`)
  - Django apps live under `orchestrator/apps/*` and should stay independent (avoid cross-app imports)
- Frontend:
  - TypeScript strictness enforced by `tsc` and ESLint (`frontend/eslint.config.js`)
  - Avoid static `antd` `message/notification` and `Modal.*` calls; use `App.useApp()` APIs instead (enforced by ESLint rules)
  - Generated API client lives under `frontend/src/api/generated/**` (ignored by lint)
- API naming:
  - Request params and JSON fields use `snake_case` (aligns Go/Python)
  - Prefer action-based `/api/v2/*` endpoints; v1 endpoints are deprecated per docs

### Architecture Patterns
- Allowed call graph:
  - `frontend` -> `api-gateway` -> `orchestrator` -> (`postgres`, `redis`) -> `worker` -> (OData / RAS) -> 1C
  - Frontend must not call Orchestrator directly (always through API Gateway).
  - Workers pull work from Redis; they are not called directly.
- Contract-first API:
  - Change OpenAPI in `contracts/**` first, then validate + regenerate clients/types (see `.githooks/README.md`, `contracts/README.md`).
- Local development defaults to "hybrid" mode:
  - Infrastructure in Docker (`docker-compose.local.yml`)
  - App services on host via `scripts/dev/start-all.sh`
  - Mode is driven by `USE_DOCKER` in `.env.local` (see `.claude/rules/setup.md`)
- Event-driven pieces use Redis (Pub/Sub/Streams) and Watermill (Go libraries)

### Testing Strategy
- Lint/quick checks:
  - `./scripts/dev/lint.sh` (TypeScript: `tsc` + ESLint; Python: ruff; Go: go vet)
  - `make test` runs component tests (Go/Python/Frontend)
- Unit/integration tests:
  - Django: `pytest` (tests under `orchestrator/apps/**/tests/`)
  - Go: `go test ./...` per service (`go-services/<service>/`)
  - Frontend: `vitest` (`npm test`, `npm run test:coverage`) and Playwright (`npm run test:browser`)
- Coverage targets (project rules): Django/Go > 70%, React > 60% (see `.claude/rules/testing.md`)

### Git Workflow
- Workflow: single branch `master` (changes are committed directly to `master`)
- Keep commits small and incremental; run `./scripts/dev/lint.sh` and relevant tests before pushing
- Enable repo hooks for OpenAPI contract validation/codegen:
  - `git config core.hooksPath .githooks`
- When editing `contracts/**`, ensure generated code updates are included in the same change

## Domain Context
- 1C:Enterprise (1C:Accounting 3.0) operations at scale (hundreds of infobases)
- Key integrations:
  - OData for business data operations (batching is important)
  - RAS (Remote Administration Server) for cluster/infobase administration tasks
- Workloads are long-running and require progress tracking + real-time status updates

## Important Constraints
- 1C transaction time must stay under ~15 seconds; split long operations into multiple short transactions
- Limit concurrent connections per infobase (typical: 3-5)
- Prefer OData `$batch` in the 100-500 records range per batch
- Default rate limiting is enforced at the gateway (see `.claude/rules/critical.md`; typical: 100 req/min per user)
- Dev ports are chosen to avoid Windows reserved ranges; common ports in hybrid dev:
  - 15173 (frontend), 8180 (api-gateway), 8200 (orchestrator), 5432 (postgres), 6379 (redis)

## External Dependencies
- 1C:Enterprise environment:
  - 1C OData endpoints for each managed infobase
  - 1C RAS server (default port 1545) reachable from the runtime environment
  - Local dev may require `EXE_1CV8_PATH` in `.env.local` for 1C CLI tooling
- Infrastructure services:
  - PostgreSQL and Redis are required
  - ClickHouse, Prometheus, Grafana, Jaeger are optional depending on dev mode
