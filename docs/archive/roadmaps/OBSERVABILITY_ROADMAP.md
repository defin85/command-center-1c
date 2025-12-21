# Roadmap: Observability — Метрики и Error Feedback

> **Статус:** Mostly Done (Фазы 1-5 реализованы, есть отложенные пункты)
> **Версия:** 1.6
> **Создан:** 2025-12-12
> **Обновлён:** 2025-12-15
> **Автор:** Claude Code
>
> **NOTE (2025-12-15):** Незавершённые UI-пункты, связанные с администрированием (DLQ просмотр/ретраи),
> перенесены в `docs/roadmaps/SPA_PRIMARY_ADMIN_UNIFICATION_ROADMAP.md` в рамках стратегии SPA-primary.

---

## Цель

Обеспечить полную наблюдаемость (observability) системы:
1. **Error Feedback** — гарантированная обратная связь при любых ошибках
2. **Metrics** — метрики для всех сервисов (ops/min, latency, errors)
3. **Tracing** — отслеживание пути операции через все сервисы

---

## Проблемы (текущее состояние)

> Примечание: часть пунктов ниже — описание исходных проблем, которые уже исправлены в коде; актуальные “хвосты” отмечены как (отложено) / TODO.

### 1. Потеря обратной связи при ошибках парсинга

```
Django → Redis Stream → Worker
                           ↓
                    Parse envelope FAIL
                           ↓
                    ACK + return (без feedback!)
                           ↓
                    Django не знает об ошибке
                    Операция висит в QUEUED навечно
```

**Причина:** `correlation_id` находится внутри envelope. Если envelope не парсится — Worker не знает куда отправить ошибку.

### 2. Метрики только у API Gateway

| Сервис | /metrics | Prometheus метрики |
|--------|----------|-------------------|
| API Gateway | ✅ | cc1c_requests_total, cc1c_request_duration_seconds |
| Orchestrator | ✅ | django-prometheus + cc1c_orchestrator_* |
| Worker | ✅ | cc1c_worker_* |
| ras-adapter | ✅ | cc1c_ras_* |
| worker (OData) | ✅ | external_http_* + driver metrics |
| designer-agent | ✅ | cc1c_designer_* |
| batch-service | ✅ | cc1c_batch_* |

### 3. Нет трассировки операций

- Невозможно понять где застряла операция
- Нет визуализации пути операции через сервисы
- Нет метрик по времени обработки на каждом этапе

---

## Архитектура решения

### Целевое состояние

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OBSERVABILITY                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ Prometheus  │───▶│  Grafana    │    │   Jaeger    │    │  Alerting   │  │
│  │  (metrics)  │    │ (dashboards)│    │  (tracing)  │    │ (PagerDuty) │  │
│  └──────▲──────┘    └─────────────┘    └──────▲──────┘    └─────────────┘  │
│         │                                      │                            │
│         │ scrape /metrics                      │ traces                     │
│         │                                      │                            │
│  ┌──────┴──────────────────────────────────────┴──────────────────────────┐ │
│  │                         ALL SERVICES                                    │ │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ │ │
│  │  │Orchestrator│ │  Worker   │ │ras-adapter│ │odata-adap.│ │designer-ag│ │ │
│  │  │  :8200    │ │  :8181    │ │  :8188    │ │  :8189    │ │  :8190    │ │ │
│  │  │ /metrics  │ │ /metrics  │ │ /metrics  │ │ /metrics  │ │ /metrics  │ │ │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Фаза 1: Error Feedback (Гарантированная обратная связь)

### 1.1 Дублирование correlation_id в Redis Stream fields

**Проблема:** correlation_id внутри envelope, при ошибке парсинга недоступен

**Решение:** Дублировать в поля XADD

