# Review Report: update-pool-publication-odata-auth-mapping

Дата: 2026-02-19
Формат проверки: code-first (исходники + тесты + contracts + OpenSpec), без запуска тестов.

## Итог

Статус изменения: **частично реализовано**.

Ключевые незакрытые зоны:
1. Внутренний publication/credentials contract реализован в коде, но не формализован явно в `contracts/**`.
2. Rollout/release-gates для staging/prod (mandatory operator sign-off) остаются в состоянии `PENDING`.

## По задачам (`tasks.md`)

| Задача | Статус | Evidence | Gap |
|---|---|---|---|
| 1.1 canonical `publication_auth` contract | Реализовано | `orchestrator/apps/intercompany_pools/workflow_runtime.py:415`, `go-services/worker/internal/workflow/handlers/handler.go:35` | - |
| 1.2 internal credentials contract + error codes | Частично | `go-services/shared/credentials/streams_client.go:214`, `go-services/shared/credentials/streams_client.go:217`, `go-services/worker/internal/drivers/poolops/publication_transport.go:35` | В `contracts/**` нет явной схемы этих полей/кодов (`contracts/orchestrator-internal/openapi.yaml:1260`, `contracts/orchestrator-internal/openapi.yaml:1345`) |
| 1.3 OpenSpec deltas | Реализовано | `openspec/changes/update-pool-publication-odata-auth-mapping/specs/pool-odata-publication/spec.md:1`, `openspec/changes/update-pool-publication-odata-auth-mapping/specs/pool-workflow-execution-core/spec.md:1`, `openspec/changes/update-pool-publication-odata-auth-mapping/specs/worker-odata-transport-core/spec.md:1` | - |
| 2.1 publication_auth в workflow input context | Реализовано | `orchestrator/apps/intercompany_pools/workflow_runtime.py:392`, `orchestrator/apps/intercompany_pools/workflow_runtime.py:447` | - |
| 2.2 actor provenance для safe confirm/retry | Реализовано | `orchestrator/apps/intercompany_pools/safe_commands.py:333`, `orchestrator/apps/intercompany_pools/safe_commands.py:497`, `orchestrator/apps/intercompany_pools/tests/test_safe_commands.py:128`, `orchestrator/apps/intercompany_pools/tests/test_workflow_runtime.py:449` | - |
| 2.3 serialization/bridge path propagation | Реализовано | `orchestrator/apps/intercompany_pools/workflow_runtime.py:603`, `go-services/worker/internal/workflow/handlers/operation.go:173` | - |
| 3.1 propagation `publication_auth` -> `OperationRequest` | Реализовано | `go-services/worker/internal/workflow/handlers/operation.go:173`, `go-services/worker/internal/workflow/handlers/handlers_test.go:241` | - |
| 3.2 context-aware credentials fetch | Реализовано | `go-services/worker/internal/drivers/poolops/publication_transport.go:588`, `go-services/worker/internal/drivers/poolops/publication_transport.go:590`, `go-services/worker/internal/drivers/poolops/publication_transport_test.go:212` | - |
| 3.3 fail-closed validation до side effects | Реализовано | `go-services/worker/internal/drivers/poolops/publication_transport.go:186`, `go-services/worker/internal/drivers/poolops/publication_transport.go:544`, `go-services/worker/internal/drivers/poolops/publication_transport_test.go:238` | Неполное тест-покрытие invalid вариантов (`source` missing / unknown strategy) |
| 4.1 mapping-only resolution в `get-database-credentials` | Реализовано | `orchestrator/apps/operations/event_subscriber/handlers_commands.py:155`, `orchestrator/apps/operations/event_subscriber/handlers_commands.py:195`, `orchestrator/apps/operations/event_subscriber/handlers_commands.py:224` | - |
| 4.2 deterministic lookup + conflict errors | Частично | `orchestrator/apps/operations/event_subscriber/handlers_commands.py:391`, `orchestrator/apps/operations/event_subscriber/handlers_commands.py:419`, `orchestrator/apps/operations/event_subscriber/handlers_commands.py:430` | DB-level constraints для `InfobaseUserMapping` не добавлены (`orchestrator/apps/databases/models_user_mappings.py:52`) |
| 4.3 migration/backfill checks + preflight | Частично | `orchestrator/apps/intercompany_pools/management/commands/preflight_pool_publication_auth_mapping.py:72`, `orchestrator/apps/intercompany_pools/management/commands/preflight_pool_publication_auth_mapping.py:93`, `orchestrator/apps/intercompany_pools/tests/test_publication_auth_preflight_command.py:56` | Найдены preflight/checks, но не найдена явная migration/backfill миграция |
| 5.1 UX: `/rbac` как source для publication creds | Реализовано | `frontend/src/pages/Databases/components/DatabaseCredentialsModal.tsx:53`, `frontend/src/pages/Pools/PoolRunsPage.tsx:944` | - |
| 5.2 ранняя валидация + remediation hints | Реализовано | `orchestrator/apps/intercompany_pools/workflow_runtime.py:479`, `orchestrator/apps/api_v2/views/intercompany_pools.py:1801`, `frontend/src/pages/Pools/PoolRunsPage.tsx:867`, `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py:880` | - |
| 6.1 telemetry labels | Реализовано | `go-services/worker/internal/drivers/poolops/publication_transport.go:44`, `go-services/worker/internal/drivers/poolops/publication_transport.go:612` | - |
| 6.2 rollout checklist + rollback drill + sign-off | Частично | `openspec/changes/update-pool-publication-odata-auth-mapping/artifacts/2026-02-18-rollout-checklist-and-rollback-drill.md:1` | Checklist/sign-off не завершены (`...rollback-drill.md:37`, `...rollback-drill.md:48`) |
| 7.1 backend tests | Частично | `orchestrator/apps/intercompany_pools/tests/test_workflow_runtime.py:145`, `orchestrator/apps/intercompany_pools/tests/test_workflow_runtime.py:229`, `orchestrator/apps/operations/tests/test_event_subscriber_commands.py:196`, `go-services/worker/internal/drivers/poolops/publication_transport_test.go:238` | Нет полного набора invalid `publication_auth` test-cases |
| 7.2 worker tests propagation/fallback | Частично | `go-services/worker/internal/workflow/handlers/handlers_test.go:230`, `go-services/worker/internal/drivers/poolops/publication_transport_test.go:212`, `go-services/worker/internal/drivers/poolops/adapter_test.go:215` | Нет явного теста service-пути на transport payload (`created_by` absent + `ib_auth_strategy=service`) |
| 7.3 integration e2e | Частично | `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py:853`, `orchestrator/apps/intercompany_pools/tests/test_workflow_runtime.py:234` | Не видно полного e2e actor+service+missing+ambiguous через реальный worker path |
| 7.4 contract checks + drift checks | Частично | `openspec/changes/update-pool-publication-odata-auth-mapping/artifacts/2026-02-18-release-evidence.md:6` | Drift не закрыт полностью из-за отсутствия явной contract-формализации (`contracts/orchestrator-internal/openapi.yaml:1260`, `contracts/orchestrator-internal/openapi.yaml:1345`) |
| 7.5 staging rehearsal + prod go/no-go sign-off | Не реализовано | `openspec/changes/update-pool-publication-odata-auth-mapping/artifacts/2026-02-18-release-evidence.md:29`, `openspec/changes/update-pool-publication-odata-auth-mapping/artifacts/2026-02-18-release-evidence.md:30` | Staging/production sign-off pending |

