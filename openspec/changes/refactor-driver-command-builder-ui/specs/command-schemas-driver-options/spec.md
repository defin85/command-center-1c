# Спецификация (delta): command-schemas-driver-options

## MODIFIED Requirements

### Requirement: Driver schema для schema-driven драйверов
Система ДОЛЖНА (SHALL) поддерживать driver-level schema (отдельно от command schema) для schema-driven драйверов (минимум `ibcmd`, а также `cli` для driver-level опций).

#### Scenario: Driver schema описывает execution context и опции драйвера
- **WHEN** UI загружает driver schema для `ibcmd`
- **THEN** schema содержит описание driver-level полей execution context (например `connection.*`, `timeout_seconds`, `stdin`, `auth_database_id`) и их UI‑метаданные (группировка/порядок)

#### Scenario: Driver schema описывает CLI extra options
- **WHEN** UI загружает driver schema для `cli`
- **THEN** schema содержит описание `cli_options.*` (startup/logging) как driver-level опций, отдельно от `params_by_name` команд

### Requirement: Connection options не валидируются как params команды
Система ДОЛЖНА (SHALL) обрабатывать `connection.*` и прочие driver-level поля execution context (включая `timeout_seconds`, `stdin`, `auth_database_id`) как driver-level options и НЕ валидировать их через `commands_by_id.<id>.params_by_name`.

#### Scenario: Команда без params_by_name принимает driver-level execution context
- **GIVEN** в каталоге команда имеет пустой `params_by_name`
- **WHEN** пользователь выполняет schema-driven команду и задаёт `connection.remote` и `timeout_seconds`
- **THEN** запрос не завершается ошибкой вида `params are not supported for this command`

