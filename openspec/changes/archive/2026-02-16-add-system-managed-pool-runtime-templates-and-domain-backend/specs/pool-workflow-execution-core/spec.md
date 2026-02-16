## ADDED Requirements
### Requirement: Pool workflow compiler MUST формировать pinned binding на system-managed runtime templates
Система ДОЛЖНА (SHALL) компилировать operation nodes pool workflow с `operation_ref(binding_mode="pinned_exposure")`, где указываются `template_exposure_id` и `template_exposure_revision` из system-managed pool runtime registry.

Pool workflow node НЕ ДОЛЖЕН (SHALL NOT) исполняться в режиме `alias_latest` в production path.

#### Scenario: Компиляция pool run фиксирует pinned exposure provenance
- **GIVEN** system-managed registry содержит активный alias `pool.prepare_input`
- **WHEN** компилятор строит workflow DAG для pool run
- **THEN** node `prepare_input` содержит `operation_ref.binding_mode="pinned_exposure"`
- **AND** в node заполнены `template_exposure_id` и `template_exposure_revision`

#### Scenario: Missing binding в registry блокирует создание run fail-closed
- **GIVEN** в system-managed registry отсутствует alias `pool.distribution_calculation.top_down`
- **WHEN** система пытается создать workflow execution plan для top_down run
- **THEN** создание run отклоняется fail-closed бизнес-ошибкой
- **AND** код ошибки равен `POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED`
- **AND** enqueue шагов не выполняется

### Requirement: Pool runtime steps MUST исполняться через PoolDomainBackend
Система ДОЛЖНА (SHALL) выполнять pool runtime operation nodes через выделенный `PoolDomainBackend`, а не через generic CLI backends (`ibcmd_cli`, `designer_cli`).

#### Scenario: distribution_calculation исполняется доменным backend без внешнего CLI executor
- **GIVEN** workflow run дошёл до шага `distribution_calculation`
- **WHEN** runtime выбирает backend для operation node
- **THEN** выбран `PoolDomainBackend`
- **AND** внешняя batch operation для CLI executor не создаётся

### Requirement: Runtime MUST fail-closed при pinned drift и неисполненном registry
Система ДОЛЖНА (SHALL) прекращать выполнение pool operation node при несоответствии pinned binding:
- exposure не найден;
- exposure неактивен/неопубликован;
- `template_exposure_revision` не совпал.

Система НЕ ДОЛЖНА (SHALL NOT) использовать fallback на `alias_latest` или legacy path.

#### Scenario: Drift revision останавливает node execution
- **GIVEN** node содержит `template_exposure_id=<id>` и `template_exposure_revision=12`
- **AND** текущий revision exposure равен `13`
- **WHEN** runtime исполняет node
- **THEN** execution завершается ошибкой drift
- **AND** код ошибки равен `TEMPLATE_DRIFT`
- **AND** side effects node не выполняются

### Requirement: Pool runtime MUST возвращать стабильные fail-closed коды ошибок
Система ДОЛЖНА (SHALL) возвращать machine-readable коды ошибок для несоответствий registry/binding в compile/runtime path.

Канонический набор кодов:
- `POOL_RUNTIME_TEMPLATE_NOT_CONFIGURED` — required alias не найден в registry.
- `POOL_RUNTIME_TEMPLATE_INACTIVE` — pinned exposure найден, но неактивен/непубликован.
- `TEMPLATE_DRIFT` — pinned revision не совпадает с текущей ревизией exposure.
- `POOL_RUNTIME_TEMPLATE_UNSUPPORTED_EXECUTOR` — executor pinned exposure не поддерживает `PoolDomainBackend`.

#### Scenario: Inactive exposure блокирует исполнение node fail-closed
- **GIVEN** node содержит pinned `template_exposure_id=<id>` и `template_exposure_revision=<r>`
- **AND** exposure `<id>` существует, но помечен inactive
- **WHEN** runtime пытается исполнить node
- **THEN** node завершается fail-closed без выполнения side effects
- **AND** код ошибки равен `POOL_RUNTIME_TEMPLATE_INACTIVE`
