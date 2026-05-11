## 1. Observability contract
- [x] 1.1 Обновить spec `ui-action-observability`: добавить explicit semantic route intent, route-write attribution и bounded `route.loop_warning` contract без перехода к raw clickstream.
- [x] 1.2 Обновить spec `agent-ui-observability-access`: потребовать, чтобы default agent monitoring path возвращал route intent, writer attribution и loop diagnostics как machine-readable signals.

## 2. Frontend instrumentation pilot
- [x] 2.1 Добавить explicit `trackUiAction(...)` wiring для route-changing zone switches в `PoolMasterDataPage` с устойчивыми `surface_id` / `control_id` и `from_tab` / `to_tab`.
- [x] 2.2 Добавить route-write attribution вокруг `setSearchParams(...)` writers в `PoolMasterDataPage`, `SyncStatusTab` и `DedupeReviewTab`, сохранив redaction-first contract и bounded metadata.
- [x] 2.3 Реализовать bounded route loop detector, который агрегирует oscillation по ключевым route params и эмитит machine-readable warning вместо flooding одними `route.transition`.

## 3. Access and query surfaces
- [x] 3.1 Убедиться, что local export bundle (`exportBundle`) сохраняет новые intent/attribution/loop fields в понятной machine-readable форме.
- [x] 3.2 Если durable telemetry/query path уже shipped через `ui-incident-telemetry`, расширить ingest/query/serializer contract так, чтобы `query-ui-incidents` / `query-ui-timeline` не теряли новые observability signals.
- [x] 3.3 При необходимости обновить OpenAPI / generated frontend types для prod/dev query path без нарушения existing RBAC/redaction guarantees.

## 4. Verification
- [x] 4.1 Добавить frontend tests на `Pool Master Data` route intent attribution и loop warning surface.
- [x] 4.2 Добавить focused tests на timeline/query payload, если backend/query contract меняется.
- [x] 4.3 Прогнать `openspec validate add-ui-route-intent-observability --strict --no-interactive`.
