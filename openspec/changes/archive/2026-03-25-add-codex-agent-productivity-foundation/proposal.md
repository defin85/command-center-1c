# Change: Ввести agent-facing foundation для продуктивной работы Codex в репозитории

## Почему
Сейчас в репозитории уже есть сильные agent-facing артефакты, но они не собраны в один понятный вход:
- `openspec/project.md` даёт лучший high-level summary проекта;
- `DEBUG.md` и `debug/runtime-inventory.sh --json` дают лучший runtime/runbook слой;
- `scripts/dev/*` и `frontend/package.json` содержат рабочие команды запуска, проверки и валидации.

При этом новый агент попадает в перегруженный корневой `AGENTS.md`, а затем сталкивается с несколькими устаревшими или конкурирующими doc layers (`docs/START_HERE.md`, `docs/INDEX.md`, `.claude/*`, `docs/DEBUG_WITH_AI.md`, части `README.md`, `Makefile`). В результате первые минуты работы тратятся не на решение задачи, а на различение "что в репозитории является текущим source of truth, а что осталось как legacy context".

Это снижает продуктивность Codex в четырёх ключевых сценариях:
- понять проект и его границы с первого захода;
- найти entry points и корректные команды запуска/проверки;
- безопасно выполнять длинные multi-step задачи;
- не опираться на устаревшие документы и hidden config/tooling surfaces.

## Что меняется
- Вводится canonical agent-facing onboarding surface для нового агента с явным source-of-truth contract в `docs/agent/INDEX.md` и supporting docs в `docs/agent/*`.
- Корневой `AGENTS.md` упрощается до практической карты репозитория и ссылки на deeper docs, не теряя обязательные inline contracts вроде UI platform contract.
- Для ключевых подсистем вводятся scoped `AGENTS.md`, чтобы локальные правила, entry points и verification paths были ближе к месту работы.
- Появляется набор agent-facing reference artifacts: architecture map, runbook, verification guide, execution-plan template, review checklist.
- Повторяемые repo workflows оформляются как shared team skills в `.agents/skills`.
- Для authoritative agent docs вводятся machine-checkable freshness checks, чтобы drift по версиям, портам, командам и ссылкам не проходил незамеченным.
- `openspec/project.md` синхронизируется с новой canonical agent guidance surface и перестаёт направлять агента в legacy onboarding paths как в key entry points.
- Legacy/non-authoritative doc layers получают явный статус, чтобы новый агент не воспринимал их как равноправный onboarding path.

## Impact
- Affected specs:
  - `agent-repository-guidance` (new)
  - `agent-workflow-assets` (new)
  - `agent-doc-freshness` (new)
- Related existing specs:
  - `ui-frontend-governance` — change должен сохранить явный inline UI contract в корневом `AGENTS.md`
- Affected areas:
  - `AGENTS.md`
  - `openspec/project.md`
  - `docs/**` и новый canonical agent docs surface
  - `.agents/skills/**`
  - `.codex/config.toml` visibility/discoverability docs
  - `debug/runtime-inventory.sh` как machine-readable input в doc/tooling checks
  - validation/CI scripts для doc freshness
- Non-goals:
  - не менять runtime behavior продукта;
  - не рефакторить бизнес-логику сервисов ради "архитектурной красоты";
  - не переписывать всю историческую документацию проекта в рамках одного change;
  - не делать Codex-only workflow ценой несовместимости с другими agentic surfaces