**Django (redis_client.py):**
```python
def enqueue_operation_stream(self, message: Dict[str, Any]) -> Optional[str]:
    envelope = self._create_envelope(message)
    msg_id = self.client.xadd(
        self.STREAM_COMMANDS,
        {
            "data": json.dumps(envelope),
            "correlation_id": envelope["correlation_id"],  # NEW
            "operation_id": message.get("operation_id", ""),  # NEW
        },
        maxlen=self.STREAM_MAX_LEN
    )
    return msg_id
```

**Worker (stream_consumer.go):**
```go
func (c *Consumer) processMessage(ctx context.Context, message redis.XMessage) {
    messageID := message.ID

    // Extract fallback correlation_id from fields (before parsing envelope)
    fallbackCorrelationID, _ := message.Values["correlation_id"].(string)
    fallbackOperationID, _ := message.Values["operation_id"].(string)

    envelopeData, ok := message.Values["data"].(string)
    if !ok {
        c.publishFailedResult(ctx, fallbackOperationID, fallbackCorrelationID,
            "missing data field in message")
        c.ackMessage(ctx, messageID)
        return
    }

    var envelope events.Envelope
    if err := json.Unmarshal([]byte(envelopeData), &envelope); err != nil {
        c.publishFailedResult(ctx, fallbackOperationID, fallbackCorrelationID,
            fmt.Sprintf("invalid envelope: %v", err))
        c.ackMessage(ctx, messageID)
        return
    }
    // ... rest of processing
}
```

**Subtasks:**
- [x] 1.1.1: Обновить `redis_client.py` — добавить correlation_id, operation_id в XADD ✅
- [x] 1.1.2: Обновить `stream_consumer.go` — извлекать fallback IDs перед парсингом ✅
- [x] 1.1.3: Обновить `publishFailedResult` — использовать fallback если envelope не распарсился ✅
- [x] 1.1.4: Unit tests (11 тестов для extractFallbackIDs) ✅

**Дополнительные улучшения (code review):**
- [x] ACK только после успешной публикации результата
- [x] Fallback to disk при недоступности DLQ (`/var/log/cc1c/dlq-fallback.jsonl`)
- [x] Атомарный idempotency check через SetNX
- [x] Lock owner validation через Lua script

### 1.2 Dead Letter Queue (DLQ)

**Проблема:** Сообщения с ошибками теряются

**Решение:** Перемещать в отдельный stream для анализа

```
commands:worker:operations → (ошибка) → commands:worker:dlq
```

**Subtasks:**
- [x] 1.2.1: Создать stream `commands:worker:dlq` ✅
- [x] 1.2.2: Worker: перемещать failed messages в DLQ ✅
- [x] 1.2.3: Django EventSubscriber: обработчик DLQ сообщений ✅
- [x] 1.2.4: Deduplication DLQ через Redis Set с TTL ✅
- [ ] 1.2.5: UI для просмотра DLQ (перенесено → `docs/roadmaps/SPA_PRIMARY_ADMIN_UNIFICATION_ROADMAP.md`)
- [ ] 1.2.6: Retry механизм из DLQ (перенесено → `docs/roadmaps/SPA_PRIMARY_ADMIN_UNIFICATION_ROADMAP.md`)

---

## Фаза 2: Prometheus Metrics для всех сервисов

### 2.1 Стандартные метрики (для каждого сервиса)

| Метрика | Тип | Описание |
|---------|-----|----------|
| `cc1c_{service}_requests_total` | Counter | Всего запросов |
| `cc1c_{service}_request_duration_seconds` | Histogram | Время обработки |
| `cc1c_{service}_errors_total` | Counter | Ошибки по типам |
| `cc1c_{service}_active_operations` | Gauge | Активные операции |
| `cc1c_{service}_queue_depth` | Gauge | Глубина очереди |

### 2.2 Сервис-специфичные метрики

**Worker:**
```
cc1c_worker_tasks_processed_total{operation_type, status}
cc1c_worker_task_duration_seconds{operation_type}
cc1c_worker_saga_steps_total{workflow, step, status}
cc1c_worker_saga_compensations_total{workflow}
cc1c_worker_locks_acquired_total{resource_type}
cc1c_worker_locks_wait_seconds{resource_type}
```

