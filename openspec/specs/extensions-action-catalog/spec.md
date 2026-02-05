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

#### Scenario: ibcmd_cli action маппится на execute-ibcmd-cli и использует профиль подключения базы
- **WHEN** действие использует executor `ibcmd_cli`
- **THEN** его можно выполнить через `POST /api/v2/operations/execute-ibcmd-cli/` с промаппленными полями
- **AND** действие НЕ содержит `executor.connection` (connection не хранится на уровне action)
- **AND** connection для каждой таргет-базы резолвится из профиля подключения этой базы (или per-run override, если задан)
- **AND** mixed mode допустим (часть баз remote, часть offline) в рамках одного bulk запуска

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

#### Scenario: Snapshot обновляется после успешного list/sync (capability-based)
- **WHEN** завершается успешная операция list/sync расширений, помеченная как snapshot-producing
- **THEN** запись snapshot расширений для этой базы upsert'ится с актуальными данными

### Requirement: Staff может увидеть plan/provenance при запуске действия расширений
Система ДОЛЖНА (SHALL) позволять staff пользователю увидеть Execution Plan + Binding Provenance при запуске действий расширений из UI (drawer `/databases`) до подтверждения запуска, без раскрытия секретов.

#### Scenario: Staff видит preview перед запуском действия расширений
- **GIVEN** действие по расширениям доступно пользователю из effective action catalog
- **WHEN** staff открывает drawer запуска и запрашивает preview
- **THEN** UI отображает plan+bindings и только после подтверждения создаёт операцию/исполнение

### Requirement: User-friendly ошибки preflight для действий расширений
Система ДОЛЖНА (SHALL) показывать ошибки preflight `ibcmd_cli` при запуске действий расширений из UI в user-friendly виде, согласованном с мастером операций.

#### Scenario: OFFLINE_DB_METADATA_NOT_CONFIGURED отображается как actionable подсказка
- **GIVEN** пользователь запускает действие расширений с `executor.kind=ibcmd_cli` и `connection.offline`
- **AND** DBMS metadata для части таргетов не настроены
- **WHEN** backend возвращает `HTTP 400` с `error.code=OFFLINE_DB_METADATA_NOT_CONFIGURED`
- **THEN** UI показывает понятную инструкцию, что нужно заполнить DBMS metadata на `/databases` или задать override через `connection.offline.*`

### Requirement: Семантика extensions действий задаётся capability, а не id
Система ДОЛЖНА (SHALL) поддерживать явное поле `capability` для действий extensions в `ui.action_catalog`, чтобы backend мог определять семантику без привязки к `action.id`.

#### Scenario: Произвольный action.id с capability работает
- **GIVEN** в `ui.action_catalog` есть действие с произвольным `id` (например `ListExtension`)
- **AND** у него `capability` задан в формате namespaced string (например `extensions.list`)
- **AND** `executor.command_id` указывает на валидную команду драйвера
- **WHEN** пользователь запускает это действие
- **THEN** система трактует его как `extensions.list` (для plan/apply и snapshot-marking), независимо от `id`

### Requirement: Зарезервированные capability валидируются fail-closed
Система ДОЛЖНА (SHALL) обеспечивать детерминизм для reserved capability, которые backend понимает и использует для особой семантики (plan/apply, snapshot-marking), но НЕ ДОЛЖНА (SHALL NOT) требовать уникальности `capability` на уровне update-time валидации `ui.action_catalog`.

#### Scenario: Дубликаты reserved capability допускаются, но требуют детерминизма на запуске
- **GIVEN** в `ui.action_catalog` есть два actions с `capability="extensions.set_flags"`
- **WHEN** UI/клиент вызывает reserved endpoint без `action_id` (только по `capability`)
- **THEN** backend возвращает ошибку ambiguity и не выполняет действие
- **AND** error message содержит список candidate `action.id`

### Requirement: Actions для управления флагами расширений через capability
Система ДОЛЖНА (SHALL) поддерживать зарезервированный capability `extensions.set_flags` для применения policy флагов расширений к списку баз (bulk).

#### Scenario: Effective action catalog содержит apply-flags action только если executor валиден
- **GIVEN** в `ui.action_catalog` есть действие с `capability="extensions.set_flags"`
- **WHEN** executor этого действия невалиден (unknown command / missing workflow / запрещённый dangerous)
- **THEN** действие исключается из effective action catalog (fail-closed)

### Requirement: extensions.set_flags поддерживает selective apply через params-based executor
Система ДОЛЖНА (SHALL) обеспечивать selective apply для reserved capability `extensions.set_flags` через executor, который задаёт флаги в `executor.params`.

#### Scenario: selective apply требует params-based executor shape
- **GIVEN** в `ui.action_catalog` есть действие с `capability="extensions.set_flags"`
- **WHEN** оператор запускает selective apply (не все флаги выбраны)
- **THEN** backend применяет mask, удаляя невыбранные флаги из `executor.params`
- **AND** если executor не поддерживает params-based режим (например, использует только `additional_args`), backend возвращает ошибку конфигурации (fail-closed)

### Requirement: Presets для `extensions.set_flags` через `executor.fixed.apply_mask`
Система ДОЛЖНА (SHALL) поддерживать presets selective apply для `extensions.set_flags` на уровне action catalog через `executor.fixed.apply_mask`.

#### Scenario: apply_mask берётся из action preset по умолчанию
- **GIVEN** action с `capability="extensions.set_flags"` содержит `executor.fixed.apply_mask`, выбирающий только один флаг (например `active=true`, остальные `false`)
- **WHEN** UI вызывает plan без `apply_mask`, но с `action_id` этого action
- **THEN** backend использует `executor.fixed.apply_mask` как effective mask
- **AND** apply изменяет только выбранный флаг

