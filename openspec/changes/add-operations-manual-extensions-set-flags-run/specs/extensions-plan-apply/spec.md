## ADDED Requirements
### Requirement: `extensions.set_flags` plan/apply SHALL поддерживать ручной канал запуска из `/operations`
Система ДОЛЖНА (SHALL) принимать ручные вызовы `extensions.set_flags` из `/operations` через тот же `POST /api/v2/extensions/plan/` и `POST /api/v2/extensions/apply/` pipeline, что и другие каналы.

#### Scenario: Manual run из `/operations` использует тот же pipeline
- **GIVEN** оператор запускает ручную операцию `extensions.set_flags` из `/operations`
- **WHEN** UI вызывает `POST /api/v2/extensions/plan/`, а затем `POST /api/v2/extensions/apply/`
- **THEN** backend применяет те же drift/precondition/validation правила
- **AND** создаётся обычная операция в monitor (`/operations`) без обходных execution путей

### Requirement: Ручной канал `/operations` SHALL предоставлять preview до apply
Система ДОЛЖНА (SHALL) предоставлять preview (`execution_plan` + `bindings`) при ручном запуске `extensions.set_flags` из `/operations` до создания apply operation.

#### Scenario: Оператор видит preview и provenance перед подтверждением
- **GIVEN** оператор заполнил manual форму в `/operations`
- **WHEN** UI вызывает `POST /api/v2/extensions/plan/`
- **THEN** backend возвращает `execution_plan` и `bindings`
- **AND** apply запускается только после явного подтверждения оператора
