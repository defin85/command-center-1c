# Change: Metadata-driven builders для Document policy и Edge metadata в UI каталога пулов

## Why
Сейчас оператор редактирует `Document policy (JSON)` и `Edge metadata (JSON)` вручную. Для реальных 1С-баз это приводит к частым ошибкам в именах документов, реквизитов и табличных частей, а также к сложному onboarding для новых конфигураций.

Дополнительно отсутствует штатный способ интерактивно получить полный каталог доступных OData-метаданных по конкретной базе и использовать его как source-of-truth при сборке policy.

## What Changes
- Добавить backend read API для получения нормализованного каталога OData-метаданных выбранной ИБ:
  - документы;
  - реквизиты шапки;
  - табличные части и реквизиты строк.
- Добавить кэширование каталога метаданных с TTL и явным refresh-path, чтобы снизить нагрузку на OData endpoint.
- Добавить в `/pools/catalog` интерактивные builder-режимы:
  - `Document policy builder` (chain/documents/mappings/link rules);
  - `Edge metadata builder` (структурированное редактирование metadata с сохранением неизвестных ключей).
- Сохранить raw JSON режим как fallback/escape hatch с двусторонней синхронизацией между builder и raw.
- Добавить fail-closed валидацию на сохранении topology snapshot:
  - ссылки policy на недоступные документы/реквизиты/табличные части должны отклоняться с machine-readable ошибкой.

## Impact
- Affected specs:
  - `organization-pool-catalog`
- Affected code (expected):
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `orchestrator/apps/api_v2/serializers/intercompany_pools.py`
  - `orchestrator/apps/intercompany_pools/document_policy_contract.py`
  - `frontend/src/pages/Pools/PoolCatalogPage.tsx`
  - `frontend/src/pages/Pools/components/*` (новые builder-компоненты)
  - `contracts/orchestrator/openapi.yaml`

## Dependencies
- Требуется совместимость с контрактом `document_policy.v1`, введённым в change `add-02-pool-document-policy`.
- Для получения OData credentials используется существующий контур mapping-based auth (`InfobaseUserMapping`) без fallback на legacy `Database.username/password`.

## Non-Goals
- Не реализуется универсальный low-code редактор всех бизнес-объектов 1С вне `Document policy` и `Edge metadata`.
- Не добавляется автоматическая миграция всех исторических topology snapshot к новому builder формату.
- Не изменяется execution runtime семантика публикации документов в этом change.
