# pool-distribution-runs Specification

## Purpose
TBD - created by archiving change add-intercompany-pool-distribution-module. Update Purpose after archive.
## Requirements
### Requirement: Distribution runs MUST поддерживать фиксированный lifecycle и режимы безопасности
Система ДОЛЖНА (SHALL) поддерживать lifecycle run в состояниях:
- `draft -> validated -> publishing -> partial_success|published|failed`.

В рамках этого change данный lifecycle фиксируется как внешний доменный контракт facade; источник исполнения и проекции статусов определяется unified runtime change.

Система ДОЛЖНА (SHALL) поддерживать режимы:
- `safe`: публикация после проверок и явного решения пользователя,
- `unsafe`: публикация без этапа ручного подтверждения.

#### Scenario: Safe run требует явного решения перед публикацией
- **GIVEN** run запущен в режиме `safe`
- **WHEN** завершена валидация и сформированы предупреждения/ошибки данных
- **THEN** переход к публикации выполняется только после явного подтверждения пользователя
- **AND** решение фиксируется в audit trail

### Requirement: Top-down algorithm MUST быть детерминируемым и учитывать ограничения рёбер
Система ДОЛЖНА (SHALL) выполнять top-down распределение с использованием ограничений ребра (`weight`, `min_amount`, `max_amount`) и `seed`.

При округлении денежный остаток ДОЛЖЕН (SHALL) переноситься на последнего child узла.

#### Scenario: Повторный run с тем же seed даёт те же суммы
- **GIVEN** одинаковые входные данные, период, структура пула и `seed`
- **WHEN** пользователь запускает top-down run повторно
- **THEN** детальные суммы распределения совпадают
- **AND** итог по узлам сходится строго

### Requirement: Bottom-up import MUST использовать файл как источник истины
Система ДОЛЖНА (SHALL) в bottom-up режиме воспринимать входной файл как источник фактических продаж и агрегировать суммы снизу-вверх до root.

Строки с неизвестным ИНН ДОЛЖНЫ (SHALL) фиксироваться как диагностические ошибки, но run НЕ ДОЛЖЕН (SHALL NOT) автоматически останавливаться.

#### Scenario: Неизвестный ИНН фиксируется без автоматического стопа run
- **GIVEN** во входном XLSX есть строка с ИНН, отсутствующим в активной версии пула
- **WHEN** выполняется импорт
- **THEN** строка помечается ошибкой в диагностике
- **AND** run продолжает обработку остальных строк

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

### Requirement: Reporting MUST предоставлять сводный и детализированный баланс
Система ДОЛЖНА (SHALL) формировать:
- сводный отчёт по узлам/уровням пула,
- детальный отчёт по парам продажа/покупка.

Система ДОЛЖНА (SHALL) рассчитывать строгую проверку сходимости сумм по выбранному периоду и отображать диагностику при разбеге.

#### Scenario: Пользователь получает два представления отчёта
- **WHEN** пользователь открывает отчёт run
- **THEN** доступны агрегатный и детализированный режимы
- **AND** отчёт содержит явный статус сходимости сумм

### Requirement: Module MUST предоставить внешние API для запуска и дозаписи
Система ДОЛЖНА (SHALL) предоставить внешние endpoint'ы для:
- запуска run,
- чтения статуса/деталей run,
- повторной дозаписи failed-частей.

Фактическая реализация execution-path для этих endpoint'ов ДОЛЖНА (SHALL) быть перенесена и зафиксирована в `refactor-unify-pools-workflow-execution-core`.

#### Scenario: Внешний клиент выполняет дозапись failed-частей
- **GIVEN** run завершился в `partial_success`
- **WHEN** внешний клиент вызывает endpoint retry
- **THEN** система запускает повторную публикацию только для failed-целей
- **AND** обновляет статусы публикации в том же run

### Requirement: Pool runs UI MUST запускать распределение с direction-specific входными данными
Система ДОЛЖНА (SHALL) предоставлять на `/pools/runs` форму запуска run, которая запрашивает и валидирует direction-specific входные данные.

Для `top_down` система ДОЛЖНА (SHALL) требовать ввод стартовой суммы распределения пользователем.

Для `bottom_up` система ДОЛЖНА (SHALL) поддерживать выбор шаблона импорта и ввод/загрузку источника данных из UI.

#### Scenario: Top-down run запускается из UI со стартовой суммой
- **GIVEN** оператор выбрал пул и направление `top_down`
- **WHEN** оператор вводит стартовую сумму и отправляет форму запуска
- **THEN** run создаётся через `/api/v2/pools/runs/` с direction-specific входными данными
- **AND** запуск не требует ручного формирования payload во внешнем API-клиенте

#### Scenario: UI create-run payload не содержит source_hash
- **GIVEN** оператор запускает run через `/pools/runs`
- **WHEN** UI формирует payload для `POST /api/v2/pools/runs/`
- **THEN** payload содержит `run_input` и не содержит `source_hash`
- **AND** idempotency определяется содержимым `run_input`

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

