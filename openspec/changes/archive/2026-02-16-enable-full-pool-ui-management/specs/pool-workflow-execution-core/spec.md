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

Профиль canonicalization ДОЛЖЕН (SHALL) включать:
- лексикографическую сортировку ключей объектов;
- сохранение порядка элементов массивов;
- нормализацию денежных значений в fixed-scale decimal string;
- сериализацию без зависимости от whitespace/formatting входного JSON.

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

#### Scenario: Семантически эквивалентный JSON даёт тот же fingerprint
- **GIVEN** два create-run payload с одинаковым смыслом `run_input`, но разным порядком ключей
- **WHEN** backend canonicalizes `run_input`
- **THEN** вычисленный idempotency fingerprint совпадает
- **AND** система не создаёт дублирующий run

### Requirement: Create-run API MUST удалить source_hash из публичного контракта
Система ДОЛЖНА (SHALL) удалить поле `source_hash` из публичного контракта `POST /api/v2/pools/runs/` и из формулы idempotency key.

Система ДОЛЖНА (SHALL) сохранять читаемость historical run после удаления `source_hash` из create-path.

Публичный read-контракт run ДОЛЖЕН (SHALL) возвращать:
- `run_input` как nullable поле;
- `input_contract_version` (`run_input_v1` или `legacy_pre_run_input`);
- без публичного поля `source_hash`.

#### Scenario: Запрос create-run с source_hash отклоняется как невалидный контракт
- **GIVEN** клиент отправляет create-run с полем `source_hash`
- **WHEN** backend валидирует payload по обновлённому контракту
- **THEN** возвращается `400` с ошибкой валидации неизвестного/запрещённого поля
- **AND** run не создаётся

#### Scenario: Historical run остаётся читаемым после удаления source_hash из create-path
- **GIVEN** в системе есть historical run, созданный до обновления контракта
- **WHEN** клиент запрашивает список или детали run
- **THEN** API возвращает run без ошибки десериализации с `run_input=null`
- **AND** поле `input_contract_version` равно `legacy_pre_run_input`
- **AND** данные run доступны для UI мониторинга и safe-flow операций

### Requirement: Create-run validation errors MUST использовать Problem Details контракт
Система ДОЛЖНА (SHALL) возвращать ошибки валидации create-run в формате `application/problem+json`.

Problem payload ДОЛЖЕН (SHALL) содержать `type`, `title`, `status`, `detail`, `code`.

#### Scenario: source_hash в create-run возвращает Problem Details ошибку
- **GIVEN** клиент отправляет create-run с запрещённым полем `source_hash`
- **WHEN** backend формирует ответ об ошибке
- **THEN** response content-type равен `application/problem+json`
- **AND** payload содержит `status=400` и machine-readable `code`

## MODIFIED Requirements
### Requirement: Migration MUST сохранять historical runs и идемпотентность
Система ДОЛЖНА (SHALL) выполнить миграцию так, чтобы historical pool runs оставались читаемыми, а create-run idempotency использовал canonicalized `run_input` fingerprint вместо legacy `source_hash`.

Система ДОЛЖНА (SHALL) иметь rollback criteria и rollback-path для возврата execution routing без потери связей run/provenance.

Система ДОЛЖНА (SHALL) сопровождать breaking удаление `source_hash` обновлением OpenAPI-примеров и release notes для интеграторов.

#### Scenario: Идемпотентный ключ после миграции вычисляется из canonicalized run_input
- **GIVEN** клиент отправляет create-run с `run_input`
- **WHEN** backend вычисляет idempotency fingerprint
- **THEN** fingerprint зависит от canonicalized `run_input` и контекста запуска (`pool_id`, `period`, `direction`)
- **AND** поле `source_hash` не участвует в вычислении

#### Scenario: Breaking cutover документирован для интеграторов
- **GIVEN** система переходит на контракт без `source_hash`
- **WHEN** публикуется новая версия OpenAPI
- **THEN** release notes содержат migration guidance и обновлённые примеры create-run payload
- **AND** интеграторы могут перейти на `run_input` без двусмысленности контракта
