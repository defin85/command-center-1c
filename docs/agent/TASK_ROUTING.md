# Task Routing

Статус: authoritative agent-facing guidance.

Этот документ помогает выбрать первый рабочий маршрут для типовой задачи без широкого чтения всего репозитория. Это bounded routing matrix, а не полный cookbook.

Если ты ещё не прошёл canonical onboarding path, сначала открой [INDEX.md](./INDEX.md), а затем вернись сюда за первым маршрутом под конкретную задачу.

## Вопросы про продукт и домен

- Первые docs:
  - [DOMAIN_MAP.md](./DOMAIN_MAP.md)
  - [ARCHITECTURE_MAP.md](./ARCHITECTURE_MAP.md)
  - [openspec/project.md](../../openspec/project.md)
- Первые code entry points:
  - [frontend/src/App.tsx](../../frontend/src/App.tsx)
  - `openspec/specs/**`
  - `orchestrator/apps/**`
- Первые проверки:
  - для guidance-only изменений: `./scripts/dev/check-agent-doc-freshness.sh`
  - для OpenSpec changes: `openspec validate <change-id> --strict --no-interactive`
- Machine-readable surfaces:
  - `openspec list`
  - `openspec list --specs`
  - `./debug/runtime-inventory.sh --json`

## Frontend work

- Первые docs:
  - [frontend/AGENTS.md](../../frontend/AGENTS.md)
  - [VERIFY.md](./VERIFY.md)
  - [ui-skills.md](./ui-skills.md)
  - root [AGENTS.md](../../AGENTS.md) section `UI Platform Contract`
- Первые code entry points:
  - [frontend/src/main.tsx](../../frontend/src/main.tsx)
  - [frontend/src/App.tsx](../../frontend/src/App.tsx)
- `frontend/src/components/platform/`
- `frontend/src/pages/`
- Skill routing:
  - для frontend/UI/UX/browser tasks proactively выбирай минимальный релевантный набор shared UI skills из `/home/egor/.agents/skills/` по [ui-skills.md](./ui-skills.md)
  - при live-runtime debugging или restart flows дополнительно подключай repo-local `.agents/skills/runtime-debug/SKILL.md`
- Первые проверки:
  - `cd frontend && npm run generate:api`
  - `cd frontend && npm run lint`
  - `cd frontend && npm run test:run -- <path>`
  - `cd frontend && npm run test:browser:ui-platform`
- Machine-readable surfaces:
  - [frontend/package.json](../../frontend/package.json)
  - `./debug/runtime-inventory.sh --json`
  - `./debug/eval-frontend.sh "<js expression>"`

## Orchestrator work

- Первые docs:
  - [orchestrator/AGENTS.md](../../orchestrator/AGENTS.md)
  - [RUNBOOK.md](./RUNBOOK.md)
  - [VERIFY.md](./VERIFY.md)
- Первые code entry points:
  - [orchestrator/config/asgi.py](../../orchestrator/config/asgi.py)
  - [orchestrator/manage.py](../../orchestrator/manage.py)
  - `orchestrator/apps/`
- Первые проверки:
  - `./scripts/dev/lint.sh --python`
  - `./scripts/dev/pytest.sh -q <path>`
- Machine-readable surfaces:
  - `./debug/runtime-inventory.sh --json`
  - `./debug/eval-django.sh "<python code>"`

## Go services work

- Первые docs:
  - [go-services/AGENTS.md](../../go-services/AGENTS.md)
  - [RUNBOOK.md](./RUNBOOK.md)
  - [VERIFY.md](./VERIFY.md)
- Первые code entry points:
  - [go-services/api-gateway/cmd/main.go](../../go-services/api-gateway/cmd/main.go)
  - [go-services/worker/cmd/main.go](../../go-services/worker/cmd/main.go)
  - `go-services/shared/`
- Первые проверки:
  - `./scripts/dev/lint.sh --go`
  - `cd go-services/api-gateway && go test ./...`
  - `cd go-services/worker && go test ./...`
- Machine-readable surfaces:
  - `./debug/runtime-inventory.sh --json`
  - `./scripts/dev/debug-service.sh api-gateway 2345`
  - `./scripts/dev/debug-service.sh worker 2346`

## Contracts и OpenSpec work

- Первые docs:
  - [openspec/AGENTS.md](../../openspec/AGENTS.md)
  - [openspec/project.md](../../openspec/project.md)
  - [PLANS.md](./PLANS.md)
  - shared OpenSpec skills: `/home/egor/.agents/skills/openspec-*/SKILL.md`
- Первые code entry points:
  - `openspec/changes/<change-id>/`
  - `openspec/specs/`
  - `contracts/**`
- Первые проверки:
  - `openspec validate <change-id> --strict --no-interactive`
  - при docs/guidance change: `./scripts/dev/check-agent-doc-freshness.sh`
- Machine-readable surfaces:
  - `openspec list`
  - `openspec list --specs`
  - `bd ready`

## Runtime-debug и live verification

- Первые docs:
  - [RUNBOOK.md](./RUNBOOK.md)
  - [DEBUG.md](../../DEBUG.md)
  - `.agents/skills/runtime-debug/SKILL.md`
- Первые code entry points:
  - `debug/`
  - `scripts/dev/`
  - runtime entrypoint из `./debug/runtime-inventory.sh --json`
- Первые проверки:
  - `./debug/runtime-inventory.sh --json`
  - `./scripts/dev/health-check.sh`
  - `./debug/probe.sh all`
- Machine-readable surfaces:
  - `./debug/runtime-inventory.sh --json`
  - `./debug/restart-runtime.sh <runtime>`
  - `./debug/eval-django.sh "<python code>"`
  - `./debug/eval-frontend.sh "<js expression>"`

## Agent docs и guidance work

- Первые docs:
  - [INDEX.md](./INDEX.md)
  - [DOMAIN_MAP.md](./DOMAIN_MAP.md)
  - [RUNBOOK.md](./RUNBOOK.md)
  - [VERIFY.md](./VERIFY.md)
  - [ui-skills.md](./ui-skills.md), если change затрагивает frontend/UI guidance
- Первые code entry points:
  - `docs/agent/*`
  - [AGENTS.md](../../AGENTS.md)
  - [frontend/AGENTS.md](../../frontend/AGENTS.md)
  - [orchestrator/AGENTS.md](../../orchestrator/AGENTS.md)
  - [go-services/AGENTS.md](../../go-services/AGENTS.md)
  - [scripts/dev/check-agent-doc-freshness.py](../../scripts/dev/check-agent-doc-freshness.py)
- Первые проверки:
  - `./scripts/dev/check-agent-doc-freshness.sh`
  - если guidance меняется в рамках OpenSpec change: `openspec validate <change-id> --strict --no-interactive`
- Machine-readable surfaces:
  - [frontend/package.json](../../frontend/package.json)
  - `./debug/runtime-inventory.sh --json`
  - [.codex/config.toml](../../.codex/config.toml)
