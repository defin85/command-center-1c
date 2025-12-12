# Roadmap: Обновление Service Mesh диаграммы

> **Статус:** Done
> **Версия:** 1.1
> **Создан:** 2025-12-12
> **Завершён:** 2025-12-12
> **Автор:** Claude Code
>
> ### Результаты
> - Добавлен тип связи `streams` (Redis Streams) с зелёным цветом
> - Добавлены сервисы: `odata-adapter`, `designer-agent`
> - Обновлены связи Worker → адаптеры на Redis Streams
> - Добавлены обратные связи адаптеры → Redis (events)
> - Диаграмма показывает 11 сервисов (без backup-service — PLANNED)

---

## Цель

Привести диаграмму Service Mesh (`/service-mesh`) в соответствие с текущей Event-Driven архитектурой после миграции на Redis Streams (см. `STATE_MACHINE_MIGRATION_ROADMAP.md`).

---

## Текущее состояние (проблема)

### Диаграмма показывает устаревшую архитектуру:

```
Frontend → API Gateway → Orchestrator → PostgreSQL
                              ↓
                            Redis
                              ↓
                           Worker
                           /    \
                    (HTTP)      (HTTP)
                      ↓           ↓
               ras-adapter   batch-service
```

**Проблемы:**
1. Worker → ras-adapter показан как HTTP (устарело — теперь Redis Streams)
2. Worker → batch-service показан как HTTP (устарело — теперь Redis Streams)
3. Отсутствует `odata-adapter` (создан в Phase 1.5)
4. Отсутствует `designer-agent` (создан в Phase 1.6)
5. Нет типа соединения `streams` для Redis Streams
6. Связи через Redis не показаны для Execution Layer

---

## Целевая архитектура

```
Frontend → API Gateway → Orchestrator → PostgreSQL
                              ↓
                            Redis ←──────────────────┐
                              ↓                      │
                           Worker                    │
                      (Redis Streams)                │
              ┌────────┬────────┬────────┐          │
              ↓        ↓        ↓        ↓          │
        ras-adapter  odata    designer  batch       │
              │     adapter    agent   service      │
              └────────┴────────┴────────┘          │
                         │ (events:*)               │
                         └──────────────────────────┘
```

**Изменения:**
- Worker общается с адаптерами через Redis Streams (не HTTP)
- Добавлены новые сервисы: `odata-adapter`, `designer-agent`
- Новый тип соединения: `streams` (Redis Streams)
- Адаптеры публикуют результаты обратно в Redis

---

## Затрагиваемые файлы

### Frontend (основные изменения)

```
frontend/src/types/serviceMesh.ts
├── ConnectionType: добавить 'streams'
├── CONNECTION_TYPE_COLORS: добавить цвет для streams
├── CONNECTION_TYPE_LABELS: добавить метку
├── CONNECTION_TYPES: обновить связи
├── DEFAULT_SERVICE_POSITIONS: добавить новые сервисы
└── SERVICE_DISPLAY_CONFIG: добавить конфиги новых сервисов
```

### Backend (метрики)

```
orchestrator/apps/operations/services/prometheus_client.py
└── Добавить сбор метрик для новых сервисов

go-services/odata-adapter/internal/api/health.go
└── Убедиться, что /health и /metrics доступны

go-services/designer-agent/internal/api/health.go
└── Убедиться, что /health и /metrics доступны
```

---

## Фазы реализации

### Фаза 1: Обновление типов и констант

**Файл:** `frontend/src/types/serviceMesh.ts`

**Subtasks:**
- [ ] 1.1: Добавить `streams` в `ConnectionType`
- [ ] 1.2: Добавить цвет для `streams` в `CONNECTION_TYPE_COLORS` (предлагаю `#52c41a` — зелёный, как Redis Streams)
- [ ] 1.3: Добавить метку `Redis Streams` в `CONNECTION_TYPE_LABELS`
- [ ] 1.4: Обновить `CONNECTION_TYPES`:
  - `worker->ras-adapter`: `http` → `streams`
  - `worker->batch-service`: `http` → `streams`
  - Добавить `worker->odata-adapter`: `streams`
  - Добавить `worker->designer-agent`: `streams`
  - Добавить `ras-adapter->redis`: `streams` (events)
  - Добавить `odata-adapter->redis`: `streams` (events)
  - Добавить `designer-agent->redis`: `streams` (events)
  - Добавить `batch-service->redis`: `streams` (events)
- [ ] 1.5: Добавить позиции для новых сервисов в `DEFAULT_SERVICE_POSITIONS`
- [ ] 1.6: Добавить конфиги в `SERVICE_DISPLAY_CONFIG`:
  - `odata-adapter`: icon `database`, description `OData CRUD operations`
  - `designer-agent`: icon `tool`, description `1C Designer Agent (SSH)`

---

### Фаза 2: Обновление диаграммы связей

**Файл:** `frontend/src/components/service-mesh/ServiceFlowDiagram.tsx`

