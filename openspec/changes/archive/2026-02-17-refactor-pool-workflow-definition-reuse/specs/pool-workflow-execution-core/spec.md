## MODIFIED Requirements
### Requirement: Import templates и execution plan MUST быть разделены терминологически и технически
Система ДОЛЖНА (SHALL) использовать разделённые сущности:
- `PoolImportSchemaTemplate` как execution-core термин для доменного шаблона импорта (`PoolSchemaTemplate` из foundation change);
- `PoolWorkflowDefinition` как переиспользуемый blueprint процесса;
- `PoolExecutionPlanSnapshot` как immutable runtime snapshot конкретного запуска.

Система ДОЛЖНА (SHALL) иметь детерминированный compiler, который разделяет:
- compile-time результат: `PoolImportSchemaTemplate + structural_context -> PoolWorkflowDefinition`;
- run-time результат: `PoolRun + request_context -> PoolExecutionPlanSnapshot`.

`definition_key` ДОЛЖЕН (SHALL) строиться только из структурных признаков (`pool_id`, `direction`, `mode`, template version/schema content, DAG structure, workflow binding hint) и НЕ ДОЛЖЕН (SHALL NOT) зависеть от `period_start`, `period_end`, `run_input`, idempotency key.

Система ДОЛЖНА (SHALL) трактовать foundation-поле `workflow_binding` на import template как optional compiler hint и НЕ ДОЛЖНА (SHALL NOT) трактовать его как отдельный runtime execution-template.

#### Scenario: Разные period/run_input переиспользуют один workflow definition
- **GIVEN** два запуска одного `pool_id` с одинаковыми `direction/mode` и одинаковой версией import template
- **AND** `period_*` и `run_input` различаются
- **WHEN** backend компилирует workflow для обоих запусков
- **THEN** `definition_key` и ссылка на workflow definition совпадают
- **AND** каждый запуск получает собственный `PoolExecutionPlanSnapshot` с его `period_*` и `run_input`

#### Scenario: Структурное изменение создаёт новый workflow definition
- **GIVEN** для того же `pool_id` изменилась версия schema template или compiled DAG structure
- **WHEN** backend компилирует workflow definition
- **THEN** вычисляется новый `definition_key`
- **AND** создаётся новая версия workflow definition

#### Scenario: Legacy template с workflow_binding остаётся совместимым
- **GIVEN** import template содержит `workflow_binding`
- **WHEN** запускается unified execution
- **THEN** template принимается без изменения публичного API
- **AND** `workflow_binding` используется только как compiler hint

## ADDED Requirements
### Requirement: Pool workflow runtime MUST переиспользовать definition и хранить immutable execution snapshot
Система ДОЛЖНА (SHALL) резолвить/создавать workflow template для pool run по `definition_key`, а не по run-specific fingerprint.

Система ДОЛЖНА (SHALL) сохранять для каждого workflow execution immutable snapshot, включающий:
- run-specific вход (`period_start`, `period_end`, `run_input`, `seed`);
- lineage metadata (`root_workflow_run_id`, `parent_workflow_run_id`, `attempt_number`, `attempt_kind`);
- provenance ссылки на definition (`workflow_template_id`, `workflow_template_version`, `definition_key`).

Retry path ДОЛЖЕН (SHALL) переиспользовать тот же definition (если структурный контекст не изменился) и создавать новый execution snapshot для новой попытки.

#### Scenario: Повторный run не создаёт новый template при неизменной структуре
- **GIVEN** существует workflow definition для (`pool_id`, `direction`, `mode`, template version, DAG structure)
- **WHEN** создаётся новый run с другим `period_*` или `run_input`
- **THEN** runtime переиспользует существующий workflow template
- **AND** создаёт новый workflow execution с новым snapshot

#### Scenario: Retry наследует definition и фиксирует новый lineage snapshot
- **GIVEN** run имеет root workflow execution и доступен для retry
- **WHEN** выполняется retry
- **THEN** retry execution ссылается на тот же `definition_key`
- **AND** snapshot содержит `attempt_kind=retry` и корректный `parent_workflow_run_id`

#### Scenario: Historical executions остаются читаемыми после split-модели
- **GIVEN** execution создан до введения definition reuse
- **WHEN** клиент читает details/provenance run
- **THEN** historical execution остаётся доступным
- **AND** отсутствие новых snapshot полей не приводит к ошибке десериализации
