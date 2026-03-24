# Agent Guidance Index

Статус: authoritative agent-facing guidance.

Этот каталог является canonical onboarding surface для нового агента, который начинает работу из корня репозитория.

## Что читать первым

1. [ARCHITECTURE_MAP.md](./ARCHITECTURE_MAP.md)
2. [DOMAIN_MAP.md](./DOMAIN_MAP.md)
3. [RUNBOOK.md](./RUNBOOK.md)
4. [VERIFY.md](./VERIFY.md)
5. [TASK_ROUTING.md](./TASK_ROUTING.md)
6. [PLANS.md](./PLANS.md)
7. [code_review.md](./code_review.md)

## Вопросы первых 10 минут

- Что это за проект:
  - control plane для массовых операций по 1С-базам через `frontend -> api-gateway -> orchestrator -> worker -> 1C`
- Где product/domain context:
  - см. [DOMAIN_MAP.md](./DOMAIN_MAP.md)
- Где entry points:
  - `frontend/src/main.tsx`
  - `go-services/api-gateway/cmd/main.go`
  - `go-services/worker/cmd/main.go`
  - `orchestrator/config/asgi.py`
- Как запускать и проверять:
  - см. [RUNBOOK.md](./RUNBOOK.md)
  - см. [VERIFY.md](./VERIFY.md)
- Как выбрать первый рабочий маршрут для задачи:
  - см. [TASK_ROUTING.md](./TASK_ROUTING.md)
- Где workflow intent:
  - `openspec/`
  - `openspec/project.md`
- Где live task graph:
  - `.beads/`
  - `bd ready`

## Authoritative / Supplemental / Legacy

### Authoritative

- `AGENTS.md`
- `docs/agent/*`
- `frontend/AGENTS.md`
- `orchestrator/AGENTS.md`
- `go-services/AGENTS.md`
- `openspec/project.md`

### Supplemental

- `README.md`
- `DEBUG.md`
- `scripts/dev/README.md`

### Legacy / Non-Authoritative

- `docs/START_HERE.md`
- `docs/INDEX.md`
- `docs/DEBUG_WITH_AI.md`
- `CLAUDE.md`
- `.claude/README.md`
- `.claude/rules/**`

Legacy documents могут сохранять полезный исторический контекст, но не являются canonical onboarding path. Если они конфликтуют с этой поверхностью, источником истины считается `docs/agent/*` и root `AGENTS.md`.

## Machine-Readable Surfaces

- Codex repo config: `.codex/config.toml`
- Runtime inventory: `./debug/runtime-inventory.sh --json`
- Runtime probes and eval helpers: `./debug/probe.sh all`, `./debug/eval-django.sh`, `./debug/eval-frontend.sh`
- Frontend validation scripts: `frontend/package.json`
- Dev scripts: `scripts/dev/*`

## Scoped Guidance

- `frontend/AGENTS.md`
- `orchestrator/AGENTS.md`
- `go-services/AGENTS.md`

## Shared Team Skills

Открывай конкретный `SKILL.md` только когда routed task совпадает с его workflow.

- `runtime-debug` — `.agents/skills/runtime-debug/SKILL.md`
- `pool-run-verification` — `.agents/skills/pool-run-verification/SKILL.md`
- `openspec-change-delivery` — `.agents/skills/openspec-change-delivery/SKILL.md`

## OpenSpec And Beads

- OpenSpec intent: `openspec/changes/<change-id>/`
- Active change list: `openspec list`
- Existing specs: `openspec list --specs`
- Execution graph: `bd ready`, `bd show <id>`