**Subtasks:**
- [ ] 2.1: Убедиться, что новые типы соединений корректно отображаются
- [ ] 2.2: Проверить, что dagre layout работает с новой топологией
- [ ] 2.3: Добавить `streams` в легенду (если не автоматически)

---

### Фаза 3: Backend — метрики для новых сервисов

**Subtasks:**
- [ ] 3.1: Проверить, что `odata-adapter` экспортирует метрики на `/metrics`
- [ ] 3.2: Проверить, что `designer-agent` экспортирует метрики на `/metrics`
- [ ] 3.3: Обновить `prometheus_client.py` для сбора метрик с новых сервисов
- [ ] 3.4: Добавить новые сервисы в Prometheus scrape config (если требуется)

---

### Фаза 4: Тестирование и документация

**Subtasks:**
- [ ] 4.1: Визуальное тестирование диаграммы на `/service-mesh`
- [ ] 4.2: Проверить, что все сервисы отображаются
- [ ] 4.3: Проверить, что связи правильно типизированы и окрашены
- [ ] 4.4: Обновить документацию (если требуется)

---

## Детали изменений

### 1. Новые сервисы

| Сервис | Порт | Описание | Icon |
|--------|------|----------|------|
| `odata-adapter` | 8189 | OData CRUD операции | `database` |
| `designer-agent` | 8086 | 1C Designer через SSH | `tool` |

### 2. Изменённые связи

| Связь | Было | Стало | Причина |
|-------|------|-------|---------|
| `worker→ras-adapter` | `http` | `streams` | Phase 1 миграции |
| `worker→batch-service` | `http` | `streams` | Phase 3 миграции |

### 3. Новые связи

| Связь | Тип | Направление | Описание |
|-------|-----|-------------|----------|
| `worker→redis` (commands) | `streams` | Worker → Redis | XADD commands:* |
| `redis→ras-adapter` | `streams` | Redis → Adapter | XREADGROUP |
| `redis→odata-adapter` | `streams` | Redis → Adapter | XREADGROUP |
| `redis→designer-agent` | `streams` | Redis → Adapter | XREADGROUP |
| `redis→batch-service` | `streams` | Redis → Adapter | XREADGROUP |
| `*-adapter→redis` (events) | `streams` | Adapter → Redis | XADD events:* |

### 4. Предлагаемый layout

```
Level 0:  [Frontend]
              |
Level 1:  [API Gateway]
              |
Level 2:  [Orchestrator] ←→ [Event Subscriber]
              |                    |
Level 3:  [PostgreSQL]  [Redis]  [Worker]
                           |
                    ┌──────┼──────┬──────┐
                    ↓      ↓      ↓      ↓
Level 4:    [ras-adapter] [odata] [designer] [batch]
```

**Позиции (TB layout):**

```typescript
DEFAULT_SERVICE_POSITIONS: {
  // Level 0
  frontend: { x: 400, y: 50 },

  // Level 1
  'api-gateway': { x: 400, y: 150 },

  // Level 2
  orchestrator: { x: 300, y: 280 },
  'event-subscriber': { x: 500, y: 280 },

  // Level 3
  postgresql: { x: 150, y: 410 },
  redis: { x: 400, y: 410 },
  worker: { x: 650, y: 410 },

  // Level 4: Execution Layer (адаптеры)
  'ras-adapter': { x: 200, y: 540 },
  'odata-adapter': { x: 400, y: 540 },
  'designer-agent': { x: 600, y: 540 },
  'batch-service': { x: 800, y: 540 },
}
```

---

## Визуализация связей

### Цветовая схема соединений

| Тип | Цвет | Hex | Описание |
|-----|------|-----|----------|
| `http` | Синий | `#1890ff` | REST API |
| `queue` | Фиолетовый | `#722ed1` | Redis LIST (legacy) |
| `database` | Бирюзовый | `#13c2c2` | PostgreSQL |
| `pubsub` | Розовый | `#eb2f96` | Redis Pub/Sub |
| `streams` | Зелёный | `#52c41a` | **NEW** Redis Streams |

---

## Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Метрики недоступны для новых сервисов | Medium | High | Проверить /health и /metrics endpoints |
| Сложная топология трудно читается | Low | Medium | Использовать dagre auto-layout |
| Цвета плохо различимы | Low | Low | Выбрать контрастные цвета |

---

## Критерии завершения

- [x] Диаграмма показывает все 11 сервисов
- [x] Связи Worker → адаптеры через Redis Streams (зелёные)
- [x] Легенда содержит все типы соединений
- [x] Метрики собираются для всех сервисов
- [x] Визуально соответствует архитектуре из STATE_MACHINE_MIGRATION_ROADMAP.md

---

## См. также

- [STATE_MACHINE_MIGRATION_ROADMAP.md](./STATE_MACHINE_MIGRATION_ROADMAP.md) — основной roadmap миграции
- [EVENT_DRIVEN_ARCHITECTURE.md](../architecture/EVENT_DRIVEN_ARCHITECTURE.md) — детальный дизайн
- [serviceMesh.ts](../../frontend/src/types/serviceMesh.ts) — текущие типы
