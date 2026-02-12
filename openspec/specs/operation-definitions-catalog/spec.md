# operation-definitions-catalog Specification

## Purpose
TBD - created by archiving change add-unified-templates-action-catalog-contract. Update Purpose after archive.
## Requirements
### Requirement: Unified persistent contract MUST разделять definition и exposure
Система ДОЛЖНА (SHALL) хранить исполняемые конфигурации templates в двух связанных слоях:
- `operation_definition` — canonical execution payload,
- `operation_exposure(surface="template")` — публикация шаблона и идентичность `template_id` через `alias`.

После Big-bang cutover legacy projection `OperationTemplate`/`operation_templates` НЕ ДОЛЖЕН (SHALL NOT) использоваться как read/write источник в runtime или management/API контуре.

#### Scenario: Runtime резолвит template без legacy projection
- **GIVEN** релиз cutover завершён и legacy projection удалён
- **WHEN** workflow/internal runtime запрашивает шаблон по `template_id`
- **THEN** система резолвит шаблон через `operation_exposure(surface="template", alias=<template_id>)` и связанный `operation_definition`
- **AND** fallback к `OperationTemplate` не выполняется

### Requirement: Migration MUST быть обратимо-наблюдаемой и fail-closed
Система ДОЛЖНА (SHALL) выполнять Big-bang migration в одном релизе через этапы preflight → backfill → switch → contract с явными `go/no-go` критериями.

Система ДОЛЖНА (SHALL) прерывать cutover до switch/contract фазы при preflight или parity ошибках и оставлять сервис в согласованном pre-cutover состоянии.

Preflight ДОЛЖЕН (SHALL) включать минимум:
- alias uniqueness check для `operation_exposure(surface="template")`,
- referential check для legacy template permissions и operation references,
- parity checks для direct/group template permissions,
- runtime path gate (отсутствие критичных runtime/internal/rbac обращений к `OperationTemplate`).

Для критичных preflight/parity проверок порог допуска ДОЛЖЕН (SHALL) быть `0` mismatches.

#### Scenario: Preflight ошибка блокирует switch и удаление legacy
- **GIVEN** preflight обнаружил alias collision или RBAC parity mismatch
- **WHEN** запускается cutover release
- **THEN** switch/contract фазы не выполняются
- **AND** удаление legacy projection не происходит
- **AND** проблема фиксируется в migration diagnostics/runbook отчёте

#### Scenario: Preflight блокирует cutover при runtime path violations
- **GIVEN** runtime/internal/rbac gate обнаружил обращение к `OperationTemplate` в целевых switch-путях
- **WHEN** запускается cutover release
- **THEN** switch/contract фазы не выполняются
- **AND** релиз помечается как `No-Go`

#### Scenario: Rollback выполняется как полный откат релиза
- **GIVEN** после switch выявлена критическая регрессия
- **WHEN** команда выполняет rollback
- **THEN** откат выполняется через restore pre-cutover backup и возврат предыдущего deploy
- **AND** частичный rollback только схемы или только кода не используется

### Requirement: Unified contract MUST иметь явный API для definitions/exposures
Система ДОЛЖНА (SHALL) использовать `operation-catalog` API как management-контур templates и сохранять backward-compatible внешнюю идентичность template через `template_id` (значение alias exposure).

#### Scenario: Внешний template_id стабилен после cutover
- **WHEN** клиент читает template exposure или execution metadata
- **THEN** `template_id` совпадает с `operation_exposure.alias`
- **AND** клиентский контракт не требует знания внутреннего `OperationExposure.id`

### Requirement: Unified contract MUST canonicalize mapping между `executor_kind` и runtime driver
Система ДОЛЖНА (SHALL) использовать canonical mapping между `operation_definition.executor_kind` и runtime driver для canonical executors:
- `ibcmd_cli -> ibcmd`
- `designer_cli -> cli`
- `workflow -> driver не применяется`

`driver` НЕ ДОЛЖЕН (SHALL NOT) быть независимым пользовательским измерением для этих kinds в persistent/wire contract.

#### Scenario: Redundant driver не создаёт новый definition fingerprint
- **GIVEN** два write-запроса описывают один и тот же executor для `ibcmd_cli`, но в одном payload присутствует redundant `driver=ibcmd`
- **WHEN** backend нормализует payload и вычисляет definition fingerprint
- **THEN** создаётся/используется один и тот же `operation_definition`
- **AND** дублирование definition из-за redundant `driver` не возникает

#### Scenario: Конфликт kind/driver валидируется fail-closed
- **GIVEN** write-запрос передаёт конфликтный payload (`executor_kind=ibcmd_cli` и `driver=cli`)
- **WHEN** backend выполняет validation
- **THEN** запрос отклоняется с детализированной ошибкой по пути поля
- **AND** exposure не публикуется и не переводится в валидное состояние автоматически

#### Scenario: Legacy записи нормализуются при миграции
- **GIVEN** в unified store есть legacy exposure/definition с redundant или конфликтным kind/driver
- **WHEN** выполняется migration/normalization step
- **THEN** корректные записи нормализуются в canonical shape
- **AND** конфликтные записи фиксируются в diagnostics/migration issues для ручной доработки

### Requirement: Legacy action-catalog exposures MUST быть удалены hard delete миграцией
Система ДОЛЖНА (SHALL) выполнить hard delete legacy записей `surface="action_catalog"` в рамках cutover migration.

#### Scenario: После миграции action-catalog rows отсутствуют
- **WHEN** завершена миграция cutover
- **THEN** в persistent store отсутствуют записи `operation_exposure.surface="action_catalog"`
- **AND** orphaned definitions, связанные только с удалёнными exposures, очищены

#### Scenario: Historical execution references сохраняются
- **GIVEN** operation definition исторически использовался в plan/execution/snapshot данных
- **WHEN** выполняется cutover migration
- **THEN** definition НЕ удаляется как orphan
- **AND** historical records остаются читаемыми для audit/details

### Requirement: Big-bang cutover MUST удалить legacy template projection в одном релизе
Система ДОЛЖНА (SHALL) в рамках того же релиза, где выполняется switch на exposure-only, удалить legacy template projection (`operation_templates` и зависимые permission/FK структуры), чтобы исключить dual-model drift.

Минимальный обязательный перечень удаления ДОЛЖЕН (SHALL) включать:
- `operation_templates`,
- `templates_operation_template_permissions`,
- `templates_operation_template_group_permissions`,
- `batch_operations.template_id` FK/column и связанные индексы/constraints.

#### Scenario: После cutover legacy projection отсутствует
- **WHEN** post-cutover проверки релиза завершены
- **THEN** persistent схема больше не содержит `operation_templates` и зависимые template-permission таблицы legacy модели
- **AND** smoke проверки runtime/API проходят без обращений к legacy projection
- **AND** `batch_operations` не содержит зависимости на `OperationTemplate` FK

