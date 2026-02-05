## MODIFIED Requirements

### Requirement: Plan set_flags принимает apply_mask
Система ДОЛЖНА (SHALL) принимать `apply_mask` в `POST /api/v2/extensions/plan/` для `capability="extensions.set_flags"`.

#### Scenario: apply_mask может быть задан preset-ом action
- **GIVEN** `POST /api/v2/extensions/plan/` вызывается для `extensions.set_flags`
- **AND** `apply_mask` отсутствует в request
- **AND** выбранный action содержит preset mask (`executor.fixed.apply_mask`)
- **THEN** effective `apply_mask` берётся из action preset

## ADDED Requirements

### Requirement: Детерминированный выбор action через action_id
Система ДОЛЖНА (SHALL) поддерживать выбор конкретного extensions action для plan/apply через `action_id`, а не только через `capability`.

#### Scenario: action_id выбирает конкретный action при нескольких candidates по capability
- **GIVEN** в `ui.action_catalog` есть 3 actions с `capability="extensions.set_flags"`
- **WHEN** UI делает `POST /api/v2/extensions/plan/` с `action_id`, указывающим на один из них
- **THEN** backend строит plan на основе executor выбранного action

#### Scenario: capability без action_id возвращает ambiguity
- **GIVEN** в `ui.action_catalog` есть 2+ actions с `capability="extensions.set_flags"`
- **WHEN** UI делает `POST /api/v2/extensions/plan/` без `action_id`, но с `capability="extensions.set_flags"`
- **THEN** backend возвращает `HTTP 400` с кодом ошибки ambiguity (например `AMBIGUOUS_ACTION`)

