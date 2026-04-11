## MODIFIED Requirements

### Requirement: Pool master-data workspace MUST предоставлять операторский Bootstrap Import from IB wizard
Система ДОЛЖНА (SHALL) в `/pools/master-data` предоставить отдельную рабочую зону `Bootstrap Import` для первичного импорта canonical master-data из ИБ.

Зона ДОЛЖНА (SHALL) поддерживать:
- single-database bootstrap import;
- multi-database batch collection launch для `cluster_all` и `database_set`.

Wizard/launcher ДОЛЖЕН (SHALL) как минимум поддерживать шаги:
1. выбор target scope и entity scope;
2. preflight;
3. dry-run summary;
4. execute.

#### Scenario: Оператор запускает bootstrap collection по всем ИБ кластера
- **GIVEN** пользователь открыл `/pools/master-data` в активном tenant context
- **WHEN** он переходит в `Bootstrap Import`, выбирает `cluster_all`, конкретный кластер и entity scope
- **THEN** система отображает batch bootstrap launcher с canonical staged lifecycle
- **AND** запуск выполняется через канонический v2 API bootstrap collection

#### Scenario: Оператор запускает bootstrap import по выбранному набору ИБ
- **GIVEN** пользователь открыл `Bootstrap Import`
- **WHEN** он выбирает `database_set`, несколько конкретных ИБ и entity scope
- **THEN** UI создаёт batch collection request только для выбранных ИБ
- **AND** operator detail показывает immutable snapshot выбранных targets

### Requirement: UI MUST enforce preflight/dry-run gate before execute
Система ДОЛЖНА (SHALL) блокировать кнопку execute, пока не завершены preflight и dry-run выбранного bootstrap scope.

Система НЕ ДОЛЖНА (SHALL NOT) отправлять execute-запрос при fail-результате preflight/dry-run.

Это требование распространяется как на single-database bootstrap import, так и на multi-database batch collection.

#### Scenario: Провал aggregate preflight блокирует batch execute
- **GIVEN** batch preflight вернул fail-closed ошибки для выбранного target scope
- **WHEN** оператор находится на шаге запуска
- **THEN** execute action недоступен
- **AND** UI показывает operator-facing причину блокировки без очистки уже выбранного scope

## ADDED Requirements

### Requirement: Bootstrap Import zone MUST показывать batch collection history и per-database detail
Система ДОЛЖНА (SHALL) в `Bootstrap Import` зоне показывать history для batch collection requests.

History/detail ДОЛЖНЫ (SHALL) включать как минимум:
- `created_at`, `requested_by`, `target_mode`, target summary;
- aggregate counters `scheduled/coalesced/skipped/failed/completed`;
- per-database outcomes и ссылку на child bootstrap job, если он существует;
- handoff в child job detail, когда оператору нужно разобрать конкретную ИБ.

#### Scenario: Оператор открывает detail batch collection и видит прогресс по базам
- **GIVEN** batch collection request запущен по нескольким ИБ
- **WHEN** оператор открывает detail этого request
- **THEN** UI показывает aggregate counters и список выбранных баз с outcome
- **AND** оператор может перейти к child bootstrap job для конкретной базы

### Requirement: Batch launcher UI MUST сохранять operator input при create/preflight/dry-run errors
Система ДОЛЖНА (SHALL) сохранять выбранные `target_mode`, cluster/database selection и `entity_scope`, если batch collection create/preflight/dry-run завершился Problem Details ошибкой.

Система НЕ ДОЛЖНА (SHALL NOT) очищать введённый scope после validation/access failure.

#### Scenario: Ошибка batch create не сбрасывает выбранный scope
- **GIVEN** оператор заполнил batch bootstrap launcher
- **WHEN** API отклоняет create request из-за validation или access error
- **THEN** UI показывает operator-facing ошибку
- **AND** ранее выбранные cluster/database targets и entity scope остаются в форме для повторной попытки
