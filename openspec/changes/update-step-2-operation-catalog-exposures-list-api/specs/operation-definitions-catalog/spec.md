## MODIFIED Requirements
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
