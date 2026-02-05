# ui-action-catalog-editor Specification

## Purpose
TBD - created by archiving change add-ui-action-catalog-editor. Update Purpose after archive.
## Requirements
### Requirement: Staff-only UI редактор каталога действий
Система ДОЛЖНА (SHALL) предоставить staff-only UI для просмотра и редактирования `ui.action_catalog`.

#### Scenario: Non-staff не имеет доступа
- **WHEN** non-staff пользователь открывает страницу редактора
- **THEN** доступ запрещён (403/redirect) и данные каталога не раскрываются

#### Scenario: Staff видит текущую конфигурацию
- **WHEN** staff пользователь открывает страницу редактора
- **THEN** UI загружает текущий `ui.action_catalog` и отображает actions

### Requirement: Guided editor + Raw JSON toggle
Система ДОЛЖНА (SHALL) поддерживать два режима редактирования: guided UI и Raw JSON, с возможностью переключения.

#### Scenario: Переключение режимов
- **WHEN** staff пользователь переключает guided ↔ raw
- **THEN** изменения сохраняются в рамках текущей сессии редактирования и не теряются без явного Save

### Requirement: Поддержка executor kinds
Система ДОЛЖНА (SHALL) поддерживать в редакторе executor kinds `ibcmd_cli`, `designer_cli` и `workflow`.

#### Scenario: ibcmd_cli выбирается из driver catalog и не содержит connection на уровне action
- **WHEN** staff создаёт/редактирует действие с executor `ibcmd_cli`
- **THEN** UI позволяет выбрать `driver` и `command_id` из доступного driver catalog и сохранить конфигурацию
- **AND** UI НЕ позволяет задавать `executor.connection` в action (connection резолвится из профиля базы при запуске)

#### Scenario: workflow выбирается из списка workflow templates
- **WHEN** staff создаёт/редактирует действие с executor `workflow`
- **THEN** UI позволяет выбрать `workflow_id` из списка доступных workflow templates и сохранить конфигурацию

#### Scenario: designer_cli редактируется как CLI command
- **WHEN** staff создаёт/редактирует действие с executor `designer_cli`
- **THEN** UI позволяет задать команду/аргументы и сохранить конфигурацию

#### Scenario: UI предлагает params template из command schema при создании action
- **GIVEN** staff открывает modal создания нового action в guided editor
- **AND** выбран `executor.kind` из `{ibcmd_cli, designer_cli}`
- **WHEN** staff выбирает `driver` и `command_id` из driver catalog
- **THEN** UI показывает список параметров команды из schema (`params_by_name`) с признаками required/default
- **AND** UI предлагает “Insert params template” для заполнения `executor.params` объектом-шаблоном (ключи из `params_by_name`)
- **AND** auto-fill НЕ должен затирать уже введённый JSON в `params` без явного подтверждения пользователя

#### Scenario: params template не включает disabled и ibcmd connection params
- **GIVEN** выбран `driver=ibcmd` и `command_id`
- **WHEN** UI строит список параметров и template для `executor.params`
- **THEN** UI исключает параметры, помеченные как `disabled`
- **AND** UI исключает параметры, относящиеся к connection (которые должны приходить из профиля базы), чтобы не вводить оператора в заблуждение

### Requirement: Save с серверной валидацией и отображением ошибок
Система ДОЛЖНА (SHALL) сохранять изменения через backend и показывать ошибки валидации пользователю.

#### Scenario: Ошибка валидации отображается с путём
- **WHEN** staff сохраняет невалидный action catalog
- **THEN** UI показывает список ошибок, включая пути вида `extensions.actions[i]...`, чтобы пользователь мог исправить конфигурацию

#### Scenario: Успешное сохранение
- **WHEN** staff сохраняет валидный action catalog
- **THEN** UI подтверждает успешное сохранение и отображает актуальную сохранённую версию

### Requirement: Preview execution plan в редакторе action catalog
Система ДОЛЖНА (SHALL) предоставить в staff-only редакторе `ui.action_catalog` возможность сделать preview для выбранного action и увидеть:
- Execution Plan (в masked виде),
- Binding Provenance (источники и места подстановки),
без раскрытия секретов.

#### Scenario: Staff видит preview plan+provenance для ibcmd_cli
- **WHEN** staff выбирает action с `executor.kind=ibcmd_cli` и нажимает Preview
- **THEN** UI отображает `argv_masked[]` и список биндингов (включая пометки `resolve_at=api|worker`)

#### Scenario: Staff видит preview plan+provenance для workflow
- **WHEN** staff выбирает action с `executor.kind=workflow` и нажимает Preview
- **THEN** UI отображает `workflow_id`, `input_context_masked` и список биндингов

