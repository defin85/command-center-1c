## ADDED Requirements
### Requirement: `/settings/command-schemas` MUST использовать canonical command schema workspace
Система ДОЛЖНА (SHALL) представлять `/settings/command-schemas` как platform-owned command schema workspace с route-addressable driver/mode/selected command context и responsive fallback для inspect/editor path.

#### Scenario: Deep-link восстанавливает driver, mode и selected command
- **GIVEN** staff пользователь открывает `/settings/command-schemas` с query state, указывающим активный driver, mode и выбранную команду
- **WHEN** страница загружается повторно или пользователь использует browser back/forward
- **THEN** workspace восстанавливает тот же driver/mode/command context
- **AND** primary inspect/editor flow остаётся внутри canonical workspace shell
