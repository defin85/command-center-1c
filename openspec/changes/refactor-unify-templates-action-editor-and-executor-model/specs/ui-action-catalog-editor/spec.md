## MODIFIED Requirements
### Requirement: Поддержка executor kinds
Система ДОЛЖНА (SHALL) поддерживать в editor-е executor kinds `ibcmd_cli`, `designer_cli` и `workflow`, а capability-специфичные поля НЕ ДОЛЖНЫ (SHALL NOT) масштабироваться через хардкод условных веток в UI.

Для canonical kinds UI НЕ ДОЛЖЕН (SHALL NOT) требовать отдельный ручной выбор `driver`; `driver` ДОЛЖЕН (SHALL) определяться из `executor.kind`:
- `ibcmd_cli -> ibcmd`
- `designer_cli -> cli`
- `workflow -> driver не применяется`

#### Scenario: `ibcmd_cli` использует ibcmd catalog без отдельного driver select
- **WHEN** staff выбирает `executor.kind=ibcmd_cli`
- **THEN** editor показывает команды из `ibcmd` catalog
- **AND** UI не показывает отдельное обязательное поле `driver`

#### Scenario: `designer_cli` использует cli catalog без отдельного driver select
- **WHEN** staff выбирает `executor.kind=designer_cli`
- **THEN** editor показывает команды из `cli` catalog
- **AND** UI не показывает отдельное обязательное поле `driver`

#### Scenario: `workflow` скрывает command fields
- **WHEN** staff выбирает `executor.kind=workflow`
- **THEN** editor показывает `workflow_id`
- **AND** поля `driver/command_id` не используются и не сериализуются как обязательные

### Requirement: Editor MUST использовать shared command-config contract с Templates UI
Система ДОЛЖНА (SHALL) использовать единый frontend editor pipeline (shared component + adapter + serializer + validation mapping) для surfaces `template` и `action_catalog` в одном UI, чтобы исключить дублирование логики и расхождения UX.

#### Scenario: Единый modal editor используется в двух surfaces
- **GIVEN** staff открывает `/templates`
- **WHEN** создаёт/редактирует exposure в `template` и в `action_catalog`
- **THEN** используется один и тот же modal editor shell и одна state-модель формы
- **AND** различаются только surface-specific поля/ограничения

#### Scenario: Одинаковая command-конфигурация сериализуется одинаково в двух surfaces
- **GIVEN** оператор задаёт одинаковые `executor.kind`, `command_id`, `params`, `additional_args`, `stdin`, safety-поля
- **WHEN** сохраняет exposure как `template` и как `action_catalog`
- **THEN** serialized execution payload в unified definition совпадает по контракту
- **AND** не возникает surface-specific расхождения executor shape
