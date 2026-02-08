# ui-action-catalog-editor Specification

## Purpose
TBD - created by archiving change add-ui-action-catalog-editor. Update Purpose after archive.
## Requirements
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

### Requirement: Guided editor + Raw JSON toggle
Система ДОЛЖНА (SHALL) поддерживать два режима редактирования: guided UI и Raw JSON, с возможностью переключения.

#### Scenario: Переключение режимов
- **WHEN** staff пользователь переключает guided ↔ raw
- **THEN** изменения сохраняются в рамках текущей сессии редактирования и не теряются без явного Save

### Requirement: Поддержка executor kinds
Система ДОЛЖНА (SHALL) поддерживать в editor-е executor kinds `ibcmd_cli`, `designer_cli` и `workflow`, а capability-специфичные поля НЕ ДОЛЖНЫ (SHALL NOT) масштабироваться через хардкод условных веток в UI.

Для canonical kinds UI НЕ ДОЛЖЕН (SHALL NOT) требовать отдельный ручной выбор `driver`; `driver` ДОЛЖЕН (SHALL) определяться из `executor.kind`:
- `ibcmd_cli -> ibcmd`
- `designer_cli -> cli`
- `workflow -> driver не применяется`

#### Scenario: `ibcmd_cli` использует ibcmd catalog без отдельного driver select
- **WHEN** staff выбирает `executor.kind=ibcmd_cli`
- **THEN** editor показывает команды из `ibcmd` catalog
- **AND** UI не показывает отдельное обязательное поле `driver`

#### Scenario: `designer_cli` использует cli catalog без отдельного driver select
- **WHEN** staff выбирает `executor.kind=designer_cli`
- **THEN** editor показывает команды из `cli` catalog
- **AND** UI не показывает отдельное обязательное поле `driver`

#### Scenario: `workflow` скрывает command fields
- **WHEN** staff выбирает `executor.kind=workflow`
- **THEN** editor показывает `workflow_id`
- **AND** поля `driver/command_id` не используются и не сериализуются как обязательные

### Requirement: Save с серверной валидацией и отображением ошибок
Система ДОЛЖНА (SHALL) сохранять изменения через backend и показывать ошибки валидации пользователю; UI НЕ ДОЛЖЕН (SHALL NOT) вводить дополнительные ограничения, которые не требуются backend (например, блокировать дубли reserved capability), если backend допускает такие конфигурации.

#### Scenario: UI не блокирует сохранение из-за duplicate reserved capability
- **GIVEN** staff добавляет второй action с `capability="extensions.set_flags"`
- **WHEN** staff нажимает Save
- **THEN** UI отправляет payload на backend и показывает результат
- **AND** если backend вернул ошибки, UI показывает их с путями вида `extensions.actions[i]...`

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

### Requirement: Staff-only endpoint для Action Catalog editor hints
Система ДОЛЖНА (SHALL) предоставить staff-only endpoint, который возвращает UI hints для capability (минимум: `executor.fixed.*`) в виде JSON Schema + uiSchema.

#### Scenario: Hints endpoint доступен только staff
- **WHEN** non-staff вызывает hints endpoint
- **THEN** доступ запрещён (403)

#### Scenario: Hints содержат fixed schema для extensions.set_flags
- **WHEN** staff вызывает hints endpoint
- **THEN** ответ содержит capability `extensions.set_flags` с описанием `fixed.apply_mask`

### Requirement: Editor MUST записывать action exposures в unified persistent store
Система ДОЛЖНА (SHALL) сохранять изменения editor-а в unified exposure-модель (`surface="action_catalog"`), а не в isolated legacy JSON источник.

#### Scenario: Save action обновляет unified exposure
- **GIVEN** staff сохраняет action из editor modal
- **WHEN** backend принимает payload
- **THEN** обновляется/создаётся соответствующий action exposure
- **AND** изменения доступны в runtime только через unified storage path

### Requirement: Editor MUST использовать shared command-config contract с Templates UI
Система ДОЛЖНА (SHALL) использовать единый frontend editor pipeline (shared component + adapter + serializer + validation mapping) для surfaces `template` и `action_catalog` в одном UI, чтобы исключить дублирование логики и расхождения UX.

#### Scenario: Единый modal editor используется в двух surfaces
- **GIVEN** staff открывает `/templates`
- **WHEN** создаёт/редактирует exposure в `template` и в `action_catalog`
- **THEN** используется один и тот же modal editor shell и одна state-модель формы
- **AND** различаются только surface-specific поля/ограничения

#### Scenario: Одинаковая command-конфигурация сериализуется одинаково в двух surfaces
- **GIVEN** оператор задаёт одинаковые `executor.kind`, `command_id`, `params`, `additional_args`, `stdin`, safety-поля
- **WHEN** сохраняет exposure как `template` и как `action_catalog`
- **THEN** serialized execution payload в unified definition совпадает по контракту
- **AND** не возникает surface-specific расхождения executor shape

### Requirement: Editor hints MUST включать `target_binding` schema для `extensions.set_flags`
Система ДОЛЖНА (SHALL) возвращать в editor hints capability schema для `target_binding`, чтобы UI строил guided-поле binding без хардкода структуры.

#### Scenario: Hints содержат `target_binding.extension_name_param`
- **GIVEN** staff открывает editor для action catalog
- **WHEN** UI получает hints для capability `extensions.set_flags`
- **THEN** hints содержит schema для `target_binding.extension_name_param`
- **AND** UI отображает guided-поле для настройки binding

### Requirement: Editor MUST показывать migration/validation diagnostics для unified exposure
Система ДОЛЖНА (SHALL) показывать оператору ошибки валидации unified exposure по точному пути поля и не выполнять silent fallback.

#### Scenario: Ошибка в `target_binding` отображается по пути unified поля
- **GIVEN** action `extensions.set_flags` сохранён с невалидным binding
- **WHEN** backend возвращает validation error
- **THEN** UI показывает ошибку по пути до binding-поля
- **AND** UI не выполняет автозаполнение/автокоррекцию без явного действия оператора

