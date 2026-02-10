# operation-definitions-catalog Specification

## Purpose
TBD - created by archiving change add-unified-templates-action-catalog-contract. Update Purpose after archive.
## Requirements
### Requirement: Unified persistent contract MUST разделять definition и exposure
Система ДОЛЖНА (SHALL) хранить исполняемые конфигурации в двух связанных слоях:
- `operation_definition` — canonical execution payload,
- `operation_exposure` — surface-specific публикация (`template` или `action_catalog`).

#### Scenario: Один definition используется несколькими exposure
- **GIVEN** есть два объекта публикации (template и action) с идентичным execution payload
- **WHEN** данные сохраняются в unified persistent store
- **THEN** оба exposure ссылаются на один `operation_definition`
- **AND** дублирование execution payload не создаётся

### Requirement: Unified contract MUST поддерживать capability-specific config
Система ДОЛЖНА (SHALL) хранить capability-specific поля в exposure-уровне (`capability_config`) без смешивания с canonical execution payload definition.

#### Scenario: `extensions.set_flags` хранит target binding в exposure
- **GIVEN** action exposure с `capability="extensions.set_flags"`
- **WHEN** exposure проходит валидацию
- **THEN** `capability_config.target_binding.extension_name_param` обязателен
- **AND** exposure без этого поля получает fail-closed статус `invalid`

### Requirement: Migration MUST быть обратимо-наблюдаемой и fail-closed
Система ДОЛЖНА (SHALL) выполнять миграцию из legacy источников в unified store с журналом проблем и без публикации невалидных exposure.

#### Scenario: Невалидный legacy объект не публикуется
- **GIVEN** legacy запись не проходит unified validation
- **WHEN** выполняется backfill
- **THEN** создаётся запись в migration issues
- **AND** соответствующий exposure НЕ публикуется в effective read model

### Requirement: Unified contract MUST иметь явный API для definitions/exposures
Система ДОЛЖНА (SHALL) использовать `operation-catalog` API как основной management-контур для обеих surfaces:
- `template`,
- `action_catalog`.

API ДОЛЖЕН (SHALL) применять surface-aware RBAC:
- `template` surface: доступ по template permissions (view/manage, включая object-level),
- `action_catalog` surface: staff-only.

List endpoint exposures ДОЛЖЕН (SHALL):
- поддерживать staff unified list без `surface` как канонический способ выборки всех surfaces;
- поддерживать `surface=all` как явный алиас канонического staff unified-list;
- поддерживать server-side `search`/`filters`/`sort`/`limit`/`offset`;
- поддерживать `include=definitions` с side-loading definition данных в том же ответе;
- оставаться backward compatible с существующими параметрами и shape ответа.

#### Scenario: Staff получает unified list без параметра `surface`
- **GIVEN** staff пользователь запрашивает `GET /api/v2/operation-catalog/exposures/`
- **WHEN** endpoint обрабатывает запрос
- **THEN** возвращаются exposures разных surfaces в рамках одного списка
- **AND** `count/total` соответствуют server-side фильтрации и пагинации

#### Scenario: `surface=all` работает как алиас staff unified list
- **GIVEN** staff пользователь запрашивает `GET /api/v2/operation-catalog/exposures/?surface=all`
- **WHEN** endpoint обрабатывает запрос
- **THEN** возвращается тот же смысловой набор данных, что и при запросе без `surface` с теми же фильтрами/пагинацией

#### Scenario: Non-staff не может использовать staff unified list
- **GIVEN** non-staff пользователь имеет template view права
- **WHEN** вызывает `GET /api/v2/operation-catalog/exposures/` без `surface` или с `surface=all`
- **THEN** API возвращает `403 Forbidden`
- **AND** пользователь продолжает работать через `surface=template`

#### Scenario: Include definitions возвращается через side-loading
- **GIVEN** staff вызывает list endpoint с `include=definitions`
- **WHEN** endpoint формирует ответ
- **THEN** ответ содержит `exposures[]` и top-level `definitions[]` (уникальные по `id` для текущей страницы exposures)
- **AND** exposure продолжает ссылаться на definition через `definition_id` без inline embedding
- **AND** клиенту не требуется отдельный обязательный запрос на definitions для каждой перезагрузки списка

#### Scenario: Backward compatibility сохранена
- **GIVEN** существующий клиент вызывает endpoint без новых параметров
- **WHEN** запрос выполняется
- **THEN** API возвращает совместимый ответ
- **AND** существующий клиентский flow не ломается

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

