## ADDED Requirements
### Requirement: Pool runs UI MUST запускать распределение с direction-specific входными данными
Система ДОЛЖНА (SHALL) предоставлять на `/pools/runs` форму запуска run, которая запрашивает и валидирует direction-specific входные данные.

Для `top_down` система ДОЛЖНА (SHALL) требовать ввод стартовой суммы распределения пользователем.

Для `bottom_up` система ДОЛЖНА (SHALL) поддерживать выбор шаблона импорта и ввод/загрузку источника данных из UI.

#### Scenario: Top-down run запускается из UI со стартовой суммой
- **GIVEN** оператор выбрал пул и направление `top_down`
- **WHEN** оператор вводит стартовую сумму и отправляет форму запуска
- **THEN** run создаётся через `/api/v2/pools/runs/` с direction-specific входными данными
- **AND** запуск не требует ручного формирования payload во внешнем API-клиенте

#### Scenario: Top-down стартовая сумма валидируется как денежное поле
- **GIVEN** оператор выбрал направление `top_down`
- **WHEN** оператор вводит отрицательное значение или нечисловой формат стартовой суммы
- **THEN** UI и backend отклоняют значение как невалидное
- **AND** run не создаётся до исправления значения

#### Scenario: Top-down run не запускается без стартовой суммы
- **GIVEN** оператор выбрал направление `top_down`
- **WHEN** поле стартовой суммы не заполнено или невалидно
- **THEN** UI блокирует отправку формы
- **AND** показывает понятную ошибку валидации

#### Scenario: Bottom-up run запускается из UI с выбранным шаблоном и source payload
- **GIVEN** оператор выбрал направление `bottom_up`
- **WHEN** оператор выбирает schema template и задаёт источник входных данных в UI
- **THEN** run запускается через канонический endpoint
- **AND** дальнейший lifecycle доступен в том же UI без ручных API-вызовов

### Requirement: Pool runs UI MUST поддерживать полный операторский lifecycle run
Система ДОЛЖНА (SHALL) предоставлять в `/pools/runs` полный операторский контроль run lifecycle: создание, мониторинг статуса/provenance, safe-команды (`confirm-publication`, `abort-publication`) и retry failed-целей.

#### Scenario: Safe run проходит pre-publish и подтверждается из UI
- **GIVEN** run запущен в режиме `safe`
- **WHEN** run достигает состояния ожидания подтверждения
- **THEN** оператор подтверждает публикацию кнопкой в UI
- **AND** run продолжает публикацию без внешних HTTP-клиентов

#### Scenario: Retry failed выполняется из UI для частично успешного run
- **GIVEN** run находится в `partial_success`
- **WHEN** оператор инициирует retry failed-целей из интерфейса
- **THEN** UI вызывает retry endpoint
- **AND** обновлённый статус run отображается в том же интерфейсе

## MODIFIED Requirements
### Requirement: Run execution MUST быть идемпотентным для одного ключа расчёта
Система ДОЛЖНА (SHALL) использовать idempotency key на основе `pool_id + period + direction + canonicalized(run_input)`.

Система НЕ ДОЛЖНА (SHALL NOT) использовать `source_hash` как часть публичного create-run контракта или как часть новой формулы idempotency key.

Повторный запуск с тем же canonicalized `run_input` ДОЛЖЕН (SHALL) обновлять существующий набор результатов/документов (upsert), а не создавать дубликаты.

#### Scenario: Повторный запуск с тем же run_input не создаёт дубликаты
- **GIVEN** run уже выполнен для конкретного canonicalized `run_input`
- **WHEN** пользователь запускает повторную обработку с тем же `run_input`
- **THEN** существующие записи обновляются
- **AND** новые дубликаты документов и строк распределения не появляются

#### Scenario: Изменение run_input создаёт новый idempotent запуск
- **GIVEN** пользователь повторно запускает run с теми же `pool_id`, `period`, `direction`
- **AND** `run_input` отличается от предыдущего запуска
- **WHEN** система вычисляет idempotency key
- **THEN** key отличается от предыдущего
- **AND** создаётся новый запуск, а не reuse старого
