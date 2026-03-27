# Change: Добавить factual balance monitoring и batch intake для pool-run процесса

## Why
Текущий pool runtime уже умеет рассчитывать и публиковать run, но операторский контур ограничен run-local отчётом по расчёту и публикации. Целевой бизнес-процесс требует другого уровня автоматизации: принимать внешние реестры поступлений и реализаций в произвольном формате, запускать распределение от выбранной бухгалтером стартовой организации и затем показывать бухгалтерам near-real-time фактический баланс по пулу на основе реальных данных ИБ.

Без отдельного batch intake и централизованной factual balance projection пользователи не смогут быстро увидеть, где сумма дошла до leaf-узлов, где она зависла, какие суммы уже закрыты реализациями и что переносится в следующий квартал.

## What Changes
- Добавить pool-scoped batch intake для внешних реестров поступлений и реализаций с произвольным форматом через `Pool Schema Templates` и будущие integration adapters.
- Расширить top-down run contract: запуск от явной стартовой организации, `one batch = one pool_run`, batch/run provenance и отделение batch settlement status от существующего `PoolRun.status`.
- Добавить централизованную factual balance projection по `pool + organization + edge + quarter + batch` на основе фактических документов и регистров ИБ.
- Зафиксировать целевой архитектурный вариант `B`: расширение текущих `orchestrator + worker` границ без отдельного factual microservice или нового primary runtime; `orchestrator` владеет batch/projection/review contracts, а `worker` получает отдельный factual read/reconcile lane внутри текущего runtime family.
- Добавить operator-facing summary/drill-down в отдельном factual workspace внутри существующего frontend приложения, который показывает `вошло`, `вышло`, `остаток`, разбивку `с НДС / без НДС / НДС`, а также где сумма застряла.
- Добавить quarter carry-forward для незакрытого остатка на том же узле и explicit review queue для документов без traceability, которые нельзя автоматически привязать к конкретному pool/batch.
- Уточнить, что существующий run report остаётся runtime/local отчётом по расчёту и публикации и не подменяет factual balance dashboard.

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
  - новый top-level service или отдельный frontend app не вводятся

## Non-Goals For This Change
- Автоматическая подача декларации из 1С.
- Автоматическое "лечение" ручных правок пользователя в 1С.
- Полная автоматическая атрибуция всех ручных реализаций без пользовательской разметки.
- Исторический backfill старых кварталов до запуска change.
- Выделение отдельного factual microservice, отдельного frontend приложения или нового primary runtime для factual monitoring.
