## 1. Contract
- [ ] 1.1 Обновить metadata catalog contract: добавить отдельное поле `config_generation_id` в read-model для выбранной ИБ без изменения canonical shared snapshot identity.
- [ ] 1.2 Обновить decision metadata context/read-model contract: сохранять и возвращать `config_generation_id` как отдельный provenance marker.
- [ ] 1.3 Зафиксировать в контракте, что `config_generation_id` не подменяет `config_version` и не вычисляется из OData/RAS/`Database.version`.

## 2. Backend
- [ ] 2.1 Встроить Designer-based probe `GetConfigGenerationID` в metadata refresh/read path, используя уже существующий Designer driver/execution path.
- [ ] 2.2 Persist/read: хранить resolved `config_generation_id` в database-scoped metadata resolution/provenance слое и прокидывать его в `/api/v2/pools/odata-metadata/catalog*` и `/api/v2/decisions`.
- [ ] 2.3 Обеспечить поведение без synthetic fallback: при недоступном Designer probe поле остаётся пустым, но не подменяется `config_version` или значением из другого источника.

## 3. Frontend
- [ ] 3.1 Обновить generated API contract/client и typed consumer для новых полей metadata catalog/decision context.
- [ ] 3.2 Обновить `/decisions`, чтобы UI показывал `Config generation ID` отдельно от `Config version`.
- [ ] 3.3 Обновить related metadata surfaces/empty states так, чтобы пустой `config_version` не скрывал resolved `config_generation_id`.

## 4. Validation
- [ ] 4.1 Добавить backend tests на success path `GetConfigGenerationID`, на отсутствие synthetic fallback и на сохранение marker в decision metadata context.
- [ ] 4.2 Добавить API/UI tests на отображение `config_generation_id` отдельно от `config_version`.
- [ ] 4.3 Прогнать `openspec validate add-config-generation-id-metadata-snapshots --strict --no-interactive`.
