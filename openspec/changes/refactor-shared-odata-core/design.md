## Context
В `go-services/worker` OData transport concerns распределены по нескольким путям исполнения. Это создаёт риск несогласованных retry/error semantics между `odataops` и `poolops`, особенно для `publication_odata`.

В проекте уже есть доменные требования по публикации, diagnostics и retry-контракту (`pool-workflow-execution-core`, `pool-odata-publication`). Новый change должен стандартизировать транспортный слой, не меняя доменную семантику.

## Goals
- Единый shared OData transport слой для `odataops` и `poolops`.
- Поведенческий паритет по retry/error/auth/session.
- Наблюдаемость transport-поведения на уровне метрик и трейсинга.
- Минимальный риск регрессий через поэтапную миграцию.

## Non-Goals
- Рефакторинг бизнес-логики pool runtime шагов.
- Изменение публичных REST контрактов pools API.
- Унификация всех worker-драйверов в общий супер-драйвер.

## Decisions
### Decision 1: Выделить `odata-core` как transport-only слой
`odata-core` отвечает только за transport concerns:
- конфигурация клиента и сессии;
- выполнение HTTP-запросов к OData;
- retry policy;
- нормализация ошибок;
- shared helpers для batch/upsert/posting.

Доменные правила (`pool publication`, `generic CRUD`) остаются в соответствующих драйверах.

### Decision 2: Миграция в два шага
1. Подключить `poolops(publication_odata)` к `odata-core`.
2. Подключить `odataops` к `odata-core` и удалить дубли.

Причина: `poolops` сейчас критичен для workflow-пути, и его стабилизация даст ранний сигнал о корректности shared слоя.

### Decision 3: Retry policy стандартизируется
`odata-core` использует bounded exponential backoff + jitter для retryable ошибок (transport errors, `5xx`, `429`) с ограниченным количеством попыток.

Для non-retryable ошибок (`4xx` кроме `429`) повтор не выполняется.

### Decision 4: Наблюдаемость обязательна
`odata-core` публикует единые telemetry-сигналы:
- request latency;
- retry count;
- финальный status class/error code;
- trace-атрибут resend attempt для повторных HTTP-запросов.

## Alternatives Considered
### A1. Оставить независимые transport-пути в `poolops` и `odataops`
Отклонено: неизбежный drift, дорогая поддержка, сложная диагностика.

### A2. Встроить pool domain семантику внутрь `odata-core`
Отклонено: нарушает границы ответственности и усложняет reuse.

### A3. Big-bang переключение обоих драйверов одновременно
Отклонено: высокий rollback risk, сложнее локализовать регрессии.

## Risks / Trade-offs
- Риск изменения поведения retry в edge-кейсах.
  - Mitigation: parity tests до/после для обоих драйверов и фиксированные retry-критерии.
- Риск latency overhead от дополнительной абстракции.
  - Mitigation: profiling + метрики p50/p95/p99, без дополнительных сетевых hops.
- Риск частичной миграции с “полу-дублирующим” кодом.
  - Mitigation: явный task на удаление legacy transport-компонентов.

## Migration Plan
1. Определить публичный интерфейс `odata-core` и контракт ошибок/ретраев.
2. Реализовать адаптер для `poolops(publication_odata)`.
3. Прогнать pool интеграционные сценарии (включая 500/3-org с созданием документов).
4. Переключить `odataops` на `odata-core`.
5. Прогнать parity/regression suite для CRUD + pool publication.
6. Удалить legacy transport-дубли.

## Open Questions
- Нужен ли отдельный runtime flag для постепенного включения `odata-core` per-driver.
- Нужна ли отдельная метрика совместимости медиа-типов/версий из `odata-compatibility-profile` в runtime path.
