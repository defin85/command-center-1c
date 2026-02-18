## ADDED Requirements
### Requirement: Publication auth MUST использовать RBAC infobase mapping как source-of-truth
Система ДОЛЖНА (SHALL) резолвить OData username/password для `pool.publication_odata` через `InfobaseUserMapping` на основе publication auth strategy:
- `actor`: mapping по `database + actor_username`;
- `service`: service mapping по `database`.

Система ДОЛЖНА (SHALL) брать OData endpoint (`odata_url`) из `Database`, но НЕ ДОЛЖНА (SHALL NOT) использовать `Database.username/password` как runtime fallback для publication auth после cutover.

#### Scenario: Actor mapping используется для публикации
- **GIVEN** run publication выполняется со стратегией `actor`
- **AND** для target database существует `InfobaseUserMapping` для `actor_username`
- **WHEN** worker исполняет `pool.publication_odata`
- **THEN** credentials запрос использует actor mapping
- **AND** публикация выполняется без обращения к `Database.username/password`

#### Scenario: Отсутствие mapping приводит к fail-closed
- **GIVEN** publication выполняется со стратегией `actor`
- **AND** для части target databases mapping отсутствует
- **WHEN** worker запрашивает credentials
- **THEN** шаг публикации завершается fail-closed с credentials error
- **AND** в diagnostics указываются проблемные target databases без раскрытия секретов

### Requirement: Конфигурация publication auth MUST быть операторски прозрачной
Система ДОЛЖНА (SHALL) разделять operator configuration surfaces для publication:
- `odata_url` задаётся в управлении базой (`Databases`);
- OData user/password задаются в RBAC infobase mappings (`/rbac`, Infobase Users).

Система ДОЛЖНА (SHALL) давать оператору явный сигнал, что legacy database credentials не являются source-of-truth для `pool.publication_odata`.

#### Scenario: Оператор конфигурирует publication через Databases + RBAC
- **GIVEN** у базы заполнен `odata_url`
- **AND** для оператора или service-аккаунта настроен infobase mapping
- **WHEN** запускается pool publication
- **THEN** система использует `odata_url` из базы и credentials из mapping
- **AND** публикация проходит без дополнительного ввода OData пароля в run UI

### Requirement: Publication auth errors MUST быть machine-readable и remediation-friendly
Система ДОЛЖНА (SHALL) возвращать детерминированные machine-readable коды для auth/configuration ошибок publication path:
- `ODATA_MAPPING_NOT_CONFIGURED`;
- `ODATA_MAPPING_AMBIGUOUS`;
- `ODATA_PUBLICATION_AUTH_CONTEXT_INVALID`.

Diagnostics ДОЛЖНЫ (SHALL) содержать `target_database_id` и operator remediation hint (путь в `/rbac`) без раскрытия секретов.

#### Scenario: Ambiguous mapping возвращает детерминированный код и remediation hint
- **GIVEN** для target database обнаружено неоднозначное mapping состояние
- **WHEN** выполняется `pool.publication_odata`
- **THEN** шаг завершается fail-closed с `error_code=ODATA_MAPPING_AMBIGUOUS`
- **AND** diagnostics содержит `target_database_id` и указание на настройку в `/rbac`

### Requirement: Cutover на mapping-only auth MUST проходить через operator-gated rollout
Система ДОЛЖНА (SHALL) перед production cutover выполнять preflight проверки coverage mapping по target databases и staged rehearsal.

Production cutover НЕ ДОЛЖЕН (SHALL NOT) выполняться без documented operator sign-off для staging и prod.

#### Scenario: Preflight coverage fail блокирует production cutover
- **GIVEN** release candidate включает mapping-only auth для `pool.publication_odata`
- **AND** preflight report показывает missing mapping хотя бы для одной target database
- **WHEN** выполняется go/no-go проверка релиза
- **THEN** production cutover отклоняется
- **AND** оператор получает список баз для remediation через `/rbac`
