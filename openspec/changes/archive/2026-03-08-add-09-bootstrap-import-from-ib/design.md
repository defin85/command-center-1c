## Context
В текущем проекте canonical master-data hub уже есть, но операторский путь первичной загрузки данных из ИБ отсутствует.
Оператор либо заполняет сущности вручную в `/pools/master-data`, либо использует узкоспециализированный bulk sync только для каталога организаций.

Существующий runtime двустороннего sync покрывает регулярную синхронизацию, но не предоставляет безопасный UX/API для первичного bootstrap-импорта с preflight/dry-run/reporting.

## Goals / Non-Goals
### Goals
- Добавить отдельный операторский bootstrap import из ИБ в canonical master-data hub.
- Дать управляемый асинхронный pipeline с preflight, dry-run, execute, progress и retry failed chunks.
- Сохранить fail-closed поведение и идемпотентность при больших объёмах.
- Не нарушить anti-ping-pong инвариант существующего sync контура.

### Non-Goals
- Не заменять существующий runtime регулярной двусторонней синхронизации.
- Не добавлять произвольный file-ingest (CSV/XLSX) в рамках этого change.
- Не делать новый отдельный UI-модуль вне `/pools/master-data`.

## Decisions
### Decision 1: Отдельный bootstrap job pipeline (а не синхронный API import)
Bootstrap выполняется асинхронно как job с chunk execution.
Причины:
- объём данных может быть большим и не подходит под request/response;
- нужен resumable и retry-friendly режим;
- требуется прозрачный прогресс и операторский отчёт.

### Decision 2: Обязательные этапы preflight и dry-run перед execute
До фактического execute система всегда проходит:
1. `preflight` (проверка tenant scope, auth mapping, доступности источника и минимального schema coverage);
2. `dry-run` (оценка ожидаемых create/update/skip/fail без mutating side effects);
3. только после этого доступен `execute`.

Если preflight/dry-run неуспешен, execute блокируется fail-closed.

### Decision 3: Детерминированный порядок сущностей и chunked import
Для обеспечения ссылочной целостности используется порядок:
`party -> item -> tax_profile -> contract -> binding`.

`contract` зависит от owner counterparty, поэтому строки без валидной зависимости не должны silently пропускаться:
- либо deferred для повторной попытки в рамках job;
- либо failed с machine-readable диагностикой.

### Decision 4: Идемпотентность и resume как базовый инвариант
Каждый chunk имеет стабильный idempotency fingerprint.
Повторный запуск chunk после restart/retry:
- не создаёт дубли canonical сущностей;
- не создаёт дубли bindings;
- не ломает итоговую статистику job.

### Decision 5: Anti-ping-pong сохраняется через inbound origin маркировку
Bootstrap apply маркируется как inbound (`origin_system=ib` + детерминированный `origin_event_id`), чтобы outbound path не отправлял echo обратно в ту же ИБ.

### Decision 6: UI как отдельная рабочая зона в текущем master-data workspace
В `/pools/master-data` добавляется зона `Bootstrap Import` с wizard flow:
1. Выбор базы и сущностей;
2. Preflight;
3. Dry-run summary;
4. Execute;
5. Progress + итоговый отчёт + retry failed chunks.

Это минимально-инвазивно для текущего IA и сохраняет task-oriented поведение workspace.

## API Sketch
- `POST /api/v2/pools/master-data/bootstrap-import/preflight/`
- `POST /api/v2/pools/master-data/bootstrap-import/jobs/`
- `GET /api/v2/pools/master-data/bootstrap-import/jobs/`
- `GET /api/v2/pools/master-data/bootstrap-import/jobs/{id}/`
- `POST /api/v2/pools/master-data/bootstrap-import/jobs/{id}/cancel/`
- `POST /api/v2/pools/master-data/bootstrap-import/jobs/{id}/retry-failed-chunks/`

Все mutating endpoints работают в tenant scope и требуют tenant admin/staff.

## Data Model Sketch
- `PoolMasterDataBootstrapJob`:
  - `tenant_id`, `database_id`, `entity_scope[]`, `status`,
  - `preflight_result`, `dry_run_summary`,
  - counters (`created`, `updated`, `skipped`, `failed`),
  - `started_at`, `finished_at`, `last_error_code`, `metadata`.
- `PoolMasterDataBootstrapChunk`:
  - `job_id`, `entity_type`, `chunk_index`, `status`,
  - `idempotency_key`, `attempt_count`, `last_error_code`, `last_error`,
  - `diagnostics`, `started_at`, `finished_at`.

## Trade-offs
- Reuse существующего inbound polling runtime (альтернатива) отвергнут:
  - в текущем состоянии он не является удобным операторским bootstrap UX;
  - требует обязательного callback wiring и не даёт естественного dry-run/wizard контракта.
- Отдельный bootstrap pipeline увеличивает surface area API/моделей, но снижает операционный риск и улучшает управляемость первичной загрузки.

## Risks / Mitigations
- Риск: ошибки маппинга полей/сущностей из ИБ.
  - Mitigation: обязательный preflight + dry-run + явная diagnostics модель.
- Риск: частичные ошибки на больших объёмах.
  - Mitigation: chunking, retry failed chunks, resumable job cursor.
- Риск: непреднамеренный outbound echo после bootstrap.
  - Mitigation: строгая inbound origin маркировка для bootstrap apply.
- Риск: утечка credentials в error payload.
  - Mitigation: redaction и Problem Details без секретов.

## Rollout Plan
1. Включить feature flag `pools.master_data.bootstrap_import.enabled` (по умолчанию off).
2. Внедрить backend preflight/dry-run/jobs API.
3. Внедрить UI wizard и read-model прогресса.
4. Включить в non-prod tenant, пройти операторский smoke.
5. По результатам smoke включить для целевых tenant.