Система ДОЛЖНА (SHALL) структурировать интерфейс `/pools/runs` как stage-based workflow (create, inspect, safe actions, retry), чтобы каждый этап имел отдельный фокус и не перегружал пользователя нерелевантными controls.

Система ДОЛЖНА (SHALL) сохранять единый контекст выбранного `run` при переходе между этапами, без повторного ручного выбора на каждом шаге.

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

#### Scenario: UI корректно отображает ошибки create-run в Problem Details формате
- **GIVEN** backend отклонил create-run запрос
- **WHEN** ответ возвращён как `application/problem+json`
- **THEN** UI показывает `detail` оператору
- **AND** использует machine-readable `code` для привязки к конкретному полю/действию

#### Scenario: Оператор последовательно проходит этапы без перегруженного единого полотна
- **GIVEN** оператор создал run на этапе `create`
- **WHEN** оператор переходит к этапам `inspect` и `safe/retry`
- **THEN** интерфейс показывает только controls текущего этапа
- **AND** выбранный run context сохраняется между этапами

### Requirement: Pool run distribution MUST гарантировать полное покрытие активной цепочки организаций
Система ДОЛЖНА (SHALL) рассчитывать распределение для create-run path на основе активной версии DAG topology (`effective_from/effective_to`) за период run.

Система ДОЛЖНА (SHALL) обеспечивать, что распределение покрывает активную цепочку организаций, участвующую в публикации, и не оставляет нераспределённый денежный остаток вне допуска денежной точности.

#### Scenario: Top-down распределение полностью покрывает многоуровневую цепочку
- **GIVEN** активный граф пула содержит многоуровневую цепочку `root -> level1 -> level2`
- **AND** run запущен в `top_down` со стартовой суммой
- **WHEN** выполняется шаг `distribution_calculation.top_down`
- **THEN** суммы распределяются по рёбрам с учётом `weight/min_amount/max_amount`
- **AND** итоговая сумма по целевым узлам совпадает с исходной суммой в пределах денежной точности
- **AND** в runtime artifact нет gaps покрытия для активных publish-target узлов

#### Scenario: Bottom-up распределение сходится к root без потери входной суммы
- **GIVEN** run запущен в `bottom_up` и содержит валидный source payload
- **WHEN** выполняется шаг `distribution_calculation.bottom_up`
- **THEN** суммы агрегируются по активной topology до root
- **AND** `root_total` совпадает с суммой принятых входных строк в пределах денежной точности
- **AND** при несходимости run маркируется fail-closed до шага публикации

### Requirement: Create-run publication payload MUST строиться из distribution artifacts
Система ДОЛЖНА (SHALL) формировать `pool_runtime_publication_payload.documents_by_database` для create-run path из канонического runtime distribution artifact.

Система НЕ ДОЛЖНА (SHALL NOT) использовать raw `run_input` как authoritative источник итогового publication payload, если рассчитанный distribution artifact уже сформирован.

Система ДОЛЖНА (SHALL) принимать `run_input.documents_by_database` в create-run только как `provenance-only` вход для аудита/диагностики и не использовать его для переопределения расчётного payload.

#### Scenario: Runtime игнорирует raw publication payload при наличии расчётного artifact
- **GIVEN** create-run запрос содержит `run_input` с полем `documents_by_database`
- **AND** шаги распределения успешно сформировали канонический distribution artifact
- **WHEN** runtime формирует payload для `pool.publication_odata`
- **THEN** используется payload из distribution artifact
- **AND** raw `run_input.documents_by_database` не может обойти инварианты покрытия и сходимости

#### Scenario: Raw create-run payload сохраняется только как provenance
- **GIVEN** create-run запрос содержит `run_input.documents_by_database`
- **AND** distribution шаги завершились успешно с `distribution_artifact.v1`
- **WHEN** run сохраняется и публикуется
- **THEN** raw payload сохраняется только в provenance/diagnostics контексте
- **AND** финальный publication payload формируется исключительно из `distribution_artifact.v1`

### Requirement: Pool runs diagnostics UI MUST использовать progressive disclosure
Система ДОЛЖНА (SHALL) показывать тяжёлые диагностические блоки (`Run Input`, `Validation Summary`, `Publication Summary`, `Step Diagnostics`) по запросу оператора, а не в полном виде по умолчанию.

Система ДОЛЖНА (SHALL) сохранять полноту диагностической информации и доступ к ней в один шаг из контекста выбранного run.

#### Scenario: Диагностика раскрывается по требованию оператора
- **GIVEN** оператор анализирует run в разделе inspect
- **WHEN** оператор включает отображение diagnostics
- **THEN** UI раскрывает детальные JSON-блоки
- **AND** без включения diagnostics базовый экран остаётся компактным и читаемым

#### Scenario: Retry-form остаётся доступной без визуальной конкуренции с diagnostics
- **GIVEN** оператор находится на этапе retry failed targets
- **WHEN** diagnostics блоки не требуются для текущего действия
- **THEN** retry form отображается как основной фокус экрана
- **AND** diagnostic секции не отвлекают от завершения retry операции

