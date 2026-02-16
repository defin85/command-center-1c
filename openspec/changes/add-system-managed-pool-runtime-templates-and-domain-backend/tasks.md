## 1. Spec & Contracts
- [ ] 1.1 Добавить spec deltas в `pool-workflow-execution-core` и `operation-templates`.
- [ ] 1.2 Зафиксировать список системных pool runtime aliases и их contract version.
- [ ] 1.3 Описать/задокументировать fail-closed коды ошибок (`POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED`, `TEMPLATE_DRIFT`, и т.п.).

## 2. Backend: System-managed runtime templates
- [ ] 2.1 Добавить признак system-managed для runtime template exposures (например `system_managed`, `domain=pool_runtime`).
- [ ] 2.2 Реализовать bootstrap/sync механизм системного реестра pool aliases -> OperationExposure/OperationDefinition.
- [ ] 2.3 Запретить mutating write-path для системных pool runtime templates через публичный templates API.
- [ ] 2.4 Реализовать read-only introspection состояния системного pool template registry.

## 3. Backend: PoolDomainBackend + pinned binding
- [ ] 3.1 Реализовать `PoolDomainBackend` и зарегистрировать его в routing operation handler.
- [ ] 3.2 Перенести execution логику pool шагов в `PoolDomainBackend` как domain services.
- [ ] 3.3 Обновить `PoolWorkflowCompiler`: сохранять `operation_ref(binding_mode=\"pinned_exposure\", template_exposure_id, template_exposure_revision)`.
- [ ] 3.4 Обновить runtime execution path: validate pinned revision и fail-closed при drift/missing/inactive.
- [ ] 3.5 Сохранить binding snapshot в execution plan/audit для трассируемости.

## 4. UI/API Surface
- [ ] 4.1 Убедиться, что `/templates` не позволяет редактировать system-managed pool runtime templates.
- [ ] 4.2 При наличии introspection endpoint: добавить staff-only UI/diagnostics блок состояния registry.

## 5. Tests & Validation
- [ ] 5.1 Backend unit/integration тесты на bootstrap/sync системного pool registry.
- [ ] 5.2 Backend тесты на pinned binding (успех, missing alias, revision drift, inactive exposure).
- [ ] 5.3 Backend тесты routing на `PoolDomainBackend` и отсутствие fallback в внешние executor.
- [ ] 5.4 Backend/API тесты на блокировку mutating системных pool templates.
- [ ] 5.5 Прогнать `openspec validate add-system-managed-pool-runtime-templates-and-domain-backend --strict --no-interactive`.
