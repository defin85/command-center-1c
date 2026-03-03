## Context
В проекте уже есть canonical master-data hub и операторский UI, но отсутствует системный двусторонний sync-контур между CC и ИБ. В результате изменения на одной стороне не становятся автоматически консистентными на другой стороне, а конфликтные состояния диагностируются поздно.

Дополнительно, для operational надежности нужно формально зафиксировать:
- at-least-once delivery semantics;
- checkpoint/replay правила;
- anti-loop поведение;
- fail-closed конфликтную модель.

## Goals / Non-Goals
- Goals:
  - обеспечить устойчивую двустороннюю синхронизацию `CC <-> ИБ` в tenant scope;
  - минимизировать drift между canonical сущностями и данными ИБ;
  - зафиксировать deterministic идемпотентность и recovery contract при crash/restart;
  - дать оператору прозрачный read-model статуса и конфликтов.
- Non-Goals:
  - не переводить все домены платформы на этот sync-контур;
  - не добавлять автоматический merge сложных бизнес-конфликтов;
  - не менять контракт распределения и публикации документов в части бизнес-логики.

## Constraints and invariants
- Sync контуры должны быть tenant-aware и database-aware.
- Конфликты и несогласованность policy должны обрабатываться fail-closed.
- Outbound и inbound контуры должны быть идемпотентными при повторной доставке событий.
- Секреты (пароли, токены) не попадают в diagnostics/read-model.
- Long-running sync НЕ выполняется синхронно в API-request; execution path обязан быть queue-based.
- Runtime OData/exchange-plan side effects выполняются worker-transport owner.
- Persisted sync-состояние хранится в общем Postgres текущего сервиса отдельными таблицами домена sync (без отдельной физической БД).

## Decisions
### Decision 1: Явный orchestration path через Workflows и Operations
Для sync применяется единая цепочка:
- domain слой master-data формирует/обновляет `sync_job` и domain intents;
- запуск выполняется через workflow execution (API entrypoint `/api/v2/workflows/execute-workflow/`, UI surface `/workflows`);
- workflow execution публикуется через operations enqueue/outbox в Redis stream;
- worker исполняет шаги sync и пишет event/result для operations projections.

Прямой запуск долгого sync из API handler запрещён.

### Decision 2: Гибридная двусторонняя архитектура sync-контуров
Используется два контура:
- outbound `CC -> ИБ`: transactional outbox + dispatcher;
- inbound `ИБ -> CC`: exchange-plan polling с checkpoint (`SelectChanges`/`NotifyChangesReceived`).

Это позволяет согласовать модель с текущими инфраструктурными ограничениями и не требовать немедленной миграции на внешний брокер.

### Decision 3: Явная policy источника истины
Для каждого sync scope (tenant/entity/database или tenant/entity) задаётся policy:
- `cc_master`;
- `ib_master`;
- `bidirectional`.

Policy используется как обязательный контракт для разрешения расхождений и генерации конфликтов.

### Decision 4: Outbound через transactional outbox
Mutating изменения canonical сущностей формируют outbox intent в той же транзакции, где фиксируется domain изменение.

Dispatcher:
- читает pending intents батчами с row-lock (`skip locked`);
- выполняет publish в ИБ идемпотентно;
- обновляет статус/ошибку/retry тайминг.

### Decision 5: Inbound через checkpointed polling
Inbound worker периодически читает изменения из ИБ по checkpoint и применяет их в canonical слой.

`NotifyChangesReceived` выполняется только после успешного локального commit, чтобы исключить потерю данных при сбое между apply и ack.

### Decision 6: Persistence boundary — общий Postgres, отдельные sync-таблицы
`sync_job/sync_scope/sync_checkpoint/sync_outbox/sync_conflict` и dedupe-реестр хранятся в общем Postgres текущего orchestrator, отдельными таблицами домена.

Отдельная физическая БД для sync в этом change не вводится.

### Decision 7: Конфликты как first-class объект
При нарушении policy или несовместимой версии записи создаётся persisted `sync_conflict`.

Conflict:
- блокирует silent overwrite;
- даёт machine-readable диагностику;
- требует явного operator reconcile/retry.

### Decision 8: Anti-loop contract обязателен
Каждое sync-событие несёт `origin_system` и `origin_event_id`.

Повторно полученное событие с тем же origin не должно порождать новый обратный sync side-effect (защита от ping-pong).

### Decision 9: Operator observability обязателен
Система публикует read-model:
- checkpoint position;
- lag;
- retry saturation;
- количество pending/failed конфликтов;
- последнее успешное применение по scope.

UI предоставляет filtering и ручные действия `retry/reconcile/resolve`.

### Decision 10: Staged rollout
Включение делается по tenant:
1. shadow mode (метрики без apply);
2. pilot tenant;
3. полное включение.

Rollback выполняется runtime setting override без удаления накопленных checkpoint/outbox/conflict данных.

## Alternatives considered
### Alternative A: Только outbound sync
Плюсы:
- проще внедрение.

Минусы:
- не устраняет drift при ручных изменениях в ИБ;
- не закрывает запрос на двустороннюю синхронизацию.

### Alternative B: CDC через PostgreSQL logical decoding + Debezium как единственный канал
Плюсы:
- сильный event-streaming паттерн.

Минусы:
- дополнительная инфраструктурная сложность и migration cost;
- не закрывает inbound чтение из 1С exchange plans напрямую.

### Alternative C: Domain -> Operations напрямую, без явного workflow слоя
Плюсы:
- меньше сущностей в orchestration.

Минусы:
- теряется единообразный execution path с остальным runtime;
- сложнее наблюдаемость/трассировка шагов и повторный запуск;
- выше риск ad-hoc логики вместо шаблонизированного workflow execution.

## Risks / Trade-offs
- Риск: рост конфликтов на старте rollout.
  - Mitigation: pilot enablement и явный conflict queue SLA.
- Риск: backlog и lag в dispatcher/poller.
  - Mitigation: metrics + alerting + throttling и bounded retry.
- Риск: неправильная policy конфигурация tenant.
  - Mitigation: fail-closed validation + preflight checks в UI/API.
- Риск: дубли после restart.
  - Mitigation: dedupe key + persisted checkpoints + idempotent apply contract.

## Migration Plan
1. Добавить schema и доменные модели sync в общий Postgres.
2. Добавить workflow template/contract для sync job и интеграцию запуска из domain слоя.
3. Подключить operations enqueue/outbox path для sync workflow execution.
4. Включить shadow-mode наблюдение без apply.
5. Включить outbound для pilot tenant.
6. Включить inbound для pilot tenant.
7. Включить full bidirectional режим для pilot.
8. Масштабировать на остальные tenant через staged rollout.

## Open Questions
- Нет блокирующих вопросов на уровне контракта. Детали rate-limit и batch-size фиксируются на этапе implementation в runbook.
