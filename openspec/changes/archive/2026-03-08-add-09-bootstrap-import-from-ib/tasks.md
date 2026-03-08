## 1. Контракт bootstrap import (backend)
- [x] 1.1 Добавить domain-модель bootstrap job/chunk/report для scope `(tenant, database)` и выбранных `entity_type`.
- [x] 1.2 Зафиксировать lifecycle шагов `preflight -> dry_run -> execute -> finalize` с machine-readable статусами и fail-closed кодами ошибок.
- [x] 1.3 Реализовать детерминированный dependency order загрузки (`party -> item -> tax_profile -> contract -> binding`) и правила deferred/failed обработки зависимостей.
- [x] 1.4 Зафиксировать идемпотентность и resumable-поведение chunk execution (без duplicate canonical/binding side effects при retry/restart).

## 2. API и контракты
- [x] 2.1 Добавить v2 endpoints для bootstrap import:
  `preflight`, `jobs/create`, `jobs/list`, `jobs/get`, `jobs/cancel`, `jobs/retry-failed-chunks`.
- [x] 2.2 Обновить OpenAPI contracts и generated client types для новых endpoint-ов.
- [x] 2.3 Зафиксировать tenant-safe и RBAC-safe правила: mutating действия bootstrap доступны только tenant admin/staff в текущем tenant context.

## 3. Импорт из IB и интеграция с sync-инвариантами
- [x] 3.1 Реализовать source adapter для чтения данных из IB (OData/mapping path) с preflight проверками доступности и coverage выбранных сущностей.
- [x] 3.2 Интегрировать bootstrap apply с canonical upsert path для `Party/Item/Contract/TaxProfile/Binding`.
- [x] 3.3 Гарантировать anti-ping-pong: bootstrap apply маркируется как inbound origin (`origin_system=ib`, детерминированный `origin_event_id`) и не порождает обратный outbound echo.
- [x] 3.4 Зафиксировать conflict и diagnostics модель для частичных ошибок, сохраняя прогресс успешных chunks.

## 4. UI workflow в Pool Master Data
- [x] 4.1 Добавить отдельную рабочую зону `Bootstrap Import` в `/pools/master-data`.
- [x] 4.2 Реализовать wizard: выбор ИБ и сущностей, preflight, dry-run summary, execute.
- [x] 4.3 Добавить live progress, итоговый отчёт (created/updated/skipped/failed) и action `retry failed chunks`.
- [x] 4.4 Добавить operator-friendly обработку Problem Details/field-level ошибок без потери введённых данных.

## 5. Наблюдаемость и безопасность
- [x] 5.1 Добавить read-model и API-метаданные bootstrap jobs: статус, прогресс, chunk counters, время старта/окончания, last_error_code.
- [x] 5.2 Добавить redaction для diagnostics (без credentials/secrets) и audit trail для mutating операторских действий bootstrap.

## 6. Верификация
- [x] 6.1 Backend unit/integration тесты: preflight gating, dry-run, execute, retry failed chunks, idempotency/restart semantics.
- [x] 6.2 Frontend unit/component тесты для wizard-flow и error-handling.
- [x] 6.3 Прогнать релевантные линтеры/тесты и обновить документацию API/UI по новому bootstrap-сценарию.
