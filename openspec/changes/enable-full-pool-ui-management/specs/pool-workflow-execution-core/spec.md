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

### Requirement: Create-run API MUST удалить source_hash из публичного контракта
Система ДОЛЖНА (SHALL) удалить поле `source_hash` из публичного контракта `POST /api/v2/pools/runs/` и из формулы idempotency key.

Система ДОЛЖНА (SHALL) сохранять читаемость historical run после удаления `source_hash` из create-path.

#### Scenario: Запрос create-run с source_hash отклоняется как невалидный контракт
- **GIVEN** клиент отправляет create-run с полем `source_hash`
- **WHEN** backend валидирует payload по обновлённому контракту
- **THEN** возвращается `400` с ошибкой валидации неизвестного/запрещённого поля
- **AND** run не создаётся

#### Scenario: Historical run остаётся читаемым после удаления source_hash из create-path
- **GIVEN** в системе есть historical run, созданный до обновления контракта
- **WHEN** клиент запрашивает список или детали run
- **THEN** API возвращает run без ошибки десериализации
- **AND** данные run доступны для UI мониторинга и safe-flow операций

## MODIFIED Requirements
### Requirement: Migration MUST сохранять historical runs и идемпотентность
Система ДОЛЖНА (SHALL) выполнить миграцию так, чтобы historical pool runs оставались читаемыми, а create-run idempotency использовал canonicalized `run_input` fingerprint вместо legacy `source_hash`.

Система ДОЛЖНА (SHALL) иметь rollback criteria и rollback-path для возврата execution routing без потери связей run/provenance.

#### Scenario: Идемпотентный ключ после миграции вычисляется из canonicalized run_input
- **GIVEN** клиент отправляет create-run с `run_input`
- **WHEN** backend вычисляет idempotency fingerprint
- **THEN** fingerprint зависит от canonicalized `run_input` и контекста запуска (`pool_id`, `period`, `direction`)
- **AND** поле `source_hash` не участвует в вычислении
