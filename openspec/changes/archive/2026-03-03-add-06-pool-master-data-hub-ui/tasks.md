## 1. Contracts and backend API
- [x] 1.1 Спроектировать и зафиксировать public API contract для master-data hub в namespace `/api/v2/pools/master-data/` для групп `parties/items/contracts/tax-profiles/bindings` с операциями list/get/upsert, pagination/filtering и уникальными operationId.
- [x] 1.2 Зафиксировать и реализовать явный `Organization <-> Party` binding контракт (MVP `1:1`) через `organization.master_party_id` с tenant/role инвариантами и детерминированным backfill (match by tenant+inn(+kpp), ambiguous/no-match -> remediation-list, без silent fallback).
- [x] 1.3 Реализовать v2 endpoints и сериализаторы для list/upsert/get по canonical сущностям и bindings, сохранив инварианты:
  - `Party` имеет минимум одну роль,
  - `Contract` строго owner-scoped к `counterparty`,
  - `TaxProfile` ограничен `vat_rate/vat_included/vat_code`.
- [x] 1.4 Добавить в run/report read-model стабильный блок `run.master_data_gate` c фиксированной схемой (`status/mode/targets_count/bindings_count/error_code/detail/diagnostic`) и `null` для historical run без gate-шага.
- [x] 1.5 Для новых master-data endpoint-ов закрепить единый `application/problem+json` error contract и machine-readable коды.

## 2. Runtime settings and feature control
- [x] 2.1 Добавить ключ `pools.master_data.gate_enabled` в registry поддерживаемых runtime settings override.
- [x] 2.2 Реализовать единый precedence resolver для gate flag: `tenant override -> global runtime setting -> env default`.
- [x] 2.3 Реализовать использование effective runtime setting в проверке feature flag master-data gate с fail-closed поведением при неконсистентной конфигурации (`MASTER_DATA_GATE_CONFIG_INVALID`, без OData side effects).

## 3. Frontend workspace and guided authoring
- [x] 3.1 Добавить маршрут `/pools/master-data` и пункт меню в Pools navigation.
- [x] 3.2 Реализовать страницу workspace с табами `Party`, `Item`, `Contract`, `TaxProfile`, `Bindings`, включая поиск, фильтры и create/edit формы.
- [x] 3.3 Встроить в `/pools/catalog` token picker для `document_policy` mapping (`field_mapping`/`table_parts_mapping`) с явным `source_type` (`expression|master_data_token`) и валидацией canonical token формата.
- [x] 3.4 Добавить в `/pools/runs` карточку `Master Data Gate` с отображением summary, кодов ошибок, контекста сущности/ИБ и action-oriented remediation hint.

## 4. Verification and rollout
- [x] 4.1 Добавить backend тесты API/доменных инвариантов и контракта `master_data_gate` в run/report.
- [x] 4.2 Добавить frontend unit/integration тесты для workspace, token picker и run diagnostics panel.
- [x] 4.3 Обновить e2e browser-flow для pools (минимум: authoring token -> failed gate diagnostics -> remediation-ready view).
- [x] 4.4 Добавить проверку миграционного сценария backfill `Organization <-> Party` и fail-closed диагностики при отсутствующем binding.
- [x] 4.5 Добавить staged rollout/rollback runbook: deploy with gate off -> backfill/remediation -> pilot tenant enable -> scale-out; rollback через tenant override и релизный откат без удаления binding-данных.
- [x] 4.6 Прогнать `openspec validate add-06-pool-master-data-hub-ui --strict --no-interactive`.
