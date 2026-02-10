## MODIFIED Requirements
### Requirement: Unified persistent contract MUST разделять definition и exposure
Система ДОЛЖНА (SHALL) хранить исполняемые конфигурации в двух связанных слоях:
- `operation_definition` — canonical execution payload,
- `operation_exposure` — публикация шаблона (`surface="template"`).

`operation_exposure(surface="action_catalog")` НЕ ДОЛЖЕН (SHALL NOT) существовать в целевой модели.

#### Scenario: Попытка создать exposure с `surface=action_catalog` отклоняется
- **WHEN** клиент отправляет upsert exposure с `surface="action_catalog"`
- **THEN** backend возвращает `HTTP 400` (`VALIDATION_ERROR`)
- **AND** запись не создаётся

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

## ADDED Requirements
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

## REMOVED Requirements
### Requirement: Unified contract MUST поддерживать capability-specific config
**Reason**: capability-specific action layer удаляется вместе с `action_catalog`.
**Migration**: использовать manual-operation compatibility на template exposure.
