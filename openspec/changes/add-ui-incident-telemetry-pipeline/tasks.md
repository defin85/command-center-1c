## 1. Frontend producer contract

- [ ] 1.1 Зафиксировать, какие semantic events из `ui-action-observability` подлежат durable upload и какие low-value события допускают sampling/omission.
- [ ] 1.2 Зафиксировать canonical client batch envelope: `batch_id`, flush reason, tenant/user/session/release metadata, route context, ordered events и correlation identifiers. (после 1.1)
- [ ] 1.3 Зафиксировать background flush policy: size/time thresholds, unload-safe fallback, bounded retry queue и правило "telemetry path never blocks operator flow". (после 1.2)

## 2. Ingest and storage

- [ ] 2.1 Зафиксировать authenticated ingest path через gateway/orchestrator, включая duplicate-safe semantics по `batch_id` / `event_id`. (после 1.2)
- [ ] 2.2 Зафиксировать durable append-only storage model, normalized indexes и bounded retention policy для recent incident telemetry. (после 2.1)
- [ ] 2.3 Зафиксировать server-side validation/redaction contract для stored payloads, oversize trimming и fail-closed handling на unsafe fields. (после 2.1)

## 3. Query and analysis

- [ ] 3.1 Зафиксировать canonical read-only query surface для recent incident summaries и ordered timelines с фильтрами по tenant/user/session/request/ui_action/route/time window. (после 2.2)
- [ ] 3.2 Зафиксировать relation с `add-agent-readable-ui-observability-access`: новый change поставляет durable telemetry substrate, а consumer-facing prod/dev access policy reuse-ит этот query path. (после 3.1)
- [ ] 3.3 Зафиксировать query result shape, достаточный для LLM analysis без browser attach и без vendor UI scraping. (после 3.1)

## 4. Safety and validation

- [ ] 4.1 Зафиксировать fail-closed behavior при недоступности ingest/query path: bounded buffering, retry, duplicate-safe recovery и отсутствие влияния на primary user flow. (после 1.3 и 2.1)
- [ ] 4.2 Добавить validation scope для client batching, ingest redaction/idempotency, retention cleanup и query filtering/RBAC. (после 2.3, 3.1 и 4.1)
- [ ] 4.3 Прогнать `openspec validate add-ui-incident-telemetry-pipeline --strict --no-interactive`.
