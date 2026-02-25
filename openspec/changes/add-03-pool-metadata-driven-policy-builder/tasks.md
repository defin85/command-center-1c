## 1. Backend metadata catalog
- [ ] 1.1 Добавить read endpoint каталога OData-метаданных для выбранной ИБ (documents/fields/table parts/row fields).
- [ ] 1.2 Добавить persisted snapshot storage в БД как source-of-truth для metadata catalog (`config_name`, `config_version`, `metadata_hash`, payload, `fetched_at`, `source`, `is_current`/эквивалент).
- [ ] 1.3 Добавить Redis read-through cache как ускоритель чтения: hit -> Redis, miss/error -> fallback к current snapshot в БД, плюс TTL и key-prefix.
- [ ] 1.4 Добавить refresh-path, который читает live `$metadata`, обновляет/создаёт snapshot в БД и прогревает Redis.
- [ ] 1.5 Добавить fail-closed обработку auth/configuration ошибок для metadata-read path с machine-readable кодами.

## 2. Backend validation and contracts
- [ ] 2.1 Расширить валидацию topology mutating API: проверка ссылок `document_policy` на существующие metadata-объекты в current snapshot выбранной ИБ/конфигурации.
- [ ] 2.2 Обновить OpenAPI контракт для metadata catalog endpoint и новых validation ошибок.
- [ ] 2.3 Добавить unit/integration тесты для snapshot lifecycle (create/update/version switch), Redis fallback и validation path.

## 3. Frontend builders
- [ ] 3.1 Добавить data-layer в UI для загрузки/обновления metadata catalog по выбранной базе.
- [ ] 3.2 Реализовать `Document policy builder` c интерактивным выбором документов, реквизитов и табличных частей.
- [ ] 3.3 Реализовать `Edge metadata builder` с сохранением произвольных metadata-полей.
- [ ] 3.4 Сохранить raw JSON fallback и двухстороннюю синхронизацию с builder-режимом.
- [ ] 3.5 Добавить frontend тесты на builder-flow, round-trip и ошибки валидации.

## 4. Rollout and verification
- [ ] 4.1 Прогнать `openspec validate add-03-pool-metadata-driven-policy-builder --strict --no-interactive`.
- [ ] 4.2 Прогнать целевые backend/frontend тесты и зафиксировать результаты.
- [ ] 4.3 Подготовить rollout note для операторов `/pools/catalog` (builder vs raw mode) и для эксплуатации (refresh, версии snapshot, деградация Redis).
