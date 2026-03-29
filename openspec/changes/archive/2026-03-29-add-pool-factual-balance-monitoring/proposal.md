# Change: Добавить factual balance monitoring и batch intake для pool-run процесса

## Why
Текущий pool runtime уже умеет рассчитывать и публиковать run, но операторский контур ограничен run-local отчётом по расчёту и публикации. Целевой бизнес-процесс требует другого уровня автоматизации: принимать внешние реестры поступлений и реализаций в произвольном формате, запускать распределение от выбранной бухгалтером стартовой организации и затем показывать бухгалтерам near-real-time фактический баланс по пулу на основе реальных данных ИБ.

Без отдельного batch intake и централизованной factual balance projection пользователи не смогут быстро увидеть, где сумма дошла до leaf-узлов, где она зависла, какие суммы уже закрыты реализациями и что переносится в следующий квартал.

## What Changes
- Добавить pool-scoped batch intake для внешних реестров поступлений и реализаций с произвольным форматом через `Pool Schema Templates` и будущие integration adapters.
- Расширить top-down run contract: запуск от явной стартовой организации, `one batch = one pool_run`, batch/run provenance и отделение batch settlement status от существующего `PoolRun.status`.
- Добавить централизованную factual balance projection по `pool + organization + edge + quarter + batch` на основе фактических документов и регистров ИБ.
- Зафиксировать целевой архитектурный вариант `B`: расширение текущих `orchestrator + worker` границ без отдельного factual microservice или нового primary runtime; внутри этих границ change раскладывается на три изолированные подсистемы: `intake`, `factual read/projection`, `reconcile/review`.
- Зафиксировать ownership подсистем варианта `B`: `orchestrator` владеет batch/projection/review contracts и materialized read model, а `worker` получает отдельные operational lanes `write` и `read/reconcile` внутри текущего runtime family.
- Добавить operator-facing summary/drill-down в отдельном factual workspace внутри существующего frontend приложения, который показывает `вошло`, `вышло`, `остаток`, разбивку `с НДС / без НДС / НДС`, а также где сумма застряла.
- Зафиксировать, что новый factual workspace реализуется через project UI platform layer; если используется `MasterDetail`/catalog-detail композиция, master pane остаётся compact selection surface, а detail/review на narrow viewport открывается через mobile-safe fallback без horizontal overflow.
- Добавить quarter carry-forward для незакрытого остатка на том же узле и explicit review queue для документов без traceability, которые нельзя автоматически привязать к конкретному pool/batch.
- Уточнить, что существующий run report остаётся runtime/local отчётом по расчёту и публикации и не подменяет factual balance dashboard.

## Implementation Readiness
Audit verdict: `Ready with conditions`.

Change может переходить в implementation phase только при следующих условиях:
- сохраняется вариант `B` внутри текущих `orchestrator + worker + frontend` boundaries;
- public/domain contracts для `PoolBatch`, batch-backed `top_down`, factual API/read-model surface и `CCPOOL:v=1;...` фиксируются до начала кодинга runtime и UI;
- factual projection, batch settlement и review queue остаются отдельным `orchestrator`-owned boundary и не встраиваются в existing execution store `PoolRun`;
- pilot/preflight cohort ИБ подтверждает published 1C integration surfaces для bounded factual sync без direct DB access как primary production path;
- factual monitoring и manual review выходят отдельным workspace, а `/pools/runs` остаётся execution-centric surface;
- новый factual route входит в UI governance perimeter и проходит platform/lint/browser validation, если использует `MasterDetail` или иной catalog/detail shell.

При нарушении этих условий change должен считаться `Not ready` до обновления OpenSpec или отдельного архитектурного решения.

## Impact
- Affected specs:
  - `pool-distribution-runs` (modified)
  - `pool-batch-intake` (new)
  - `pool-factual-balance-monitoring` (new)
- Affected code:
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/api_v2/**`
  - `go-services/worker/**`
  - `frontend/src/pages/Pools/**`
  - `contracts/**`
- Affected integrations:
  - 1C document/register polling
  - machine-readable traceability marker в комментарии документа с возможным расширением до отдельного регистра в follow-up
- Runtime / deployment:
  - используются существующие `orchestrator`, `worker`, `frontend`
  - `intake`, `factual read/projection`, `reconcile/review` остаются внутренними подсистемами этих runtime, а не новыми top-level сервисами
  - новый top-level service или отдельный frontend app не вводятся

## Non-Goals For This Change
- Автоматическая подача декларации из 1С.
- Автоматическое "лечение" ручных правок пользователя в 1С.
- Полная автоматическая атрибуция всех ручных реализаций без пользовательской разметки.
- Исторический backfill старых кварталов до запуска change.
- Выделение отдельного factual microservice, отдельного frontend приложения или нового primary runtime для factual monitoring.
