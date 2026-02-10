## MODIFIED Requirements
### Requirement: Обзор расширений по всем базам
Система ДОЛЖНА (SHALL) использовать `/extensions` как templates-first экран для запуска и управления `extensions.*` операциями.

В рамках этого change runtime path через `action_catalog` для `extensions.*` НЕ ДОЛЖЕН (SHALL NOT) использоваться внутри `/extensions`.

#### Scenario: `/extensions` запускает `extensions.set_flags` через template-based path
- **GIVEN** пользователь работает в `/extensions`
- **WHEN** выбирает template, заполняет runtime input и подтверждает запуск
- **THEN** UI вызывает единый `extensions plan/apply` pipeline
- **AND** backend резолвит executor через `template_id`

#### Scenario: Action-catalog runtime controls отсутствуют в `/extensions`
- **GIVEN** пользователь находится в `/extensions`
- **WHEN** открывает controls запуска `extensions.*`
- **THEN** UI не использует runtime actions из `ui/action-catalog`
- **AND** экран показывает только templates-first execution controls