**ras-adapter:**
```
cc1c_ras_commands_total{command_type, status}
cc1c_ras_command_duration_seconds{command_type}
cc1c_ras_connections_active
cc1c_ras_connection_errors_total
```

**worker (OData):**
```
external_http_requests_total{method,path,status}
external_http_duration_seconds{method,path}
cc1c_driver_executions_total{driver,operation_type,status}
cc1c_driver_duration_seconds{driver,operation_type}
```

**designer-agent:**
```
cc1c_designer_commands_total{command_type, status}
cc1c_designer_command_duration_seconds{command_type}
cc1c_designer_ssh_connections_active
cc1c_designer_ssh_connection_errors_total
```

**Orchestrator (Django):**
```
cc1c_orchestrator_operations_total{operation_type, status}
cc1c_orchestrator_operation_duration_seconds{operation_type}
cc1c_orchestrator_websocket_connections_active
cc1c_orchestrator_api_requests_total{endpoint, method, status}
```

### 2.3 Реализация по сервисам

**Subtasks:**

**Worker:** (уже реализовано ранее)
- [x] 2.3.1: HTTP server для /metrics (порт 9091) ✅
- [x] 2.3.2: prometheus/client_golang интегрирован ✅
- [x] 2.3.3: Метрики в stream_consumer.go ✅
- [x] 2.3.4: Метрики scheduler ✅

**ras-adapter:**
- [x] 2.3.6: /metrics endpoint (порт 8188) ✅
- [x] 2.3.7: HTTP метрики + RAS commands ✅
- [x] 2.3.8: Метрики для RAS connections ✅

**batch-service:**
- [x] 2.3.9: /metrics endpoint (порт 8187) ✅
- [x] 2.3.10: Batch operations метрики ✅
- [x] 2.3.11: v8executor метрики ✅

**worker (OData):**
- [x] 2.3.12: OData HTTP метрики через shared httptrace ✅
- [x] 2.3.13: Driver executions/duration метрики ✅
- [x] 2.3.14: Transaction duration (<15s SLA) ✅

**designer-agent:**
- [x] 2.3.15: /metrics endpoint (порт 8190) ✅
- [x] 2.3.16: Designer commands метрики ✅
- [x] 2.3.17: SSH pool метрики ✅

**Orchestrator:**
- [x] 2.3.18: django-prometheus middleware ✅
- [x] 2.3.19: Кастомные метрики (operations, batch, redis events) ✅
- [x] 2.3.20: Метрики для WebSocket connections ✅

---

## Фаза 3: Operation Tracing (Путь операции)

### 3.1 Концепция

Каждая операция проходит через несколько сервисов:

```
Frontend → API Gateway → Orchestrator → Redis → Worker → ras-adapter → 1C
                                                    ↓
                                               OData (direct) → 1C
```

**Цель:** Видеть полный путь операции с временными метками на каждом этапе.

### 3.2 Operation Timeline (в Redis)

```
operation:timeline:{operation_id}
├── [1702400000000] orchestrator:created
├── [1702400000100] orchestrator:enqueued
├── [1702400000200] worker:received
├── [1702400000300] worker:saga:started
├── [1702400000400] worker:saga:step:1:lock_acquire
├── [1702400000500] ras-adapter:command:received
├── [1702400000600] ras-adapter:command:completed
├── [1702400000700] worker:saga:step:1:completed
├── [1702400001000] worker:saga:step:2:ras_lock
├── ...
└── [1702400005000] worker:completed
```

### 3.3 Реализация

**Subtasks:**
- [x] 3.3.1: Создать `shared/tracing/timeline.go` — запись в Redis ZSET ✅ (60fd038)
- [x] 3.3.2: Интегрировать в Worker (каждый шаг саги) ✅ (d1e11fc)
- [x] 3.3.3: Интегрировать в адаптеры (получение/завершение команды) ✅ (100fd34)
- [x] 3.3.4: Django API `POST /api/v2/internal/get-operation-timeline` ✅ (0f6c209)
- [x] 3.3.5: Frontend Waterfall Timeline в Service Mesh ✅ (be95caa)

