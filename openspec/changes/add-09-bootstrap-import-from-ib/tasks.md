## 1. Контракт bootstrap import (backend)
- [ ] 1.1 Добавить domain-модель bootstrap job/chunk/report для scope `(tenant, database)` и выбранных `entity_type`.
- [ ] 1.2 Зафиксировать lifecycle шагов `preflight -> dry_run -> execute -> finalize` с machine-readable статусами и fail-closed кодами ошибок.
- [ ] 1.3 Реализовать детерминированный dependency order загрузки (`party -> item -> tax_profile -> contract -> binding`) и правила deferred/failed обработки зависимостей.
- [ ] 1.4 Зафиксировать идемпотентность и resumable-поведение chunk execution (без duplicate canonical/binding side effects при retry/restart).

## 2. API и контракты
- [ ] 2.1 Добавить v2 endpoints для bootstrap import:
  `preflight`, `jobs/create`, `jobs/list`, `jobs/get`, `jobs/cancel`, `jobs/retry-failed-chunks`.
- [ ] 2.2 Обновить OpenAPI contracts и generated client types для новых endpoint-ов.
- [ ] 2.3 Зафиксировать tenant-safe и RBAC-safe правила: mutating действия bootstrap доступны только tenant admin/staff в текущем tenant context.

## 3. Импорт из IB и интеграция с sync-инвариантами
- [ ] 3.1 Реализовать source adapter для чтения данных из IB (OData/mapping path) с preflight проверками доступности и coverage выбранных сущностей.
- [ ] 3.2 Интегрировать bootstrap apply с canonical upsert path для `Party/Item/Contract/TaxProfile/Binding`.
- [ ] 3.3 Гарантировать anti-ping-pong: bootstrap apply маркируется как inbound origin (`origin_system=ib`, детерминированный `origin_event_id`) и не порождает обратный outbound echo.
- [ ] 3.4 Зафиксировать conflict и diagnostics модель для частичных ошибок, сохраняя прогресс успешных chunks.

## 4. UI workflow в Pool Master Data
- [ ] 4.1 Добавить отдельную рабочую зону `Bootstrap Import` в `/pools/master-data`.
- [ ] 4.2 Реализовать wizard: выбор ИБ и сущностей, preflight, dry-run summary, execute.
- [ ] 4.3 Добавить live progress, итоговый отчёт (created/updated/skipped/failed) и action `retry failed chunks`.
- [ ] 4.4 Добавить operator-friendly обработку Problem Details/field-level ошибок без потери введённых данных.

## 5. Наблюдаемость и безопасность
- [ ] 5.1 Добавить read-model и API-метаданные bootstrap jobs: статус, прогресс, chunk counters, время старта/окончания, last_error_code.
- [ ] 5.2 Добавить redaction для diagnostics (без credentials/secrets) и audit trail для mutating операторских действий bootstrap.

## 6. Верификация
- [ ] 6.1 Backend unit/integration тесты: preflight gating, dry-run, execute, retry failed chunks, idempotency/restart semantics.
- [ ] 6.2 Frontend unit/component тесты для wizard-flow и error-handling.
- [ ] 6.3 Прогнать релевантные линтеры/тесты и обновить документацию API/UI по новому bootstrap-сценарию.

