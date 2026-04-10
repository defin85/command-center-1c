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

### Requirement: `/settings/runtime` MUST host declarative runtime-control policy without duplicating live process controls
Система ДОЛЖНА (SHALL) использовать `/settings/runtime` как advanced settings workspace для declarative runtime-control policy keys, включая global scheduler enablement, per-job enablement и per-job cadence/schedule.

Policy edits для `schedule/cadence` МОГУТ (MAY) применяться через controlled runtime reload/reconcile path, пока explicit live reschedule contract не доставлен; страница НЕ ДОЛЖНА (SHALL NOT) обещать universal live edit всех cron expressions в `V1`.

Immediate lifecycle actions, `trigger_now` и другие live process controls НЕ ДОЛЖНЫ (SHALL NOT) становиться второй primary control console внутри `/settings/runtime`; primary operator path для них остаётся `/system-status`.

#### Scenario: Deep-link из `/system-status` восстанавливает selected scheduler policy context
- **GIVEN** staff оператор выбирает на `/system-status` действие `Edit schedule` для `pool_factual_active_sync`
- **WHEN** приложение открывает `/settings/runtime` с query state выбранного section/key
- **THEN** runtime settings workspace восстанавливает тот же scheduler policy context после reload/deep-link
- **AND** страница не дублирует `restart`/`trigger_now`/другие live process actions как второй primary console