### Requirement: Preview и ошибки `ibcmd_cli` согласованы с Operations
Система ДОЛЖНА (SHALL) показывать ошибки preview для `executor.kind=ibcmd_cli` в user-friendly виде, согласованном с UX запуска `ibcmd` в мастере операций.

#### Scenario: OFFLINE_DB_METADATA_NOT_CONFIGURED отображается с инструкцией
- **GIVEN** staff нажимает Preview для action с `executor.kind=ibcmd_cli`
- **AND** backend возвращает `HTTP 400` с `error.code=OFFLINE_DB_METADATA_NOT_CONFIGURED`
- **WHEN** UI отображает ошибку
- **THEN** UI показывает actionable подсказку, где исправить проблему (минимум: `/databases` и `connection.offline.*`)

### Requirement: Preview для `ibcmd_cli` требует выбранные таргеты (или базу-пример)
Система ДОЛЖНА (SHALL) делать preview execution plan для `ibcmd_cli` с учётом effective connection, который зависит от профиля выбранных баз.

#### Scenario: Preview без таргетов не считается достоверным
- **GIVEN** staff открывает редактор action catalog
- **AND** выбран action `executor.kind=ibcmd_cli`
- **WHEN** staff пытается сделать Preview без указания базы/таргетов
- **THEN** UI сообщает, что для Preview нужно выбрать базу (или набор баз), так как connection резолвится per database

### Requirement: Safe params template UX в Action Catalog
Система ДОЛЖНА (SHALL) предоставлять schema-driven params template для `executor.params` в Action Catalog с fail-safe поведением, исключающим неожиданное auto-fill/overwrite.

#### Scenario: Schema panel collapsible и не перегружает модалку
- **WHEN** staff пользователь выбирает `driver` и `command_id` в guided editor
- **THEN** UI показывает schema panel параметров команды из `params_by_name`
- **AND** schema panel является collapsible и по умолчанию не раскрыт
- **AND** UI показывает число параметров (после фильтрации disabled/connection params)

#### Scenario: Auto-fill только для pristine params и пустого значения
- **GIVEN** staff открыл модалку создания action
- **AND** `executor.kind` из `{ibcmd_cli, designer_cli}`
- **AND** поле `params` пустое или равно `{}` (после trim/parse)
- **AND** пользователь ещё не редактировал `params` в текущей сессии модалки (pristine)
- **WHEN** staff выбирает `command_id`
- **THEN** UI может auto-fill `params` шаблоном из schema
- **AND** auto-fill не выполняется более 1 раза для одного `command_id` в рамках сессии модалки

#### Scenario: Смена command_id не сбрасывает user-edited состояние
- **GIVEN** staff пользователь вручную редактировал `params` (не pristine)
- **WHEN** staff меняет `command_id` на другой
- **THEN** UI НЕ должен auto-fill `params` автоматически
- **AND** UI предлагает кнопку “Insert params template” для явного действия пользователя

#### Scenario: Overwrite только с явным подтверждением
- **GIVEN** в `params` уже есть непустой JSON (не `{}`)
- **WHEN** staff нажимает “Insert params template”
- **THEN** UI показывает confirm overwrite
- **AND** без подтверждения исходный JSON не изменяется

### Requirement: Guided/Raw JSON редактор params в Action Catalog
Система ДОЛЖНА (SHALL) в modal редактора Action Catalog предоставлять интерактивный Guided‑редактор `executor.params` по schema выбранной команды, сохраняя возможность редактирования в Raw JSON.

#### Scenario: Guided режим по умолчанию
- **GIVEN** staff открывает modal Add/Edit action
- **WHEN** modal отображается
- **THEN** секция `params` по умолчанию в режиме Guided

#### Scenario: Guided режим использует schema params_by_name
- **GIVEN** выбран `executor.kind` из `{ibcmd_cli, designer_cli}`
- **AND** выбран `driver` и `command_id`
- **WHEN** пользователь открывает секцию `params` в Guided режиме
- **THEN** UI отображает поля для параметров из `params_by_name` (после фильтрации disabled + ibcmd connection params)
- **AND** UI позволяет задать значения этих параметров интерактивно

#### Scenario: Raw JSON остаётся доступным
- **WHEN** пользователь переключается на Raw JSON
- **THEN** UI показывает JSON textarea для `params`

#### Scenario: Сохранение кастомных ключей при Guided редактировании
- **GIVEN** в `params` присутствуют ключи, отсутствующие в schema (`params_by_name`)
- **WHEN** пользователь изменяет значения schema‑параметров в Guided режиме
- **THEN** кастомные ключи сохраняются (не удаляются) при сохранении action

#### Scenario: Layout выбора команды не схлопывается
- **WHEN** staff выбирает `driver` и `command_id`
- **THEN** UI обеспечивает стабильную ширину Select (без схлопывания до “узкого” состояния), достаточную для чтения `command_id`

