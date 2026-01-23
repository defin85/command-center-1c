# extensions-action-catalog Specification

## Purpose
TBD - created by archiving change add-extensions-action-catalog-runtime-setting. Update Purpose after archive.
## Requirements
### Requirement: RuntimeSetting для каталога действий расширений
Система ДОЛЖНА (SHALL) хранить каталог действий расширений в ключе RuntimeSetting `ui.action_catalog`.

#### Scenario: Нет каталога -> пустой результат
- **WHEN** `ui.action_catalog` не настроен
- **THEN** система возвращает пустой каталог действий расширений

#### Scenario: Валидный каталог доступен
- **WHEN** в `ui.action_catalog` настроен валидный action catalog
- **THEN** система возвращает настроенные actions для расширений и executor bindings

### Requirement: API для effective action catalog
Система ДОЛЖНА (SHALL) предоставить API endpoint, который возвращает effective action catalog для текущего пользователя.

#### Scenario: Пользователь получает только разрешённые действия
- **WHEN** пользователь запрашивает action catalog
- **THEN** ответ исключает действия, которые пользователь не имеет права видеть или выполнять

### Requirement: Action executors
Система ДОЛЖНА (SHALL) поддерживать action executors `ibcmd_cli`, `designer_cli` и `workflow` в action catalog.

#### Scenario: ibcmd_cli action маппится на execute-ibcmd-cli
- **WHEN** действие использует executor `ibcmd_cli`
- **THEN** его можно выполнить через `POST /api/v2/operations/execute-ibcmd-cli/` с промаппленными полями

#### Scenario: workflow action маппится на execute-workflow
- **WHEN** действие использует executor `workflow`
- **THEN** его можно выполнить через `POST /api/v2/workflows/execute-workflow/` с промаппленными `workflow_id` и `input_context`

### Requirement: Deactivate и delete — разные действия
Система ДОЛЖНА (SHALL) моделировать деактивацию и удаление расширения как отдельные действия с разной семантикой.

#### Scenario: Deactivate не удаляет
- **WHEN** оператор выполняет действие deactivate для расширения `X`
- **THEN** расширение `X` остаётся установленным, меняется только его флаг активности

#### Scenario: Delete удаляет расширение
- **WHEN** оператор выполняет действие delete для расширения `X` и подтверждает dangerous operation
- **THEN** расширение `X` удаляется из инфобазы

### Requirement: Bulk execution
Система ДОЛЖНА (SHALL) поддерживать выполнение действий над расширениями для одной базы или для списка баз (bulk).

#### Scenario: Bulk создаёт per-database tasks
- **WHEN** оператор выполняет per-database действие для N баз
- **THEN** создаётся одна batch operation с N tasks

### Requirement: Fail-closed validation
Система ДОЛЖНА (SHALL) валидировать элементы action catalog по доступным driver catalogs и workflows и MUST fail closed для невалидных ссылок.

#### Scenario: Unknown command фильтруется
- **WHEN** действие ссылается на `command_id`, которого нет в effective driver catalog
- **THEN** действие исключается из effective action catalog

#### Scenario: Dangerous commands скрыты от non-staff
- **WHEN** действие резолвится в dangerous command, а пользователь не staff
- **THEN** действие исключается из effective action catalog

### Requirement: Snapshot расширений в Postgres
Система ДОЛЖНА (SHALL) хранить последний известный snapshot расширений по каждой базе в Postgres.

#### Scenario: Snapshot обновляется после успешного sync
- **WHEN** настроенное действие sync для расширений успешно завершается для базы
- **THEN** запись snapshot расширений для этой базы upsert'ится с актуальными данными

### Requirement: Staff может увидеть plan/provenance при запуске действия расширений
Система ДОЛЖНА (SHALL) позволять staff пользователю увидеть Execution Plan + Binding Provenance при запуске действий расширений из UI (drawer `/databases`) до подтверждения запуска, без раскрытия секретов.

#### Scenario: Staff видит preview перед запуском действия расширений
- **GIVEN** действие по расширениям доступно пользователю из effective action catalog
- **WHEN** staff открывает drawer запуска и запрашивает preview
- **THEN** UI отображает plan+bindings и только после подтверждения создаёт операцию/исполнение

