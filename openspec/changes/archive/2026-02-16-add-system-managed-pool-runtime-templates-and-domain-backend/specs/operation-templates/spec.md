## ADDED Requirements
### Requirement: Pool runtime templates MUST быть system-managed и недоступны для пользовательского write-path
Система ДОЛЖНА (SHALL) помечать runtime templates с alias `pool.*` как system-managed в domain `pool_runtime`.

Система НЕ ДОЛЖНА (SHALL NOT) позволять create/update/delete этих templates через публичный templates management API.

#### Scenario: Попытка изменить system-managed pool template через `/templates` отклоняется
- **GIVEN** существует system-managed template alias `pool.prepare_input`
- **WHEN** пользователь отправляет update/delete через templates write endpoint
- **THEN** система возвращает отказ доступа или business conflict
- **AND** definition/exposure не изменяются

### Requirement: System-managed pool runtime registry MUST поддерживать bootstrap и introspection
Система ДОЛЖНА (SHALL) поддерживать bootstrap/sync процесс, который поддерживает полный набор required pool runtime aliases в согласованном состоянии.

Система ДОЛЖНА (SHALL) предоставлять read-only introspection registry статуса (configured/missing/drift) для диагностики.

Канонический список required aliases в `contract_version="pool_runtime.v1"`:
- `pool.prepare_input`
- `pool.distribution_calculation.top_down`
- `pool.distribution_calculation.bottom_up`
- `pool.reconciliation_report`
- `pool.approval_gate`
- `pool.publication_odata`

#### Scenario: Bootstrap восстанавливает отсутствующий системный alias
- **GIVEN** один из required alias `pool.publication_odata` отсутствует в registry
- **WHEN** выполняется bootstrap/sync системных pool runtime templates
- **THEN** alias создаётся или восстанавливается в активном состоянии
- **AND** introspection показывает статус `configured`

#### Scenario: Introspection возвращает contract version и полный набор required aliases
- **GIVEN** системный pool runtime registry синхронизирован
- **WHEN** staff/system клиент читает introspection состояние registry
- **THEN** ответ содержит `contract_version="pool_runtime.v1"`
- **AND** ответ содержит все required aliases из контракта

### Requirement: Pool runtime templates MUST использовать выделенный executor kind для доменного backend
Система ДОЛЖНА (SHALL) сохранять системные pool runtime templates с executor kind, маршрутизируемым в `PoolDomainBackend`.

#### Scenario: Runtime resolve system-managed pool template выбирает PoolDomainBackend
- **GIVEN** operation node резолвится в system-managed pool runtime template
- **WHEN** handler выбирает backend по executor kind template
- **THEN** routing указывает на `PoolDomainBackend`
- **AND** generic CLI backend не используется
