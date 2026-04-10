## ADDED Requirements

### Requirement: `/settings/runtime` MUST host declarative runtime-control policy without duplicating live process controls
Система ДОЛЖНА (SHALL) использовать `/settings/runtime` как advanced settings workspace для declarative runtime-control policy keys, включая global scheduler enablement, per-job enablement и per-job cadence/schedule.

Policy edits для `schedule/cadence` МОГУТ (MAY) применяться через controlled runtime reload/reconcile path, пока explicit live reschedule contract не доставлен; страница НЕ ДОЛЖНА (SHALL NOT) обещать universal live edit всех cron expressions в `V1`.

Immediate lifecycle actions, `trigger_now` и другие live process controls НЕ ДОЛЖНЫ (SHALL NOT) становиться второй primary control console внутри `/settings/runtime`; primary operator path для них остаётся `/system-status`.

#### Scenario: Deep-link из `/system-status` восстанавливает selected scheduler policy context
- **GIVEN** staff оператор выбирает на `/system-status` действие `Edit schedule` для `pool_factual_active_sync`
- **WHEN** приложение открывает `/settings/runtime` с query state выбранного section/key
- **THEN** runtime settings workspace восстанавливает тот же scheduler policy context после reload/deep-link
- **AND** страница не дублирует `restart`/`trigger_now`/другие live process actions как второй primary console
