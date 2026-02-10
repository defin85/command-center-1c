# operation-definitions-catalog Specification

## Purpose
TBD - created by archiving change add-unified-templates-action-catalog-contract. Update Purpose after archive.
## Requirements
### Requirement: Unified persistent contract MUST разделять definition и exposure
Система ДОЛЖНА (SHALL) хранить исполняемые конфигурации в двух связанных слоях:
- `operation_definition` — canonical execution payload,
- `operation_exposure` — публикация шаблона (`surface="template"`).

`operation_exposure(surface="action_catalog")` НЕ ДОЛЖЕН (SHALL NOT) существовать в целевой модели.

#### Scenario: Попытка создать exposure с `surface=action_catalog` отклоняется
- **WHEN** клиент отправляет upsert exposure с `surface="action_catalog"`
- **THEN** backend возвращает `HTTP 400` (`VALIDATION_ERROR`)
- **AND** запись не создаётся

### Requirement: Migration MUST быть обратимо-наблюдаемой и fail-closed
Система ДОЛЖНА (SHALL) выполнять миграцию из legacy источников в unified store с журналом проблем и без публикации невалидных exposure.

#### Scenario: Невалидный legacy объект не публикуется
- **GIVEN** legacy запись не проходит unified validation
- **WHEN** выполняется backfill
- **THEN** создаётся запись в migration issues
- **AND** соответствующий exposure НЕ публикуется в effective read model

### Requirement: Unified contract MUST иметь явный API для definitions/exposures
Система ДОЛЖНА (SHALL) использовать `operation-catalog` API как management-контур только для templates.

#### Scenario: List exposures возвращает template-only данные
- **WHEN** клиент вызывает `GET /api/v2/operation-catalog/exposures/`
- **THEN** в ответе присутствуют только exposures `surface="template"`
- **AND** поддерживаются server-side `search/filters/sort/pagination/include=definitions`

#### Scenario: Неподдерживаемый surface отклоняется fail-closed
- **WHEN** клиент передаёт `surface=action_catalog`
- **THEN** API возвращает `HTTP 400` (`VALIDATION_ERROR`)
- **AND** action-catalog path не активируется

### Requirement: Unified contract MUST canonicalize mapping между `executor_kind` и runtime driver
Система ДОЛЖНА (SHALL) использовать canonical mapping между `operation_definition.executor_kind` и runtime driver для canonical executors:
- `ibcmd_cli -> ibcmd`
- `designer_cli -> cli`
- `workflow -> driver не применяется`

`driver` НЕ ДОЛЖЕН (SHALL NOT) быть независимым пользовательским измерением для этих kinds в persistent/wire contract.

#### Scenario: Redundant driver не создаёт новый definition fingerprint
- **GIVEN** два write-запроса описывают один и тот же executor для `ibcmd_cli`, но в одном payload присутствует redundant `driver=ibcmd`
- **WHEN** backend нормализует payload и вычисляет definition fingerprint
- **THEN** создаётся/используется один и тот же `operation_definition`
- **AND** дублирование definition из-за redundant `driver` не возникает

#### Scenario: Конфликт kind/driver валидируется fail-closed
- **GIVEN** write-запрос передаёт конфликтный payload (`executor_kind=ibcmd_cli` и `driver=cli`)
- **WHEN** backend выполняет validation
- **THEN** запрос отклоняется с детализированной ошибкой по пути поля
- **AND** exposure не публикуется и не переводится в валидное состояние автоматически

#### Scenario: Legacy записи нормализуются при миграции
- **GIVEN** в unified store есть legacy exposure/definition с redundant или конфликтным kind/driver
- **WHEN** выполняется migration/normalization step
- **THEN** корректные записи нормализуются в canonical shape
- **AND** конфликтные записи фиксируются в diagnostics/migration issues для ручной доработки

### Requirement: Legacy action-catalog exposures MUST быть удалены hard delete миграцией
Система ДОЛЖНА (SHALL) выполнить hard delete legacy записей `surface="action_catalog"` в рамках cutover migration.

#### Scenario: После миграции action-catalog rows отсутствуют
- **WHEN** завершена миграция cutover
- **THEN** в persistent store отсутствуют записи `operation_exposure.surface="action_catalog"`
- **AND** orphaned definitions, связанные только с удалёнными exposures, очищены

#### Scenario: Historical execution references сохраняются
- **GIVEN** operation definition исторически использовался в plan/execution/snapshot данных
- **WHEN** выполняется cutover migration
- **THEN** definition НЕ удаляется как orphan
- **AND** historical records остаются читаемыми для audit/details

