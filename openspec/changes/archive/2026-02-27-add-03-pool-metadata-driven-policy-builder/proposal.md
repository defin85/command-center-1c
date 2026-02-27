# Change: Metadata-driven builders для Document policy и Edge metadata в UI каталога пулов

## Why
Сейчас оператор редактирует `Document policy (JSON)` и `Edge metadata (JSON)` вручную. Для реальных 1С-баз это приводит к частым ошибкам в именах документов, реквизитов и табличных частей, а также к сложному onboarding для новых конфигураций.

Дополнительно отсутствует штатный способ интерактивно получить полный каталог доступных OData-метаданных по конкретной базе и использовать его как source-of-truth при сборке policy.

## What Changes
- Добавить backend read API для получения нормализованного каталога OData-метаданных выбранной ИБ:
  - документы;
  - реквизиты шапки;
  - табличные части и реквизиты строк.
- Добавить persisted snapshot storage каталога метаданных в БД как source-of-truth:
  - version markers: `config_name`, `config_version`, `metadata_hash`;
  - payload и служебные поля (`fetched_at`, `source`, `status/current`).
- Использовать Redis только как read-through cache accelerator:
  - отдача из Redis при hit;
  - fallback к актуальному snapshot в БД при miss/ошибке Redis;
  - явный refresh-path, который обновляет snapshot в БД и прогревает Redis.
- Добавить в `/pools/catalog` интерактивные builder-режимы:
  - `Document policy builder` (chain/documents/mappings/link rules);
  - `Edge metadata builder` (структурированное редактирование metadata с сохранением неизвестных ключей).
- Сохранить raw JSON режим как fallback/escape hatch с двусторонней синхронизацией между builder и raw.
- Добавить fail-closed валидацию на сохранении topology snapshot:
  - ссылки policy на недоступные документы/реквизиты/табличные части должны отклоняться с machine-readable ошибкой.

## Mandatory clarifications before implementation
- Строгий snapshot lifecycle:
  - в рамках `(tenant_id, database_id, config_name, config_version, extensions_fingerprint)` ДОЛЖЕН существовать ровно один current snapshot;
  - переключение `is_current` ДОЛЖНО выполняться атомарно в одной транзакции;
  - конкурентный refresh ДОЛЖЕН сериализоваться через lock (single-writer per scope) с детерминированной ошибкой при занятости lock.
- Единый формат referential validation ошибки:
  - для ошибок ссылок policy на metadata используется единый machine-readable code и обязательные поля `code`, `path`, `detail`;
  - для отсутствия current snapshot используется отдельный fail-closed code, но тот же формат `code`, `path`, `detail`.
- Mapping-only credentials для metadata path:
  - metadata read/refresh использует только `InfobaseUserMapping`;
  - fallback на `Database.username/password` запрещён.
- UI dual-mode:
  - builder формирует канонический JSON (`document_policy.v1`) в детерминированном формате;
  - raw-режим сохраняет неизвестные/пользовательские ключи metadata без потерь;
  - переключение между режимами не должно разрушать валидный JSON.

## Impact
- Affected specs:
  - `organization-pool-catalog`
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/models.py` (новая snapshot-модель)
  - `orchestrator/apps/intercompany_pools/migrations/*` (схема snapshot storage)
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `orchestrator/apps/api_v2/serializers/intercompany_pools.py`
  - `orchestrator/apps/intercompany_pools/document_policy_contract.py`
  - `frontend/src/pages/Pools/PoolCatalogPage.tsx`
  - `frontend/src/pages/Pools/components/*` (новые builder-компоненты)
  - `contracts/orchestrator/openapi.yaml`

## Dependencies
- Требуется совместимость с контрактом `document_policy.v1`, введённым в change `add-02-pool-document-policy`.
- Для получения OData credentials используется существующий контур mapping-based auth (`InfobaseUserMapping`) без fallback на legacy `Database.username/password`.
- Требуется рабочий Redis для ускорения чтения, но корректность системы не должна зависеть от его доступности (fallback в БД snapshot).

## Non-Goals
- Не реализуется универсальный low-code редактор всех бизнес-объектов 1С вне `Document policy` и `Edge metadata`.
- Не добавляется автоматическая миграция всех исторических topology snapshot к новому builder формату.
- Не изменяется execution runtime семантика публикации документов в этом change.
