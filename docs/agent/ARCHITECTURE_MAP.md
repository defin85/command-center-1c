# Architecture Map

Статус: authoritative agent-facing guidance.

Source of truth for runtime topology: `./debug/runtime-inventory.sh --json`

## High-Level Call Graph

Canonical allowed flow:

`frontend -> api-gateway -> orchestrator -> worker -> 1C`

Дополнительно:
- `orchestrator` работает с `postgres` и `redis`
- `worker` использует OData / RAS для side effects в 1С
- `frontend` не должен обращаться к `orchestrator` напрямую
- `worker` не вызывается напрямую из UI

## Major Directories

- `frontend/` — React/Vite UI и platform-owned page layer
- `go-services/api-gateway/` — внешний HTTP gateway
- `go-services/worker/` — worker binaries и workflow stream processing
- `orchestrator/` — Django orchestration и domain logic
- `contracts/` — OpenAPI contracts и generation inputs
- `debug/` — runtime inventory, probes, eval helpers
- `scripts/dev/` — canonical local start/restart/lint/test scripts

## Runtime Map

| Runtime | Stack | Entrypoint | Responsibility |
|---|---|---|---|
| `frontend` | `react/vite` | `frontend/src/main.tsx` | UI, navigation, operator workflows |
| `api-gateway` | `go/gin` | `go-services/api-gateway/cmd/main.go` | external API, routing, auth, rate limiting |
| `orchestrator` | `python/django/daphne` | `orchestrator/config/asgi.py` | domain logic, API orchestration, persistence |
| `event-subscriber` | `python/django-management-command` | `orchestrator/manage.py run_event_subscriber` | event handling and sidecar processing |
| `worker` | `go` | `go-services/worker/cmd/main.go` | execution of bulk 1C operations |
| `worker-workflows` | `go (same binary, different stream)` | `go-services/worker/cmd/main.go` | workflow stream execution |

## Runtime Interfaces

- `frontend`
  - health: `http://localhost:15173`
- `api-gateway`
  - health: `http://localhost:8180/health`
- `orchestrator`
  - health: `http://localhost:8200/health`
- `worker`
  - health: `http://localhost:9191/health`
- `worker-workflows`
  - health: `http://localhost:9092/health`

## Persistent Inputs And Contracts

- Tool versions: `.tool-versions`
- OpenSpec project context: `openspec/project.md`
- OpenAPI contracts: `contracts/**`
- Runtime inventory: `./debug/runtime-inventory.sh --json`
- Frontend validation source: `frontend/package.json`

