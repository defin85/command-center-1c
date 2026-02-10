## ADDED Requirements
### Requirement: Workflow-first bulk управление флагами и расширениями
Система ДОЛЖНА (SHALL) использовать workflow-first сценарий как основной способ массового управления расширениями/флагами в `/extensions`.

#### Scenario: Bulk apply запускает workflow rollout
- **GIVEN** пользователь работает в `/extensions` и выбирает массовое применение
- **WHEN** пользователь подтверждает параметры (`flags_values`, `apply_mask`, таргеты, rollout strategy)
- **THEN** UI запускает workflow execution
- **AND** дальнейший прогресс отслеживается через `/operations`

### Requirement: Точечное управление остаётся fallback-режимом
Система ДОЛЖНА (SHALL) сохранять точечное применение (single/small target) как fallback и НЕ ДОЛЖНА (SHALL NOT) позиционировать его как основной путь массового rollout.

#### Scenario: Оператор применяет изменения для одной базы
- **GIVEN** оператору нужен аварийный/индивидуальный случай
- **WHEN** он запускает точечное применение для одной базы
- **THEN** UI использует тот же валидируемый execution pipeline
- **AND** интерфейс явно маркирует режим как fallback/аварийный
