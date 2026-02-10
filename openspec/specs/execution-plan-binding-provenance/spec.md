# execution-plan-binding-provenance Specification

## Purpose
TBD - created by archiving change add-execution-plan-binding-provenance. Update Purpose after archive.
## Requirements
### Requirement: Execution Plan и Binding Provenance как явные данные
Система ДОЛЖНА (SHALL) формировать структуру Execution Plan и Binding Provenance для каждого запуска действия через executors `ibcmd_cli`, `designer_cli` и `workflow`.

Execution Plan MUST:
- для CLI содержать `argv_masked[]` (и `stdin_masked`, если применимо);
- для workflow содержать `workflow_id` и `input_context_masked` (в безопасном виде);
- содержать таргеты выполнения (например per-database и список/количество баз).

Binding Provenance MUST содержать список биндингов, где каждый биндинг включает:
- `target_ref` (куда подставляем),
- `source_ref` (откуда берём),
- `resolve_at` (`api|worker`),
- `sensitive` (true/false),
- `status` (`applied|skipped|unresolved`) и `reason` (если не applied).

#### Scenario: CLI action имеет plan+bindings без секретов
- **WHEN** staff делает preview или запускает `ibcmd_cli`/`designer_cli` action
- **THEN** система возвращает `argv_masked[]` и `bindings[]`, в которых секретные источники отмечены `sensitive=true`, а raw значения секретов отсутствуют

#### Scenario: Workflow action имеет plan+bindings без секретов
- **WHEN** staff делает preview или запускает `workflow` action
- **THEN** система возвращает `workflow_id`, `input_context_masked` и `bindings[]` без raw секретов

### Requirement: Preview plan/provenance до запуска
Система ДОЛЖНА (SHALL) предоставлять staff-only preview API для templates/manual operations flow без создания исполнения.

#### Scenario: Preview доступен из `/databases` manual operations
- **GIVEN** пользователь staff
- **WHEN** запрашивает preview перед запуском manual operation из `/databases`
- **THEN** UI получает plan+bindings до запуска

#### Scenario: Preview доступен из `/extensions` manual operations
- **GIVEN** пользователь staff
- **WHEN** запрашивает preview перед запуском manual operation из `/extensions`
- **THEN** UI получает plan+bindings до запуска

### Requirement: Persisted plan/provenance доступен в details
Система ДОЛЖНА (SHALL) сохранять provenance с привязкой к templates/manual operations контракту.

#### Scenario: Persisted metadata содержит manual operation context
- **WHEN** staff открывает details выполнения
- **THEN** metadata включает `manual_operation` и `template_id`
- **AND** action-catalog поля (`action_id`, `action_capability`) отсутствуют

### Requirement: Staff-only видимость с расширением через RBAC
По умолчанию система ДОЛЖНА (SHALL) ограничивать доступ к plan/provenance только staff пользователям.
Система ДОЛЖНА (SHALL) предусмотреть возможность расширить доступ через RBAC (например отдельным permission), не меняя формат plan/provenance.

#### Scenario: Non-staff не видит plan/provenance
- **WHEN** non-staff запрашивает детали операции или preview
- **THEN** plan/provenance не выдаются (403 или поля отсутствуют), и секреты не раскрываются

### Requirement: Безопасное логирование и отсутствие секретов
Система ДОЛЖНА (SHALL) гарантировать, что plan/provenance не содержат raw секретов в:
- API ответах,
- persisted данных,
- событиях/стримах,
- логах.

#### Scenario: Секреты не попадают в события и логи
- **WHEN** выполнение использует источники значений, помеченные как `sensitive=true` (env/credentials store/database password)
- **THEN** в plan/provenance присутствуют только masked представления и метаданные источников, без raw значений

### Requirement: Runtime-only биндинги репортятся worker'ом безопасно
Если часть биндингов резолвится на worker (например per-database контекст, allowlist-инъекции, runtime transforms), worker ДОЛЖЕН (SHALL) репортить в результат:
- `status` (`applied|skipped`) и `reason`,
- без раскрытия значений.

#### Scenario: Worker помечает skipped биндинг как unsupported
- **GIVEN** биндинг предполагает добавление аргумента, который не поддерживается для выбранной команды
- **WHEN** worker определяет, что биндинг неприменим
- **THEN** результат содержит `status=skipped` и `reason=unsupported_for_command`, а значения не раскрываются

### Requirement: Binding Provenance отражает per-target резолв DBMS connection и creds
Система ДОЛЖНА (SHALL) отражать в `bindings[]` (Binding Provenance) для `ibcmd_cli`:
- что `connection.offline.db_name` и другие offline‑параметры резолвятся per target database;
- что DBMS creds резолвятся через credential mapping;
- что секретные значения не раскрываются.

#### Scenario: bindings показывают источники per-target резолва
- **GIVEN** операция `ibcmd_cli` `scope=per_database` с N таргетами
- **WHEN** система строит execution plan и bindings
- **THEN** bindings содержат записи со `source_ref` вида `target_db.metadata.*` (или эквивалентно)
- **AND** bindings содержат запись `credentials.db_user_mapping` (или эквивалентно) для DBMS creds
- **AND** такие bindings имеют `sensitive=true` и не содержат raw значений секретов

