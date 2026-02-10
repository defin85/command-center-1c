# extensions-action-catalog Specification

## Purpose
TBD - created by archiving change add-extensions-action-catalog-runtime-setting. Update Purpose after archive.
## Requirements
### Requirement: RuntimeSetting для каталога действий расширений
Система ДОЛЖНА (SHALL) использовать unified persistent store как единственный source of truth для каталога действий расширений.

RuntimeSetting key `ui.action_catalog` НЕ ДОЛЖЕН (SHALL NOT) оставаться поддерживаемым runtime settings ключом для чтения, записи и overrides после decommission.

#### Scenario: Effective action catalog строится из unified exposures
- **GIVEN** в unified store есть published exposures с `surface="action_catalog"`
- **WHEN** пользователь вызывает endpoint получения action catalog
- **THEN** система возвращает effective catalog из unified exposures

#### Scenario: Legacy runtime key `ui.action_catalog` недоступен
- **WHEN** оператор пытается прочитать или изменить runtime setting `ui.action_catalog`
- **THEN** backend отклоняет запрос как unsupported/decommissioned key

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
Система ДОЛЖНА (SHALL) поддерживать явное поле `capability` в `operation_exposure(surface="action_catalog")`, чтобы backend определял семантику без привязки к `alias` (бывшему `action.id`).

#### Scenario: Произвольный alias exposure с capability работает
- **GIVEN** в `operation_exposure(surface="action_catalog")` есть действие с произвольным `alias` (например `ListExtension`)
- **AND** у него `capability` задан в формате namespaced string (например `extensions.list`)
- **AND** `executor.command_id` указывает на валидную команду драйвера
- **WHEN** пользователь запускает это действие
- **THEN** система трактует его как `extensions.list`, независимо от `alias`

### Requirement: Зарезервированные capability валидируются fail-closed
Система ДОЛЖНА (SHALL) обеспечивать детерминизм для reserved capability, которые backend понимает и использует для особой семантики (plan/apply, snapshot-marking), но НЕ ДОЛЖНА (SHALL NOT) требовать уникальности `capability` на уровне update-time валидации action exposures.

#### Scenario: Дубликаты reserved capability допускаются, но требуют детерминизма на запуске
- **GIVEN** в `operation_exposure(surface="action_catalog")` есть два actions с `capability="extensions.set_flags"`
- **WHEN** UI/клиент вызывает reserved endpoint без `action_id` (только по `capability`)
- **THEN** backend возвращает ошибку ambiguity и не выполняет действие
- **AND** error message содержит список candidate `alias`

### Requirement: Actions для управления флагами расширений через capability
Система ДОЛЖНА (SHALL) поддерживать зарезервированный capability `extensions.set_flags` для применения policy флагов расширений к списку баз (bulk).

#### Scenario: Effective action catalog содержит apply-flags action только если executor валиден
- **GIVEN** в `ui.action_catalog` есть действие с `capability="extensions.set_flags"`
- **WHEN** executor этого действия невалиден (unknown command / missing workflow / запрещённый dangerous)
- **THEN** действие исключается из effective action catalog (fail-closed)

### Requirement: extensions.set_flags поддерживает selective apply через params-based executor
Система ДОЛЖНА (SHALL) обеспечивать selective apply для reserved capability `extensions.set_flags` через params-based executor и runtime-токены `$flags.*`.

#### Scenario: selective apply использует runtime flags и request mask
- **GIVEN** action `extensions.set_flags` задаёт флаговые параметры через `$flags.*` в `executor.params`
- **WHEN** оператор запускает plan/apply с `flags_values` и `apply_mask`
- **THEN** backend применяет mask, удаляя невыбранные флаги из effective params
- **AND** если executor не params-based, backend возвращает ошибку конфигурации (fail-closed)

### Requirement: Presets для `extensions.set_flags` через `executor.fixed.apply_mask`
Система НЕ ДОЛЖНА (SHALL NOT) поддерживать presets selective apply для `extensions.set_flags` на уровне action catalog через `executor.fixed.apply_mask`.

#### Scenario: Exposure с preset apply_mask становится невалидным
- **GIVEN** action/exposure с `capability="extensions.set_flags"` содержит `executor.fixed.apply_mask` (или exposure-level `capability_config.apply_mask`)
- **WHEN** exposure проходит validate/publish
- **THEN** backend возвращает ошибку валидации по пути preset-поля
- **AND** exposure не публикуется в effective action catalog

### Requirement: Unified action exposure MUST хранить capability-specific binding contract
Система ДОЛЖНА (SHALL) хранить capability-specific поля (`target_binding`, preset-поля и т.п.) на уровне exposure, с fail-closed валидацией для reserved capability.

#### Scenario: `extensions.set_flags` exposure без target binding не публикуется
- **GIVEN** exposure имеет `capability="extensions.set_flags"`
- **AND** не содержит валидного `target_binding.extension_name_param`
- **WHEN** exposure валидируется перед публикацией
- **THEN** exposure получает статус `invalid`
- **AND** не попадает в effective action catalog

### Requirement: `extensions.set_flags` binding MUST валидироваться против схемы команды
Система ДОЛЖНА (SHALL) для `capability="extensions.set_flags"` проверять, что `target_binding.extension_name_param` существует в `params_by_name` команды, привязанной к definition/exposure.

#### Scenario: Binding указывает на неизвестный параметр команды
- **GIVEN** exposure `extensions.set_flags` ссылается на command definition
- **AND** `target_binding.extension_name_param` отсутствует в `params_by_name` этой команды
- **WHEN** exposure проходит validate/publish
- **THEN** система возвращает ошибку валидации по пути binding-поля
- **AND** exposure остаётся в статусе `invalid`

### Requirement: `extensions.set_flags` action SHALL быть transport/binding-конфигурацией
Система ДОЛЖНА (SHALL) хранить в action catalog для `extensions.set_flags` только transport/binding/safety конфигурацию и НЕ ДОЛЖНА (SHALL NOT) хранить runtime state (значения флагов и selective mask).

#### Scenario: Runtime state не хранится в exposure
- **GIVEN** staff редактирует action с `capability="extensions.set_flags"`
- **WHEN** action сохраняется
- **THEN** exposure не содержит capability-specific runtime state (`apply_mask`, fixed значения флагов)
- **AND** runtime state передаётся только в request/workflow input при запуске

