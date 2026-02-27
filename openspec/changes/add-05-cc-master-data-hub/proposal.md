# Change: CC как единый source-of-truth для master-data в pool publication

## Why
Сейчас pool publication опирается на payload run-а и состояние справочников в каждой целевой ИБ. Это создаёт drift между ИБ, дублирование операторской настройки и неустойчивость при повторных запусках/retry.

Для БП 3.0 это особенно критично, потому что связанные данные распределены по отдельным справочникам (`Catalog_Организации`, `Catalog_Контрагенты`, `Catalog_Номенклатура`, `Catalog_ДоговорыКонтрагентов`), и одинаковые бизнес-сущности приходится поддерживать в нескольких местах.

## What Changes
- Ввести capability `pool-master-data-hub`: канонический master-data слой в CC для публикационных run-ов.
- Зафиксировать минимальный доменный набор MVP: `Party` (role-based), `Item`, `Contract`, `TaxProfile`.
- Добавить per-infobase binding модель (`canonical_id -> ib_ref`) и идемпотентный sync/resolve контракт.
- Добавить pre-publication gate в runtime: перед `pool.publication_odata` выполняется resolve/sync master-data для всех target ИБ.
- Зафиксировать immutable `master_data_snapshot_ref` в контексте run-а и обязательное переиспользование этого snapshot в retry.
- Зафиксировать fail-closed поведение для конфликтов/неоднозначных соответствий до OData side effects.

## Impact
- Affected specs:
  - `pool-master-data-hub` (new)
  - `pool-workflow-execution-core`
  - `pool-odata-publication`
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/models.py`
  - `orchestrator/apps/intercompany_pools/workflow_runtime.py`
  - `orchestrator/apps/intercompany_pools/pool_domain_steps.py`
  - `orchestrator/apps/intercompany_pools/document_plan_artifact_contract.py`
  - `go-services/worker/internal/drivers/poolops/publication_transport.go`
  - `contracts/orchestrator/**` (если появятся новые API контракты)

## Non-Goals
- Не выполняется полная миграция всех исторических справочников БП в одном change.
- Не вводится двусторонний merge-конфликт резолвер между CC и ИБ.
- Не меняется бизнес-логика распределения сумм (top-down/bottom-up); change ограничен master-data и публикацией.

## Dependencies
- `pool-document-policy` и `pool-workflow-execution-core` остаются источником требований по compile/publication pipeline.
- `pool-odata-publication` остаётся владельцем контракта OData side effects.