### 3.4 Jaeger Integration (опционально)

**Subtasks:**
- [ ] 3.4.1: Добавить OpenTelemetry SDK в Go сервисы
- [ ] 3.4.2: Добавить opentelemetry-python в Django
- [ ] 3.4.3: Propagate trace context через Redis Streams
- [ ] 3.4.4: Настроить Jaeger collector

---

## Фаза 4: Grafana Dashboards

### 4.1 System Overview Dashboard

- Общий health всех сервисов
- Ops/min по каждому сервису
- Error rate по сервисам
- Queue depths
- Active operations

### 4.2 Operation Flow Dashboard

- Sankey диаграмма: откуда куда идут операции
- Время на каждом этапе (heatmap)
- Bottlenecks (где задерживаются)
- Failed operations по этапам

### 4.3 Service-specific Dashboards

- Worker: Saga execution, locks, compensations
- ras-adapter: RAS commands, connection pool
- worker: OData CRUD + batch metrics (driver + external_http)
- designer-agent: SSH connections, long-running commands

**Subtasks:**
- [x] 4.1: Dashboard: System Overview ✅ (`system-overview.json`, 15 панелей)
- [x] 4.2: Dashboard: Operation Flow ✅ (`operation-flow.json`, 10 панелей)
- [x] 4.3: Dashboard: Worker Details ✅ (`worker-details.json`, 14 панелей)
- [x] 4.4: Dashboard: Adapters Details ✅ (`adapters-details.json`, 22 панели)
- [x] 4.5: Alerting rules ✅ (47 правил: 19 recording + 28 alerts)
- [ ] 4.6: PagerDuty/Slack интеграция (отложено — требует Alertmanager)

**Code Review Improvements (17 рекомендаций):**
- [x] Division by zero защита в recording rules и dashboard queries
- [x] Datasource variable `${DS_PROMETHEUS}` во всех dashboards
- [x] Thresholds скорректированы (scheduler 100, batch 50, lock 5s, memory 95%)
- [x] Alerts перенесены из recording_rules.yml в `alerts/api_alerts.yml`
- [x] Recording rules intervals унифицированы (15s = scrape_interval)
- [x] Убраны избыточные labels (aggregation, percentile)
- [x] Unit "opm" добавлен для rate панелей
- [x] JSON validation добавлен в `lint.sh`
- [x] `promtool check rules` добавлен в `lint.sh`
- [x] Проверка exporters добавлена в `health-check.sh`
- [x] Комментарий про Frontend scrape в prometheus-native.yml

**Файлы alerts:**
- `alerts/operational.yml` — 13 rules (ServiceDown, Backlog, Infrastructure)
- `alerts/api_alerts.yml` — 3 rules (HighErrorRate, HighLatency, SchedulerJobFailures)
- `alerts/rollback_alerts.yml` — 12 rules (A/B testing rollback decisions)

---

## Фаза 5: Real-time Operation Visualization ✅ ЗАВЕРШЕНА

### 5.1 Service Mesh Live View

Обновить `/service-mesh` для показа:
- Активные операции в реальном времени
- Путь операции (анимация)
- Время на каждом сервисе
- Ошибки с подсветкой

### 5.2 Operation Detail View

- Timeline с шагами
- Логи каждого шага
- Метаданные (payload, результат)
- Retry history

**Subtasks:**
- [x] 5.1: WebSocket events для operation flow ✅ (useServiceMesh.ts с race condition защитой)
- [x] 5.2: Frontend: анимация пути операции ✅ (CSS animations в ServiceFlowDiagram.css)
- [x] 5.3: Frontend: Operation detail drawer с timeline ✅ (Waterfall Timeline Drawer)
- [x] 5.4: Frontend: фильтры по статусу ✅ (RecentOperationsTable с Select multiple)