## По требованиям (`spec.md`)

### `specs/pool-odata-publication/spec.md`

1. RBAC infobase mapping как source-of-truth и без legacy fallback: **реализовано**.  
Evidence: `orchestrator/apps/operations/event_subscriber/handlers_commands.py:195`, `go-services/worker/internal/drivers/poolops/publication_transport.go:355`, `go-services/worker/internal/drivers/poolops/adapter.go:133`.

2. Прозрачность operator surfaces (`Databases` + `/rbac`): **реализовано**.  
Evidence: `frontend/src/pages/Databases/components/DatabaseCredentialsModal.tsx:53`, `frontend/src/pages/Pools/PoolRunsPage.tsx:944`.

3. Machine-readable publication auth errors + remediation hint: **реализовано**.  
Evidence: `go-services/worker/internal/drivers/poolops/publication_transport.go:35`, `orchestrator/apps/intercompany_pools/publication_auth_mapping.py:177`, `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py:877`.

4. Operator-gated cutover (preflight + sign-off): **частично реализовано**.  
Evidence: `orchestrator/apps/intercompany_pools/management/commands/preflight_pool_publication_auth_mapping.py:93`; sign-off pending в `openspec/changes/update-pool-publication-odata-auth-mapping/artifacts/2026-02-18-release-evidence.md:29`.

### `specs/pool-workflow-execution-core/spec.md`

