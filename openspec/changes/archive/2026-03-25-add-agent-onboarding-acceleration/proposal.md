# Change: Ускорить product/domain onboarding и маршрутизацию задач для агента

## Почему
`add-codex-agent-productivity-foundation` закрыл главный structural gap: новый агент теперь быстрее находит authoritative docs, runtime map и verification paths. Но в первых 10-15 минутах работы всё ещё остаются три дорогих пробела:

- agent guidance хорошо объясняет устройство репозитория, но не даёт короткой domain/product карты: что уже реализовано, какие operator workflows ключевые, какие сущности важны;
- нет одного bounded asset, который маршрутизирует типовые task families в правильные docs, кодовые entry points и verification paths;
- freshness checks ловят drift по путям, версиям и строковым reference values, но почти не проверяют, остаются ли ключевые reference commands достаточно "живыми", чтобы guidance можно было продолжать считать trustworthy.

Из-за этого даже после успешного onboarding новый агент всё ещё тратит лишнее время на реконструкцию domain context и ручной выбор первого рабочего маршрута для задачи.

## Что меняется
- Добавляется краткая product/domain карта для агента в stable checked-in path.
- Добавляется task routing matrix для типовых task families с первыми docs/code/test entry points.
- Canonical agent guidance обновляется так, чтобы новые assets были discoverable из root onboarding surface.
- Freshness automation усиливается до semantic/behavioral checks для критичных guidance references, где возможна дешёвая недеструктивная проверка.

## Impact
- Affected specs:
  - `agent-onboarding-acceleration` (new)
- Related changes:
  - `add-codex-agent-productivity-foundation`
- Affected areas:
  - `docs/agent/*`
  - `AGENTS.md`
  - `frontend/AGENTS.md`
  - `orchestrator/AGENTS.md`
  - `go-services/AGENTS.md`
  - `scripts/dev/check-agent-doc-freshness.py`
  - `scripts/dev/check-agent-doc-freshness.sh`
- Non-goals:
  - не переписывать весь docs corpus проекта;
  - не превращать routing matrix в полный cookbook на все случаи;
  - не менять runtime behavior продукта или OpenSpec/Beads workflow;
  - не добавлять новые shared skills без отдельной подтверждённой необходимости.
