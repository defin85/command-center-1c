## MODIFIED Requirements
### Requirement: Staff-only UI редактор каталога действий
Система ДОЛЖНА (SHALL) предоставлять staff-only редактирование action exposures только внутри единого экрана `/templates` (surface `action_catalog`), а не через отдельный legacy UI route.

#### Scenario: Non-staff не имеет доступа к action surface
- **WHEN** non-staff пользователь открывает `/templates`
- **THEN** action-catalog surface недоступен
- **AND** данные action exposures не раскрываются

#### Scenario: Staff видит текущую конфигурацию action exposures
- **WHEN** staff пользователь открывает `/templates` и выбирает surface `action_catalog`
- **THEN** UI загружает текущие action exposures из unified store и отображает actions

#### Scenario: Отдельный route action-catalog не используется как editor
- **WHEN** пользователь пытается открыть `/settings/action-catalog`
- **THEN** приложение не предоставляет legacy editor flow для управления action exposures

### Requirement: Editor MUST использовать shared command-config contract с Templates UI
Система ДОЛЖНА (SHALL) использовать единый frontend editor pipeline (adapter + serializer + validation mapping) для surfaces `template` и `action_catalog` в одном UI, чтобы исключить дублирование логики.

#### Scenario: Одинаковая command-конфигурация сериализуется одинаково в двух surfaces
- **GIVEN** оператор задаёт одинаковые `command_id`, `params`, `additional_args`, `stdin`, safety-поля
- **WHEN** сохраняет exposure как `template` и как `action_catalog`
- **THEN** serialized execution payload в unified definition совпадает по контракту
- **AND** не возникает surface-specific расхождения executor shape
