## MODIFIED Requirements

### Requirement: Обзор расширений по всем базам
Система ДОЛЖНА (SHALL) предоставить экран `/extensions`, который показывает агрегированную таблицу расширений по доступным пользователю базам.

#### Scenario: UI позволяет selective apply flags policy
- **WHEN** пользователь открывает drawer расширения `X` на `/extensions` и нажимает `Apply flags policy`
- **THEN** UI отображает форму из 3 строк (`active`, `safe_mode`, `unsafe_action_protection`), где каждая строка имеет:
  - checkbox “Apply this flag”
  - switch “Value” (disabled, если checkbox выключен)
- **AND** пользователь может подтвердить apply, выбрав подмножество флагов

