## 1. Canonical agent onboarding surface
- [ ] 1.1 Ввести стабильный canonical agent-facing documentation surface в `docs/agent/INDEX.md` и supporting docs в `docs/agent/*`, который явно объявлен canonical entry point для нового агента.
- [ ] 1.2 Разметить существующие onboarding/legacy docs как `authoritative`, `supplemental` или `legacy`, чтобы у нового агента не было конкурирующих “первых точек входа”.
- [ ] 1.3 Обновить `openspec/project.md`, чтобы project context и key entry points ссылались на новый canonical agent-facing path, а не на legacy onboarding layers.

## 2. Guidance layering
- [ ] 2.1 Сжать корневой `AGENTS.md` до практической repo map: что это за проект, где entry points, как запускать/проверять изменения, какие инварианты обязательны.
- [ ] 2.2 Сохранить в корневом `AGENTS.md` обязательные inline contracts из существующих capabilities, включая UI platform contract.
- [ ] 2.3 Добавить scoped `AGENTS.md` для `frontend/`, `orchestrator/` и `go-services/` с локальными entry points, verification paths и subsystem-specific constraints.

## 3. Agent-facing references
- [ ] 3.1 Добавить architecture map для нового агента: major subsystems, allowed call graph, ключевые каталоги и entry points.
- [ ] 3.2 Добавить runbook и verification guide, собранные из фактических script/package entry points и debug toolkit.
- [ ] 3.3 Явно задокументировать machine-readable inventories и Codex-specific repo surfaces, включая `.codex/config.toml` и `debug/runtime-inventory.sh --json`.

## 4. Workflow assets
- [ ] 4.1 Добавить execution-plan template (`PLANS.md` или эквивалентный stable path) для длинных multi-step задач.
- [ ] 4.2 Добавить review checklist (`code_review.md` или эквивалентный stable path) и сослаться на него из agent guidance.
- [ ] 4.3 Упаковать самые дорогие повторяемые workflows в shared team skills в `.agents/skills` с trigger phrases, inputs/outputs и verification steps.

## 5. Freshness automation
- [ ] 5.1 Ввести machine-checkable freshness checks для authoritative agent docs против реальных source-of-truth inputs: `.tool-versions`, `debug/runtime-inventory.sh --json`, `scripts/dev/*`, `frontend/package.json` и checked-in file paths.
- [ ] 5.2 Интегрировать эти checks в минимальный blocking validation path, чтобы drift по версиям, портам, командам и ссылкам не проходил незамеченным.

## 6. Validation
- [ ] 6.1 Прогнать новые doc/skill/freshness checks и минимальный набор связанных validation commands.
- [ ] 6.2 Прогнать `openspec validate add-codex-agent-productivity-foundation --strict --no-interactive`.
