# Task Routing

Статус: authoritative agent-facing guidance.

Этот документ задаёт bounded routing matrix для типовых task families. Начинай с минимально достаточного набора docs, а deeper reads подключай только по явному trigger.

Router rules:
- Если задача bounded и подсистема понятна, не читай весь onboarding bundle: переходи сразу к соответствующей секции ниже.
- Если задача неоднозначна или ты не знаешь текущую структуру репозитория, сначала открой [INDEX.md](./INDEX.md), затем вернись сюда.
- Перед расширением validation scope выбери completion profile в [VERIFY.md](./VERIFY.md).

## Вопросы про продукт и домен

- Минимум для старта:
  - [DOMAIN_MAP.md](./DOMAIN_MAP.md)
  - [ARCHITECTURE_MAP.md](./ARCHITECTURE_MAP.md)
  - [openspec/project.md](../../openspec/project.md)
- Подключай дополнительно, если:
  - [INDEX.md](./INDEX.md) нужен cold-start map по guidance layers
  - [RUNBOOK.md](./RUNBOOK.md) нужен runtime/debug context
  - [VERIFY.md](./VERIFY.md) нужен validation-aware ответ
- Первые code entry points:
  - [frontend/src/App.tsx](../../frontend/src/App.tsx)
  - `openspec/specs/**`
  - `orchestrator/apps/**`
- Проверка:
  - для guidance-only изменений: `./scripts/dev/check-agent-doc-freshness.sh`
  - для OpenSpec changes: `openspec validate <change-id> --strict --no-interactive`
- Machine-readable surfaces:
  - `openspec list`
  - `openspec list --specs`
  - `./debug/runtime-inventory.sh --json`
- Эскалация:
  - нужно различить shipped surface, active change и archived context
  - ответ затрагивает runtime boundary или более одной подсистемы

## Frontend work

- Минимум для старта:
  - [frontend/AGENTS.md](../../frontend/AGENTS.md)
  - [VERIFY.md](./VERIFY.md)
  - [ui-skills.md](./ui-skills.md)
  - root [AGENTS.md](../../AGENTS.md) section `UI Platform Contract`
- Подключай дополнительно, если:
  - [INDEX.md](./INDEX.md) нужен cold-start onboarding map
  - [RUNBOOK.md](./RUNBOOK.md) нужен runtime/restart/eval path
  - нужна live UI incident correlation через `.agents/skills/ui-action-observability/SKILL.md`
- Первые code entry points:
  - [frontend/src/main.tsx](../../frontend/src/main.tsx)
  - [frontend/src/uiGovernanceInventory.js](../../frontend/src/uiGovernanceInventory.js)
  - [frontend/src/App.tsx](../../frontend/src/App.tsx)
  - `frontend/src/components/platform/`
  - `frontend/src/pages/`
- Skill routing:
  - для frontend/UI/UX/browser tasks proactively выбирай минимальный релевантный набор shared UI skills из `/home/egor/.agents/skills/` по [ui-skills.md](./ui-skills.md)
  - при live-runtime debugging или restart flows дополнительно подключай repo-local `.agents/skills/runtime-debug/SKILL.md`
  - если задача про UI incident correlation, `trackUiAction`, `request_id` / `ui_action_id`, export bundle или WebSocket churn diagnostics, подключай repo-local `.agents/skills/ui-action-observability/SKILL.md`
- Проверка:
  - `cd frontend && npm run generate:api`
  - `cd frontend && npm run lint`
  - `cd frontend && npm run test:run -- <path>`
  - `cd frontend && npm run test:browser:ui-platform`
- Machine-readable surfaces:
  - [frontend/package.json](../../frontend/package.json)
  - `./debug/runtime-inventory.sh --json`
  - `./debug/eval-frontend.sh "<js expression>"`
- Эскалация:
  - меняется UI platform contract или route-level page shell governance
  - нужна broader browser/runtime verification, а не только static/doc change

## Orchestrator work

- Минимум для старта:
  - [orchestrator/AGENTS.md](../../orchestrator/AGENTS.md)
  - [VERIFY.md](./VERIFY.md)
  - [RUNBOOK.md](./RUNBOOK.md)
- Подключай дополнительно, если:
  - [INDEX.md](./INDEX.md) нужен полный map guidance layers
  - [DOMAIN_MAP.md](./DOMAIN_MAP.md) нужен domain context
  - `openspec/project.md` нужен spec/change context
- Первые code entry points:
  - [orchestrator/config/asgi.py](../../orchestrator/config/asgi.py)
  - [orchestrator/manage.py](../../orchestrator/manage.py)
  - `orchestrator/apps/`
- Проверка:
  - `./scripts/dev/lint.sh --python`
  - `./scripts/dev/pytest.sh -q <path>`
- Machine-readable surfaces:
  - `./debug/runtime-inventory.sh --json`
  - `./debug/eval-django.sh "<python code>"`
- Эскалация:
  - затронут API contract, background workers или runtime health path
  - change начинает пересекать frontend/go-services boundaries

## Go services work

- Минимум для старта:
  - [go-services/AGENTS.md](../../go-services/AGENTS.md)
  - [VERIFY.md](./VERIFY.md)
  - [RUNBOOK.md](./RUNBOOK.md)
