## ADDED Requirements
### Requirement: Pool workflow steps MUST резолвиться в templates с executor kind `pool_driver`
Система ДОЛЖНА (SHALL) компилировать и исполнять pool workflow steps через template aliases, где template definition использует `executor_kind=pool_driver` и `driver=pool`.

#### Scenario: distribution_calculation step выполняется через pool_driver template
- **GIVEN** workflow node `distribution_calculation` ссылается на template alias
- **WHEN** runtime резолвит alias в published template
- **THEN** template имеет `executor_kind=pool_driver`
- **AND** backend routing выполняется через schema-driven pool driver path

### Requirement: Pool workflow runtime MUST fail-closed при отсутствии pool driver binding
Система ДОЛЖНА (SHALL) отклонять выполнение pool workflow node, если отсутствует валидный `pool_driver` template binding или соответствующая command schema.

Система НЕ ДОЛЖНА (SHALL NOT) silently fallback на неподходящий executor kind.

#### Scenario: Missing pool command schema блокирует запуск run
- **GIVEN** template alias существует, но `command_id` отсутствует в effective `pool` command catalog
- **WHEN** система пытается создать/исполнить workflow run
- **THEN** выполнение отклоняется fail-closed ошибкой конфигурации
- **AND** node side effects не выполняются

### Requirement: Binding policy MUST поддерживать поэтапный переход к pinned режиму
Система ДОЛЖНА (SHALL) поддерживать включаемую policy, где для `pool_driver` workflow nodes допускается:
- переходный режим `alias_latest`;
- enforced режим `pinned_exposure`.

#### Scenario: Enforced pinned policy отклоняет alias-only сохранение
- **GIVEN** runtime setting pinned enforcement включен для pool workflow
- **WHEN** workflow сохраняется с node binding в режиме `alias_latest`
- **THEN** сохранение отклоняется ошибкой политики binding mode