**Bug Fixes & Improvements:**
- [x] 5.5: WebSocket race condition fix (requestId pattern, ping protection)
- [x] 5.6: Throttle для setNodes() (100ms) — предотвращает UI freezes
- [x] 5.7: Timeout 60сек для зависших операций — автоочистка
- [x] 5.8: Deduplication для operationHistory — нет дубликатов
- [x] 5.9: Улучшенный empty message (динамический по фильтрам)
- [x] 5.10: DISPLAY_LIMIT константа (нет magic numbers)

---

## Приоритеты

| Фаза | Приоритет | Сложность | Влияние |
|------|-----------|-----------|---------|
| 1. Error Feedback | 🔴 Critical | Medium | High — устраняет потерю операций |
| 2. Prometheus Metrics | 🟠 High | Medium | High — основа для мониторинга |
| 3. Operation Tracing | 🟡 Medium | High | Medium — debugging, optimization |
| 4. Grafana Dashboards | 🟡 Medium | Low | High — визуализация |
| 5. Real-time Visualization | 🟢 Low | High | Medium — UX improvement |

---

## Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Overhead от метрик | Low | Medium | Sampling, async writes |
| Redis memory для timeline | Medium | Low | TTL на записи, cleanup job |
| Сложность интеграции Jaeger | High | Low | Опционально, Phase 3.4 |

---

## Критерии завершения

### Фаза 1 ✅ ЗАВЕРШЕНА
- [x] При любой ошибке парсинга Django получает failed result
- [x] DLQ содержит проблемные сообщения для анализа
- [x] Fallback to disk при недоступности Redis
- [x] Атомарные операции (SetNX, Lua scripts)

### Фаза 2 ✅ ЗАВЕРШЕНА
- [x] Все 7 сервисов экспортируют /metrics (API Gateway, Worker, RAS, Batch, OData, Designer, Orchestrator)
- [x] Prometheus scrape config обновлён (prometheus-native.yml)
- [x] Service Mesh использует реальные метрики из Prometheus (c fallback при недоступности Prometheus)

### Фаза 3 ✅ ЗАВЕРШЕНА
- [x] API возвращает timeline операции (`POST /api/v2/internal/get-operation-timeline` и `POST /api/v2/operations/get-operation-timeline/`)
- [x] Timeline показывает все этапы с timestamps (Waterfall Timeline в Service Mesh)
- [x] Все сервисы записывают события: Worker, RAS, OData, Designer, Batch adapters
- [x] 135+ тестов (Go + Python + TypeScript)

### Фаза 4 ✅ ЗАВЕРШЕНА
- [x] 4 Grafana dashboards доступны (61 панель суммарно)
- [x] 47 Prometheus rules (19 recording + 28 alerts)
- [x] Recording rules переписаны на реальные метрики (cc1c:*)
- [x] Division by zero защита во всех вычислениях
- [x] Datasource variable для переносимости dashboards
- [x] JSON validation и promtool check в CI/CD (`lint.sh`)
- [x] Проверка exporters в `health-check.sh`
- [ ] PagerDuty/Slack интеграция (отложено на Phase 4.6)

### Фаза 5 ✅ ЗАВЕРШЕНА
- [x] Live view показывает активные операции (WebSocket + useServiceMesh)
- [x] Анимация пути операции работает (CSS keyframes в ServiceFlowDiagram.css)
- [x] Фильтрация операций по статусу (RecentOperationsTable)
- [x] Race condition protection (requestId pattern)
- [x] Performance optimizations (throttle, deduplication)

---

## См. также

- [STATE_MACHINE_MIGRATION_ROADMAP.md](./STATE_MACHINE_MIGRATION_ROADMAP.md) — Event-Driven архитектура
- [SERVICE_MESH_DIAGRAM_UPDATE_ROADMAP.md](./SERVICE_MESH_DIAGRAM_UPDATE_ROADMAP.md) — Service Mesh диаграмма
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [OpenTelemetry Go SDK](https://opentelemetry.io/docs/instrumentation/go/)
