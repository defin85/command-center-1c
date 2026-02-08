## MODIFIED Requirements
### Requirement: RuntimeSetting для каталога действий расширений
Система ДОЛЖНА (SHALL) использовать unified persistent store как единственный source of truth для каталога действий расширений.

RuntimeSetting key `ui.action_catalog` НЕ ДОЛЖЕН (SHALL NOT) оставаться поддерживаемым runtime settings ключом для чтения, записи и overrides после decommission.

#### Scenario: Effective action catalog строится из unified exposures
- **GIVEN** в unified store есть published exposures с `surface="action_catalog"`
- **WHEN** пользователь вызывает endpoint получения action catalog
- **THEN** система возвращает effective catalog из unified exposures

#### Scenario: Legacy runtime key `ui.action_catalog` недоступен
- **WHEN** оператор пытается прочитать или изменить runtime setting `ui.action_catalog`
- **THEN** backend отклоняет запрос как unsupported/decommissioned key

### Requirement: Семантика extensions действий задаётся capability, а не id
Система ДОЛЖНА (SHALL) поддерживать явное поле `capability` в `operation_exposure(surface="action_catalog")`, чтобы backend определял семантику без привязки к `alias` (бывшему `action.id`).

#### Scenario: Произвольный alias exposure с capability работает
- **GIVEN** в `operation_exposure(surface="action_catalog")` есть действие с произвольным `alias` (например `ListExtension`)
- **AND** у него `capability` задан в формате namespaced string (например `extensions.list`)
- **AND** `executor.command_id` указывает на валидную команду драйвера
- **WHEN** пользователь запускает это действие
- **THEN** система трактует его как `extensions.list`, независимо от `alias`

### Requirement: Зарезервированные capability валидируются fail-closed
Система ДОЛЖНА (SHALL) обеспечивать детерминизм для reserved capability, которые backend понимает и использует для особой семантики (plan/apply, snapshot-marking), но НЕ ДОЛЖНА (SHALL NOT) требовать уникальности `capability` на уровне update-time валидации action exposures.

#### Scenario: Дубликаты reserved capability допускаются, но требуют детерминизма на запуске
- **GIVEN** в `operation_exposure(surface="action_catalog")` есть два actions с `capability="extensions.set_flags"`
- **WHEN** UI/клиент вызывает reserved endpoint без `action_id` (только по `capability`)
- **THEN** backend возвращает ошибку ambiguity и не выполняет действие
- **AND** error message содержит список candidate `alias`
