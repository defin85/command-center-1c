## MODIFIED Requirements
### Requirement: Unified contract MUST иметь явный API для definitions/exposures
Система ДОЛЖНА (SHALL) использовать `operation-catalog` API как основной management-контур для обеих surfaces:
- `template`,
- `action_catalog`.

API ДОЛЖЕН (SHALL) применять surface-aware RBAC:
- `template` surface: доступ по template permissions (view/manage, включая object-level),
- `action_catalog` surface: staff-only.

List endpoint exposures ДОЛЖЕН (SHALL):
- поддерживать `surface=all` для staff unified list use-case;
- поддерживать server-side `search`/`filters`/`sort`/`limit`/`offset`;
- поддерживать include definition данных в том же ответе (по явному параметру include);
- оставаться backward compatible с существующими параметрами и shape ответа.

#### Scenario: Staff получает unified list через `surface=all`
- **GIVEN** staff пользователь запрашивает `GET /api/v2/operation-catalog/exposures/?surface=all`
- **WHEN** endpoint обрабатывает запрос
- **THEN** возвращаются exposures разных surfaces в рамках одного списка
- **AND** `count/total` соответствуют server-side фильтрации и пагинации

#### Scenario: Non-staff не может использовать `surface=all`
- **GIVEN** non-staff пользователь имеет template view права
- **WHEN** вызывает `GET /api/v2/operation-catalog/exposures/?surface=all`
- **THEN** API возвращает `403 Forbidden`
- **AND** пользователь продолжает работать через `surface=template`

#### Scenario: Include definitions доступен для unified list
- **GIVEN** staff вызывает list endpoint с параметром include definition данных
- **WHEN** endpoint формирует ответ
- **THEN** ответ содержит данные definition, необходимые для list/edit flow
- **AND** клиенту не требуется отдельный обязательный запрос на definitions для каждой перезагрузки списка

#### Scenario: Backward compatibility сохранена
- **GIVEN** существующий клиент вызывает endpoint без новых параметров
- **WHEN** запрос выполняется
- **THEN** API возвращает совместимый ответ
- **AND** существующий клиентский flow не ломается
