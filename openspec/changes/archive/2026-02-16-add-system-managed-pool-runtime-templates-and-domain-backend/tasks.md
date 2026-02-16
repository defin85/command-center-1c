## 1. Spec & Contracts
- [x] 1.1 Добавить spec deltas в `pool-workflow-execution-core` и `operation-templates`.
- [x] 1.2 Зафиксировать список системных pool runtime aliases и их contract version.
- [x] 1.3 Описать/задокументировать fail-closed коды ошибок (`POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED`, `TEMPLATE_DRIFT`, и т.п.).

## 2. Backend: System-managed runtime templates
- [x] 2.1 Добавить признак system-managed для runtime template exposures (например `system_managed`, `domain=pool_runtime`).
- [x] 2.2 Реализовать bootstrap/sync механизм системного реестра pool aliases -> OperationExposure/OperationDefinition.
- [x] 2.3 Запретить mutating write-path для системных pool runtime templates через публичный templates API.
- [x] 2.4 Реализовать read-only introspection состояния системного pool template registry.

## 3. Backend: PoolDomainBackend + pinned binding
- [x] 3.1 Реализовать `PoolDomainBackend` и зарегистрировать его в routing operation handler.
- [x] 3.2 Перенести execution логику pool шагов в `PoolDomainBackend` как domain services.
- [x] 3.3 Обновить `PoolWorkflowCompiler`: сохранять `operation_ref(binding_mode=\"pinned_exposure\", template_exposure_id, template_exposure_revision)`.
- [x] 3.4 Обновить runtime execution path: validate pinned revision и fail-closed при drift/missing/inactive.
- [x] 3.5 Сохранить binding snapshot в execution plan/audit для трассируемости.

## 4. UI/API Surface
- [x] 4.1 Убедиться, что `/templates` не позволяет редактировать system-managed pool runtime templates.
- [x] 4.2 При наличии introspection endpoint: добавить staff-only UI/diagnostics блок состояния registry.

## 5. Tests & Validation
- [x] 5.1 Backend unit/integration тесты на bootstrap/sync системного pool registry.
- [x] 5.2 Backend тесты на pinned binding (успех, missing alias, revision drift, inactive exposure).
- [x] 5.3 Backend тесты routing на `PoolDomainBackend` и отсутствие fallback в внешние executor.
- [x] 5.4 Backend/API тесты на блокировку mutating системных pool templates.
- [x] 5.5 Прогнать `openspec validate add-system-managed-pool-runtime-templates-and-domain-backend --strict --no-interactive`.
