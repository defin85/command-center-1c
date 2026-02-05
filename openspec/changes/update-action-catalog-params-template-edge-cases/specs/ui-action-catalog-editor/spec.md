## ADDED Requirements

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

