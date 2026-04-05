# workflow-management-workspaces Specification

## Purpose
Определяет canonical platform-owned workspace contract для workflow library, workflow authoring, execution diagnostics и monitor surfaces с URL-addressable state, shell-safe handoff и responsive secondary surfaces.
## Requirements
### Requirement: `/workflows` MUST использовать canonical workflow library workspace
Система ДОЛЖНА (SHALL) представлять `/workflows` как workflow library workspace с URL-addressable selected surface/filter/workflow context и shell-safe handoff в workflow authoring и execution paths.

#### Scenario: Workflow library восстанавливает selected context из URL
- **GIVEN** оператор открывает `/workflows` с query state, указывающим surface, фильтры или выбранный workflow
- **WHEN** страница перезагружается или открывается по deep-link
- **THEN** workspace восстанавливает тот же library context
- **AND** primary navigation в designer или execute path выполняется внутри canonical workspace flow

### Requirement: Workflow designer MUST использовать canonical authoring workspace
Система ДОЛЖНА (SHALL) представлять `/workflows/new` и `/workflows/:id` как workflow authoring workspace с route-addressable selected workflow/node context и canonical secondary surfaces для save/execute/inspect flows.

#### Scenario: Designer сохраняет selected workflow node context при reload/back-forward
- **GIVEN** оператор открыл workflow designer и выбрал конкретный node
- **WHEN** происходит reload, deep-link open или browser back/forward
- **THEN** workspace восстанавливает selected workflow/node context
- **AND** inspect/edit flow не зависит от bespoke full-page side panels как единственного contract boundary

### Requirement: `/workflows/executions` MUST использовать executions workspace
Система ДОЛЖНА (SHALL) представлять `/workflows/executions` как diagnostics catalog workspace с URL-addressable selected filters/execution context и shell-safe handoff в execution monitor.

#### Scenario: Executions workspace переводит в monitor без потери SPA shell
- **GIVEN** оператор открыл `/workflows/executions` и выбрал execution
- **WHEN** он переходит в `/workflows/executions/:executionId`
- **THEN** navigation выполняется внутри SPA shell без full-document reload
- **AND** selected list context остаётся восстанавливаемым через URL

### Requirement: Workflow monitor MUST использовать responsive diagnostics workspace
Система ДОЛЖНА (SHALL) представлять `/workflows/executions/:executionId` как diagnostics workspace с route-addressable selected execution/node context и responsive fallback для detail/trace inspection.

#### Scenario: Narrow viewport сохраняет доступ к node inspection
- **GIVEN** оператор открыл workflow monitor на узком viewport
- **WHEN** выбирает node или trace details
- **THEN** diagnostics flow остаётся доступным через canonical secondary surface
- **AND** страница не зависит от page-wide horizontal overflow как основного inspect режима
