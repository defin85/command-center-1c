# Спецификация: command-schemas-driver-options

## Purpose
Определяет разделение схемы на driver-level (`driver_schema`) и command-level (`commands_by_id.<id>.params_by_name`) для schema-driven драйверов (MVP: `ibcmd`), включая правила сборки канонического `argv[]` и политику конфликтов.
## Requirements
### Requirement: Driver schema для schema-driven драйверов
Система ДОЛЖНА (SHALL) поддерживать driver-level schema (отдельно от command schema) для schema-driven драйверов (минимум `ibcmd`).

#### Scenario: Driver schema существует отдельно от params_by_name команды
- **WHEN** администратор открывает “Command Schemas” для драйвера `ibcmd`
- **THEN** UI отображает отдельный раздел driver-level schema, не зависящий от выбранной команды

### Requirement: Connection options не валидируются как params команды
Система ДОЛЖНА (SHALL) обрабатывать `connection.*` как driver-level connection options и НЕ валидировать их через `commands_by_id.<id>.params_by_name`.

#### Scenario: Команда без params_by_name принимает connection.remote
- **GIVEN** в каталоге команда имеет пустой `params_by_name`
- **WHEN** пользователь выполняет schema-driven команду и задаёт `connection.remote`
- **THEN** запрос не завершается ошибкой вида `params are not supported for this command`

### Requirement: Канонический argv включает driver options + command params
Система ДОЛЖНА (SHALL) формировать канонический `argv[]` (и `argv_masked[]`) на стороне API до постановки операции в очередь, включая:
1) driver-level connection options (`connection.*`)
2) command-level params (`params`)
3) `additional_args` после нормализации

Система ДОЛЖНА (SHALL) дополнительно формировать `bindings[]` (Binding Provenance), описывающий происхождение каждого добавленного/нормализованного элемента `argv` и его источник (request/driver catalog/action catalog/database/env), без хранения секретов.

#### Scenario: Preview отражает provenance для argv
- **WHEN** staff делает preview для schema-driven команды с заполненными `connection`/`params`/`additional_args`
- **THEN** preview возвращает `argv_masked[]` и `bindings[]`, где видно, какие элементы пришли из `connection`, какие из `params`, а какие из `additional_args`/нормализации

### Requirement: Поддержка overrides для driver schema
Система ДОЛЖНА (SHALL) позволять переопределять driver-level schema через overrides (аналогично overrides для команд), чтобы изменения проходили через те же пайплайны “Command Schemas”.

#### Scenario: Overrides изменяют driver-level schema без правки base
- **GIVEN** базовый каталог определяет driver schema
- **WHEN** администратор сохраняет overrides, меняя driver-level schema
- **THEN** effective catalog отражает изменения driver schema без изменения base-версии

### Requirement: Явная политика конфликтов
Система ДОЛЖНА (SHALL) иметь документированную и реализованную политику конфликтов для driver-level флагов, когда один и тот же параметр задан в нескольких местах (например `connection` и `additional_args`).

#### Scenario: Конфликт remote между connection и additional_args
- **WHEN** пользователь задаёт `connection.remote` и одновременно добавляет `--remote=...` в `additional_args`
- **THEN** система возвращает ошибку валидации (error), и это поведение документировано

