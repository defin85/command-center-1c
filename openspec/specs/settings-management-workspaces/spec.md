# settings-management-workspaces Specification

## Purpose
TBD - created by archiving change 03-refactor-ui-platform-admin-support-workspaces. Update Purpose after archive.
## Requirements
### Requirement: `/settings/runtime` MUST использовать canonical settings workspace
Система ДОЛЖНА (SHALL) представлять `/settings/runtime` как settings management workspace с URL-addressable selected section/setting context и canonical edit surfaces внутри platform-owned shell.

#### Scenario: Runtime settings workspace восстанавливает выбранную настройку из URL
- **GIVEN** staff пользователь открывает `/settings/runtime` с query state, указывающим выбранную секцию или настройку
- **WHEN** страница перезагружается или открывается по deep-link
- **THEN** workspace восстанавливает выбранный settings context
- **AND** primary edit flow не зависит от bespoke page-level table orchestration как единственного пути

### Requirement: `/settings/timeline` MUST использовать timeline settings workspace с secondary diagnostics
Система ДОЛЖНА (SHALL) представлять `/settings/timeline` как settings workspace, где runtime controls являются primary path, а stream diagnostics и queue reset остаются secondary surfaces внутри того же platform shell.

#### Scenario: Narrow viewport сохраняет доступ к timeline controls без page-wide overflow
- **GIVEN** staff пользователь открывает `/settings/timeline` на узком viewport
- **WHEN** взаимодействует с runtime controls и secondary diagnostics
- **THEN** primary settings flow остаётся доступным без page-wide horizontal overflow
- **AND** stream diagnostics/remediation не конкурируют с основным settings catalog как параллельный page-level layout

