## ADDED Requirements

### Requirement: Guided/Raw JSON редактор params в Action Catalog
Система ДОЛЖНА (SHALL) в guided modal редактора Action Catalog предоставлять интерактивный Guided‑редактор `executor.params` по command schema, с fallback на Raw JSON.

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
- **THEN** UI обеспечивает стабильную ширину Select (без схлопывания до “узкого” состояния), достаточную для чтения command_id