- Подключай дополнительно, если:
  - [INDEX.md](./INDEX.md) нужен полный map guidance layers
  - [DOMAIN_MAP.md](./DOMAIN_MAP.md) нужен product/domain context
  - `openspec/project.md` нужен spec/change context
- Первые code entry points:
  - [go-services/api-gateway/cmd/main.go](../../go-services/api-gateway/cmd/main.go)
  - [go-services/worker/cmd/main.go](../../go-services/worker/cmd/main.go)
  - `go-services/shared/`
- Проверка:
  - `./scripts/dev/lint.sh --go`
  - `cd go-services/api-gateway && go test ./...`
  - `cd go-services/worker && go test ./...`
- Machine-readable surfaces:
  - `./debug/runtime-inventory.sh --json`
  - `./scripts/dev/debug-service.sh api-gateway 2345`
  - `./scripts/dev/debug-service.sh worker 2346`
- Эскалация:
  - затронут contracts, runtime topology или shared packages между сервисами
  - нужен live debug path, а не только code/doc edit

## Contracts и OpenSpec work

- Минимум для старта:
  - [openspec/AGENTS.md](../../openspec/AGENTS.md)
  - [openspec/project.md](../../openspec/project.md)
  - [VERIFY.md](./VERIFY.md)
- Подключай дополнительно, если:
  - [PLANS.md](./PLANS.md) нужен execution plan для multi-step change
  - нужен shared OpenSpec skill из `/home/egor/.agents/skills/openspec-*/SKILL.md`
  - change уже одобрен и должен идти через `bd ready`
- Первые code entry points:
  - `openspec/changes/<change-id>/`
  - `openspec/specs/`
  - `contracts/**`
- Проверка:
  - `openspec validate <change-id> --strict --no-interactive`
  - при docs/guidance change: `./scripts/dev/check-agent-doc-freshness.sh`
- Machine-readable surfaces:
  - `openspec list`
  - `openspec list --specs`
  - `bd ready`
- Эскалация:
  - change затрагивает несколько capabilities или требует отдельный delivery profile
  - найден mandatory gap, который нельзя закрыть без отдельного Beads issue

## Runtime-debug и live verification

- Минимум для старта:
  - [RUNBOOK.md](./RUNBOOK.md)
  - [DEBUG.md](../../DEBUG.md)
  - `.agents/skills/runtime-debug/SKILL.md`
- Подключай дополнительно, если:
  - `.agents/skills/ui-action-observability/SKILL.md` нужен для frontend action journal / request correlation
  - [INDEX.md](./INDEX.md) нужен map по authoritative/supplemental layers
  - [VERIFY.md](./VERIFY.md) нужен validation-aware escalation path
- Первые code entry points:
  - `debug/`
  - `scripts/dev/`
  - runtime entrypoint из `./debug/runtime-inventory.sh --json`
- Проверка:
  - `./debug/runtime-inventory.sh --json`
  - `./scripts/dev/health-check.sh`
  - `./debug/probe.sh all`
- Machine-readable surfaces:
  - `./debug/runtime-inventory.sh --json`
  - `./debug/restart-runtime.sh <runtime>`
  - `./debug/eval-django.sh "<python code>"`
  - `./debug/eval-frontend.sh "<js expression>"`
- Эскалация:
  - нужен restart/live probe и change уже перестаёт быть docs-only
  - инцидент пересекает UI journal, backend correlation и runtime health

## Agent docs и guidance work

- Минимум для старта:
  - root [AGENTS.md](../../AGENTS.md)
  - [INDEX.md](./INDEX.md)
  - [VERIFY.md](./VERIFY.md)
- Подключай дополнительно, если:
  - [TASK_ROUTING.md](./TASK_ROUTING.md) меняется вместе с task family routing
  - [MEMORY.md](./MEMORY.md) меняется manual Hindsight workflow или note taxonomy
  - [ui-skills.md](./ui-skills.md) затрагивается frontend/UI guidance
  - [RUNBOOK.md](./RUNBOOK.md) нужен runtime/debug surface
- Первые code entry points:
  - `docs/agent/*`
  - [AGENTS.md](../../AGENTS.md)
  - [frontend/AGENTS.md](../../frontend/AGENTS.md)
  - [orchestrator/AGENTS.md](../../orchestrator/AGENTS.md)
  - [go-services/AGENTS.md](../../go-services/AGENTS.md)
  - [scripts/dev/check-agent-doc-freshness.py](../../scripts/dev/check-agent-doc-freshness.py)
- Проверка:
  - `./scripts/dev/check-agent-doc-freshness.sh`
  - если guidance меняется в рамках OpenSpec change: `openspec validate <change-id> --strict --no-interactive`
- Machine-readable surfaces:
  - [frontend/package.json](../../frontend/package.json)
  - `./debug/runtime-inventory.sh --json`
  - [.codex/config.toml](../../.codex/config.toml)
- Эскалация:
  - конфликтует source-of-truth ownership между root, routed и scoped guidance
  - change начинает требовать правки scoped `AGENTS.md` или OpenSpec delivery contract
