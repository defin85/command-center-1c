# Change: Вынести общий OData transport core для `odataops` и `poolops`

## Why
Сейчас OData-взаимодействие в worker реализовано фрагментарно: generic `odataops` использует один путь, а `poolops/publication_odata` формируется отдельным execution-path.

Это повышает риск drift по retry/error mapping/auth/session semantics, усложняет поддержку и увеличивает стоимость регрессий при изменениях OData-клиента.

Нужен единый transport core, который переиспользуется обоими драйверами, при сохранении раздельной доменной логики.

## What Changes
- Ввести в worker выделенный shared слой `odata-core` для transport concerns:
  - auth/session management;
  - retry/backoff policy;
  - HTTP/domain error mapping;
  - batch/upsert/posting helpers.
- Перевести `poolops(publication_odata)` на `odata-core` без изменения доменной state-machine семантики `pool-workflow-execution-core`.
- Перевести `odataops` (`create|update|delete|query`) на тот же `odata-core` с сохранением текущего API/контракта operation result.
- Зафиксировать обязательную telemetry-модель (маршрутизация, retries, resend_count, latency/error labels).
- Удалить дублирующиеся transport-компоненты после полного переключения обоих драйверов.

## Impact
- Affected specs:
  - `worker-odata-transport-core` (new capability)
  - `pool-workflow-execution-core`
- Affected code (expected):
  - `go-services/worker/internal/odata/*`
  - `go-services/worker/internal/drivers/odataops/*`
  - `go-services/worker/internal/drivers/poolops/*`
  - `go-services/worker/internal/workflow/handlers/*` (только wiring/интерфейсы)
- Validation:
  - parity tests для `odataops` и `poolops` на общих retry/error semantics;
  - интеграционный сценарий pool run `500` на 3 организации с созданием документов;
  - регрессии generic CRUD (create/update/delete/query).

## Dependencies
- Рекомендуемая последовательность: после стабилизации change `add-poolops-driver-workflow-runtime-fail-closed` (минимум этапа с fail-closed и рабочим `publication_odata`).

## Non-Goals
- Не меняем stream topology (`operations`/`workflows`) и queue routing.
- Не меняем публичный API pools facade.
- Не переносим доменную pool state-machine логику в generic OData слой.
