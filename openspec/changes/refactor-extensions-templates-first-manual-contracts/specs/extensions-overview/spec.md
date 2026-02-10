## MODIFIED Requirements
### Requirement: Обзор расширений по всем базам
Система ДОЛЖНА (SHALL) использовать `/extensions` как workflow-first экран массового rollout и мониторинга состояния расширений.

Ручной targeted atomic запуск НЕ ДОЛЖЕН (SHALL NOT) быть основным execution flow внутри `/extensions`; он ДОЛЖЕН (SHALL) выполняться через `/operations` manual contracts.

#### Scenario: `/extensions` запускает workflow-first rollout
- **GIVEN** пользователь работает в `/extensions`
- **WHEN** подтверждает массовое применение для выбранных таргетов
- **THEN** UI запускает workflow-first execution path
- **AND** прогресс отслеживается через `/operations`

#### Scenario: Ручной targeted fallback направляется в `/operations`
- **GIVEN** оператору нужен единичный/аварийный запуск
- **WHEN** он инициирует fallback действие из контекста `/extensions`
- **THEN** UI перенаправляет в contract-driven manual flow `/operations`
- **AND** `/extensions` не выполняет прямой atomic targeted apply

