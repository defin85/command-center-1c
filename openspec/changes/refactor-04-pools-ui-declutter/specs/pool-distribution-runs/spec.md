## MODIFIED Requirements
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

## ADDED Requirements
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
