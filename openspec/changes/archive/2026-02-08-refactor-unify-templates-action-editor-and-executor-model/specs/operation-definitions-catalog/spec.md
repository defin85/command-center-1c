## ADDED Requirements
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
