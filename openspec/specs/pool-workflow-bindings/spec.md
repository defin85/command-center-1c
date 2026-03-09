# pool-workflow-bindings Specification

## Purpose
TBD - created by archiving change refactor-12-workflow-centric-analyst-modeling. Update Purpose after archive.
## Requirements
### Requirement: Pools MUST поддерживать несколько workflow bindings в одном организационном контуре
Система ДОЛЖНА (SHALL) поддерживать `pool_workflow_binding` как versioned связь между конкретным `pool` и pinned revision workflow definition.

Binding ДОЛЖЕН (SHALL) хранить как минимум:
- `pool_id`;
- `workflow_definition_id`;
- `workflow_revision`;
- effective period;
- binding parameters;
- role mapping или эквивалентную контекстную привязку;
- binding status.

Один `pool` МОЖЕТ (MAY) иметь несколько одновременно активных bindings, если они различимы по selector/effective period и не создают ambiguity.

#### Scenario: Один pool использует две разные схемы одновременно
- **GIVEN** один `pool` имеет binding `top_down_services_v3` и binding `bottom_up_import_v2`
- **WHEN** оператор открывает список доступных схем для этого pool
- **THEN** интерфейс показывает оба binding
- **AND** каждый binding указывает на собственную pinned workflow revision

### Requirement: Pool workflow binding resolution MUST быть детерминированной и fail-closed
Система ДОЛЖНА (SHALL) резолвить binding для запуска run либо явно по выбранному `pool_workflow_binding_id`, либо по детерминированным selector-правилам.

Если запрос запуска подходит более чем к одному активному binding без явного disambiguation, система НЕ ДОЛЖНА (SHALL NOT) молча выбирать один из них.

#### Scenario: Ambiguous binding блокирует запуск run
- **GIVEN** для одного `pool` активны два binding с пересекающимся effective scope
- **WHEN** оператор пытается запустить run без явного выбора binding
- **THEN** система отклоняет запуск fail-closed
- **AND** возвращает machine-readable диагностику ambiguity

### Requirement: Pool workflow binding MUST предоставлять preview effective runtime projection
Система ДОЛЖНА (SHALL) предоставлять preview binding-а до запуска, достаточный для понимания:
- какой workflow revision будет выполнен;
- какие decisions/parameters будут применены;
- какая concrete runtime projection будет собрана;
- какой lineage получит run.

#### Scenario: Binding preview показывает workflow lineage и compiled projection summary
- **GIVEN** аналитик или оператор открывает binding перед запуском
- **WHEN** система строит preview
- **THEN** preview показывает pinned workflow revision, linked decisions и compiled projection summary
- **AND** пользователь видит, какой именно binding будет исполнен до старта run

