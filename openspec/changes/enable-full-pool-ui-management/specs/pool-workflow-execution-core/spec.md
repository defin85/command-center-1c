## ADDED Requirements
### Requirement: Pool run create contract MUST использовать структурированный run_input как source-of-truth
Система ДОЛЖНА (SHALL) расширить контракт создания run структурированным полем `run_input` и валидировать его по направлению исполнения.

Система ДОЛЖНА (SHALL) сохранять `run_input` в состоянии run и передавать его в workflow `input_context` для шагов подготовки и расчёта распределения.

#### Scenario: Top-down run_input передаётся в workflow execution context
- **GIVEN** run создаётся с направлением `top_down` и стартовой суммой в `run_input`
- **WHEN** создаётся связанный workflow run
- **THEN** `run_input` доступен в `input_context` workflow
- **AND** шаги `prepare_input` и `distribution_calculation` используют его как входные данные

#### Scenario: Неполный run_input отклоняется на create-run
- **GIVEN** клиент отправляет `direction=top_down` без обязательных полей `run_input`
- **WHEN** backend валидирует запрос создания run
- **THEN** возвращается `400` с ошибкой валидации
- **AND** run не создаётся

### Requirement: Pool run idempotency fingerprint MUST учитывать canonicalized run_input
Система ДОЛЖНА (SHALL) включать canonicalized `run_input` в вычисление idempotency fingerprint для create/upsert run.

Система НЕ ДОЛЖНА (SHALL NOT) переиспользовать один и тот же run, если direction-specific входные данные различаются.

Канонизация `run_input` ДОЛЖНА (SHALL) быть детерминированной: semantically-equivalent payload должен давать одинаковый fingerprint независимо от порядка ключей и форматирования JSON.

#### Scenario: Изменение стартовой суммы создаёт новый idempotency fingerprint
- **GIVEN** два запроса create-run с одинаковыми `pool_id`, `period`, `direction`
- **AND** стартовая сумма в `run_input` различается
- **WHEN** backend вычисляет idempotency fingerprint
- **THEN** fingerprint различается
- **AND** второй запрос не переиспользует run первого запуска

#### Scenario: Повтор того же run_input переиспользует существующий run
- **GIVEN** create-run уже выполнен для конкретного canonicalized `run_input`
- **WHEN** клиент повторяет create-run с теми же полями
- **THEN** система возвращает существующий run по idempotency
- **AND** дубликат run не создаётся

### Requirement: Переход на run_input MUST быть backward-compatible для существующих run и legacy клиентов
Система ДОЛЖНА (SHALL) сохранять читаемость historical run, созданных до появления `run_input`.

На переходном этапе система ДОЛЖНА (SHALL) принимать legacy-путь с `source_hash` для совместимости старых клиентов, но `run_input` остаётся каноническим источником для нового create-run контракта.

#### Scenario: Historical run без run_input корректно возвращается в API
- **GIVEN** в системе есть run, созданный до введения поля `run_input`
- **WHEN** клиент запрашивает список или детали run
- **THEN** API возвращает run без ошибки десериализации
- **AND** данные run доступны для UI мониторинга и safe-flow операций

#### Scenario: Legacy create-run запрос не ломает API в переходный период
- **GIVEN** клиент отправляет create-run по legacy-контракту без `run_input`
- **WHEN** backend обрабатывает запрос в режиме совместимости
- **THEN** запрос обрабатывается без `5xx` и с детерминированным idempotency поведением
- **AND** поведение documented как временно совместимое до завершения миграции клиентов
