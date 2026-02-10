## MODIFIED Requirements
### Requirement: Unified persistent contract MUST разделять definition и exposure
Система ДОЛЖНА (SHALL) хранить исполняемые конфигурации в двух связанных слоях:
- `operation_definition` — canonical execution payload,
- `operation_exposure` — публикация шаблона (`surface="template"`).

`operation_exposure(surface="action_catalog")` НЕ ДОЛЖЕН (SHALL NOT) поддерживаться в целевой модели.

#### Scenario: Попытка создать exposure с `surface=action_catalog` отклоняется
- **WHEN** клиент отправляет upsert exposure с `surface="action_catalog"`
- **THEN** backend возвращает fail-closed ошибку валидации
- **AND** запись не создаётся

#### Scenario: Один definition переиспользуется несколькими template exposures
- **GIVEN** два templates имеют идентичный execution payload
- **WHEN** данные сохраняются в persistent store
- **THEN** exposures ссылаются на один `operation_definition`
- **AND** дублирование execution payload не создаётся

### Requirement: Unified contract MUST иметь явный API для definitions/exposures
Система ДОЛЖНА (SHALL) использовать `operation-catalog` API как основной management-контур только для template exposures.

API НЕ ДОЛЖЕН (SHALL NOT) поддерживать action-catalog surface и связанные write/read сценарии.

#### Scenario: List exposures возвращает template-only данные
- **WHEN** клиент вызывает `GET /api/v2/operation-catalog/exposures/`
- **THEN** в ответе присутствуют только exposures `surface="template"`
- **AND** shape ответа остаётся server-driven (`search`/`filters`/`sort`/`limit`/`offset`)

#### Scenario: `surface=action_catalog` не поддерживается
- **WHEN** клиент вызывает list/read/write с `surface=action_catalog`
- **THEN** API возвращает fail-closed ошибку
- **AND** action-catalog данные не участвуют в управлении

## REMOVED Requirements
### Requirement: Unified contract MUST поддерживать capability-specific config
**Reason**: capability-specific слой `action_catalog` удаляется из модели.
**Migration**: использовать template-based контракт и runtime input в plan/apply.