1. `publication_auth` в workflow execution context и без потери до worker: **реализовано**.  
Evidence: `orchestrator/apps/intercompany_pools/workflow_runtime.py:415`, `go-services/worker/internal/workflow/handlers/operation.go:173`.

2. Fail-closed валидация `publication_auth` до OData side effects: **реализовано (с частичным test gap)**.  
Evidence: `go-services/worker/internal/drivers/poolops/publication_transport.go:186`, `go-services/worker/internal/drivers/poolops/publication_transport.go:544`, `go-services/worker/internal/drivers/poolops/publication_transport_test.go:238`.

3. Provenance отражает фактического инициатора confirm/retry: **реализовано**.  
Evidence: `orchestrator/apps/intercompany_pools/safe_commands.py:333`, `orchestrator/apps/intercompany_pools/tests/test_workflow_runtime.py:449`.

### `specs/worker-odata-transport-core/spec.md`

1. Context-aware lookup + contract fields (`created_by`, `ib_auth_strategy`): **реализовано**.  
Evidence: `go-services/worker/internal/drivers/poolops/publication_transport.go:588`, `go-services/shared/credentials/streams_client.go:214`, `orchestrator/apps/operations/tests/test_event_subscriber_commands.py:156`.

2. No legacy fallback при missing mapping: **реализовано**.  
Evidence: `go-services/worker/internal/drivers/poolops/publication_transport.go:373`, `go-services/worker/internal/drivers/poolops/adapter_test.go:215`, `orchestrator/apps/api_internal/tests/test_views_workflows.py:1138`.

3. Детерминированные коды + non-retryable классификация: **частично реализовано**.  
Evidence: `go-services/worker/internal/odata/error_normalization.go:152`, `go-services/worker/internal/odata/error_normalization_test.go:72`.  
Gap: формальная фиксация в `contracts/**` не обнаружена.

## Риски/крайние случаи

1. **P1**: Контрактный drift между orchestrator/worker для publication auth path из-за отсутствия явной схемы в `contracts/**` (`contracts/orchestrator-internal/openapi.yaml:1260`, `contracts/orchestrator-internal/openapi.yaml:1345`).
2. **P1**: Release-governance не закрыт: staging/prod sign-off всё ещё pending (`openspec/changes/update-pool-publication-odata-auth-mapping/artifacts/2026-02-18-release-evidence.md:29`).
3. **P2**: `InfobaseUserMapping` не имеет DB constraints на уникальность actor/service mapping; неоднозначности ловятся только fail-closed во время выполнения (`orchestrator/apps/databases/models_user_mappings.py:52`).
4. **P2**: Недостаточное покрытие invalid `publication_auth` сценариев (missing `source`, unknown strategy, actor без username) повышает риск регрессий валидации.
5. **P3**: Frontend regression-покрытие для новых remediation/hint сообщений ограничено; в `frontend/src/pages/Pools/__tests__/PoolRunsPage.test.tsx` нет явных проверок новых mapping error messages.

## Дополнительно найдено субагентами

В параллельном ревью (4 explorer-субагента) подтверждены основные выводы отчёта выше и дополнительно зафиксированы следующие новые наблюдения:

1. Отсутствуют API-level тесты, которые прямо проверяют, что вызовы `/confirm-publication` и `/retry` обновляют `publication_auth` (`source` и `actor_username`) внутри `workflow_execution.input_context`; текущие API-тесты сфокусированы в основном на статусах/idempotency (`orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py:1780`, `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py:2260`).
2. Contract drift дополнительно подтверждён на уровне схемы `PoolRuntimeStepExecutionRequest`: поле `payload` остаётся без формализованных publication-specific полей (включая `publication_auth`) (`contracts/orchestrator-internal/openapi.yaml:1345`), при том что worker уже требует структуру `PublicationAuth` (`go-services/worker/internal/workflow/handlers/handler.go:34`).
3. Для фронтенда подтверждён отдельный test gap: в `PoolRunsPage` тестах нет явных проверок рендеринга новых `ODATA_MAPPING_*`/`ODATA_PUBLICATION_AUTH_CONTEXT_INVALID` сообщений и `/rbac` remediation текста (`frontend/src/pages/Pools/__tests__/PoolRunsPage.test.tsx:194`).

## Вопросы (если нужны)

1. Нужно ли считать обязательным добавление явного contract-описания publication auth / credentials transport в `contracts/**` в рамках этого change?
2. Должны ли DB-level constraints для `InfobaseUserMapping` (deterministic actor/service resolution) быть частью текущего scope, или текущий runtime fail-closed режим принимается как достаточный?
