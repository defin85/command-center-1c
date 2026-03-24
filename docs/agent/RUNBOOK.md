# Runbook

Статус: authoritative agent-facing guidance.

## Toolchain

Canonical tool versions come from `.tool-versions`:

- Go 1.24.0
- Python 3.13.11
- Node.js 20
- Java temurin-17.0.17+10

## First Local Checks

```bash
bd prime
./debug/runtime-inventory.sh --json
./scripts/dev/health-check.sh
```

## Start And Health

```bash
./scripts/dev/start-all.sh
./scripts/dev/health-check.sh
./debug/probe.sh all
```

## Runtime Control

| Runtime | Start / Restart | Health | Eval |
|---|---|---|---|
| `orchestrator` | `./scripts/dev/restart.sh orchestrator` | `http://localhost:8200/health` | `./debug/eval-django.sh "print('ok')"` |
| `event-subscriber` | `./scripts/dev/restart.sh event-subscriber` | `process-only (pids/event-subscriber.pid)` | `./debug/eval-django.sh "from apps.operations.models import BatchOperation; print(BatchOperation.objects.count())"` |
| `api-gateway` | `./scripts/dev/restart.sh api-gateway` | `http://localhost:8180/health` | `delve via ./scripts/dev/debug-service.sh api-gateway 2345` |
| `worker` | `./scripts/dev/restart.sh worker` | `http://localhost:9191/health` | `delve via ./scripts/dev/debug-service.sh worker 2346` |
| `worker-workflows` | `./scripts/dev/restart.sh worker-workflows` | `http://localhost:9092/health` | `delve via ./scripts/dev/debug-service.sh worker 2346` |
| `frontend` | `./scripts/dev/restart.sh frontend` | `http://localhost:15173` | `./debug/eval-frontend.sh "document.title"` |

## Debug Toolkit

- Runtime inventory: `./debug/runtime-inventory.sh`
- Runtime probes: `./debug/probe.sh all`
- Runtime restart + probe: `./debug/restart-runtime.sh <runtime>`
- Django eval: `./debug/eval-django.sh "<python code>"`
- Frontend eval: `./debug/eval-frontend.sh "<js expression>"`

## Repo Tooling Surfaces

- Codex project config: `.codex/config.toml`
- OpenSpec context: `openspec/project.md`
- Root repo contract: `AGENTS.md`
- Frontend scripts source: `frontend/package.json`
- Dev scripts: `scripts/dev/*`

## When To Use Supplemental Docs

- `README.md` — broader human-readable project overview
- `DEBUG.md` — detailed live-debug and incident recipes
- `scripts/dev/README.md` — long-form notes on dev scripts

