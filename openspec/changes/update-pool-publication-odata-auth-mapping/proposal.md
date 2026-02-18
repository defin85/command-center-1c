# Change: Перевести auth для `pool.publication_odata` на RBAC infobase mapping

## Why
После Big-bang переноса `pool.publication_odata` на worker `odata-core` публикация всё ещё берёт OData credentials из `Database.username/password`, а не из существующего RBAC-механизма `InfobaseUserMapping`.

Это создаёт архитектурный разрыв:
- дублируются источники секретов для одного и того же OData access path;
- pool run path не учитывает actor/service стратегию, хотя механизм уже есть;
- при multi-operator эксплуатации поведение auth становится непрозрачным.

Code-first evidence:
- `orchestrator/apps/operations/event_subscriber/handlers_commands.py` формирует `username/password` из `Database` для `get-database-credentials`;
- `go-services/worker/internal/drivers/poolops/publication_transport.go` вызывает `credsClient.Fetch(ctx, databaseID)` без `WithRequestedBy/WithIbAuthStrategy`;
- `orchestrator/apps/intercompany_pools/workflow_runtime.py` не прокидывает publication auth context (`created_by/strategy`) в workflow input context;
- UI/CRUD для `InfobaseUserMapping` уже существует в `/rbac` (`frontend/src/pages/RBAC/tabs/InfobaseUsersTab.tsx`).

## What Changes
- Зафиксировать `InfobaseUserMapping` как source-of-truth для OData username/password в `pool.publication_odata`.
- Зафиксировать split конфигурации:
  - `odata_url` — на уровне `Database`;
  - OData username/password — через RBAC infobase mapping (`actor`/`service`).
- Добавить обязательный publication auth context в workflow runtime path:
  - `publication_auth.strategy` (`actor|service`);
  - `publication_auth.actor_username` (для actor flow);
  - provenance источника (кто инициировал publication attempt).
- Обязать worker `pool.publication_odata` запрашивать credentials только через context-aware lookup:
  - `WithRequestedBy(...)`;
  - `WithIbAuthStrategy(...)`.
- Зафиксировать contract-first подход для внутреннего credentials transport:
  - `created_by` и `ib_auth_strategy` должны быть частью формализованного internal contract;
  - некорректный/missing contract контекст обрабатывается fail-closed до OData side effects.
- Fail-closed политика:
  - отсутствие/неоднозначность mapping => deterministic credentials error;
  - fallback на `Database.username/password` для `pool.publication_odata` запрещён.
- Зафиксировать стабильные machine-readable коды ошибок для mapping проблем:
  - `ODATA_MAPPING_NOT_CONFIGURED`,
  - `ODATA_MAPPING_AMBIGUOUS`,
  - `ODATA_PUBLICATION_AUTH_CONTEXT_INVALID`.
- Уточнить операторский UX:
  - конфигурация OData auth выполняется через `/rbac` (Infobase Users);
  - `Database credentials` UI трактуется как legacy для publication use-case и не является source-of-truth для pool publication.
- Зафиксировать rollout gates:
  - preflight coverage report по mapping для target databases;
  - mandatory operator sign-off для staging и prod перед cutover.

## Impact
- Affected specs:
  - `pool-odata-publication`
  - `pool-workflow-execution-core`
  - `worker-odata-transport-core`
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/workflow_runtime.py`
  - `orchestrator/apps/intercompany_pools/safe_commands.py`
  - `orchestrator/apps/operations/event_subscriber/handlers_commands.py`
  - `go-services/worker/internal/workflow/handlers/*`
  - `go-services/worker/internal/drivers/poolops/publication_transport.go`
  - `go-services/shared/credentials/*`
  - `contracts/orchestrator-internal/openapi.yaml` (или эквивалентная internal schema фиксация stream-contract)
  - `frontend/src/pages/Databases/*` и `frontend/src/pages/RBAC/*` (UX alignment)
- Contracts:
  - без изменения публичного pools facade API;
  - внутренний runtime/context contract дополняется publication auth context;
  - internal credentials request contract фиксируется с machine-readable error taxonomy.

## Non-Goals
- Не менять контракт `PoolRunReport`/`publication_attempts` для клиентов.
- Не переносить generic `odataops` auth semantics в этот change (кроме требуемой согласованности через shared credentials API).
- Не вводить новый отдельный storage для OData credentials.

## Assumptions
- Базовая стратегия для пользовательских запусков/подтверждений: `publication_auth.strategy=actor`.
- `publication_auth.strategy=service` используется только для системных/операторских сценариев, где actor отсутствует или явно выбран service flow.
- Для `pool.publication_odata` после этого change `Database.username/password` больше не считаются валидным runtime fallback.
- Для production cutover требуется явный operator sign-off после staging rehearsal и preflight coverage.
