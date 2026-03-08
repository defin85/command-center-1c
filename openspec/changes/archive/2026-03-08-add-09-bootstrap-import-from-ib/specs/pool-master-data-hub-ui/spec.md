## ADDED Requirements
### Requirement: Pool master-data workspace MUST предоставлять операторский Bootstrap Import from IB wizard
Система ДОЛЖНА (SHALL) в `/pools/master-data` предоставить отдельную рабочую зону `Bootstrap Import` для первичного импорта canonical master-data из выбранной ИБ.

Wizard ДОЛЖЕН (SHALL) как минимум поддерживать шаги:
1. выбор базы и entity scope;
2. preflight;
3. dry-run summary;
4. execute.

#### Scenario: Оператор запускает bootstrap wizard из master-data workspace
- **GIVEN** пользователь открыл `/pools/master-data` в активном tenant context
- **WHEN** он переходит в рабочую зону `Bootstrap Import`
- **THEN** система отображает wizard с выбором базы и сущностей для импорта
- **AND** запуск выполняется через канонический v2 API bootstrap import

### Requirement: UI MUST enforce preflight/dry-run gate before execute
Система ДОЛЖНА (SHALL) блокировать кнопку execute, пока не завершены preflight и dry-run выбранного bootstrap scope.

Система НЕ ДОЛЖНА (SHALL NOT) отправлять execute-запрос при fail-результате preflight/dry-run.

#### Scenario: Провал preflight блокирует execute в UI
- **GIVEN** preflight вернул fail-closed ошибку для выбранной базы
- **WHEN** оператор находится на шаге запуска
- **THEN** execute action недоступен
- **AND** UI показывает operator-facing причину блокировки

#### Scenario: Dry-run summary обязателен перед запуском execute
- **GIVEN** preflight успешно завершён
- **WHEN** dry-run ещё не выполнен
- **THEN** UI не отправляет execute-запрос
- **AND** оператору предлагается сначала получить dry-run summary

### Requirement: UI MUST показывать прогресс, итог и операторские действия по bootstrap job
Система ДОЛЖНА (SHALL) отображать live status bootstrap job:
- текущий статус;
- прогресс по chunk-ам;
- counters `created/updated/skipped/failed`;
- последний код/деталь ошибки (если есть).

Система ДОЛЖНА (SHALL) поддерживать операторские действия `cancel` и `retry failed chunks` в соответствии со статусом job.

#### Scenario: Частично неуспешный import позволяет retry только failed chunks
- **GIVEN** bootstrap job завершился с частичными ошибками
- **WHEN** оператор запускает `retry failed chunks`
- **THEN** UI отправляет соответствующий API action
- **AND** повторный запуск ограничивается только ранее failed chunk-ами

#### Scenario: UI сохраняет контекст и не теряет ввод при ошибке API
- **GIVEN** bootstrap mutating action завершился ошибкой Problem Details
- **WHEN** UI отображает ошибку
- **THEN** выбранные оператором параметры scope/шаг wizard сохраняются
- **AND** оператор может исправить условия и повторить действие без повторного ввода всех данных

