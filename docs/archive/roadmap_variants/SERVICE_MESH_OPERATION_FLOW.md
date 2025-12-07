# Roadmap: Визуализация прохождения операций в Service Mesh

> **Статус:** ✅ Завершено
> **Приоритет:** Высокий
> **Дата создания:** 2025-12-07
> **Связано с:** Sprint 2.1-2.2 (Task Queue & Worker Integration)

---

## Контекст

### Проблема

Service Mesh диаграмма (`/service-mesh`) должна отображать прохождение операций по всем точкам маршрута, но это **не работает**.

**Текущее поведение:**
- Диаграмма показывает топологию сервисов и их метрики (ops/min, latency)
- При запуске операции (например, `sync_cluster`) диаграмма **не реагирует**
- Нет визуализации пути операции через сервисы

**Ожидаемое поведение:**
- При запуске операции подсвечивается путь: `Frontend → API Gateway → Orchestrator → Celery → RAS Adapter`
- Активный узел пульсирует, пройденные узлы отмечены зелёным
- Анимация edges показывает направление потока данных

### Корневая причина

1. **`sync_cluster_task`** обновляет `BatchOperation` в БД напрямую, но **НЕ публикует события** в Redis PubSub
2. **Frontend SSE** (`useOperationStream`) слушает канал `operation:{id}:events`, но события туда не приходят
3. **`ServiceFlowDiagram`** не имеет логики для подсветки активных операций

### Ключевые файлы

| Файл | Текущая роль | Требуемые изменения |
|------|--------------|---------------------|
| `orchestrator/apps/operations/events.py` | `OperationEventPublisher` существует | Добавить `OperationFlowPublisher` |
| `orchestrator/apps/databases/tasks.py` | `sync_cluster_task` без событий | Интегрировать публикацию flow events |
| `orchestrator/apps/operations/consumers.py` | `ServiceMeshConsumer` для metrics | Добавить Redis Pub/Sub listener |
| `frontend/src/hooks/useServiceMesh.ts` | WebSocket для metrics | Обработка `operation_flow_update` |
| `frontend/src/components/service-mesh/ServiceFlowDiagram.tsx` | React Flow диаграмма | Подсветка узлов и edges |

---

## Архитектура решения

### Поток данных

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Единый канал: ws/service-mesh/                   │
├─────────────────────────────────────────────────────────────────────┤
│  Текущие сообщения:                                                 │
│    • metrics_update - метрики сервисов (каждые 2 сек)               │
│                                                                     │
│  НОВЫЕ сообщения:                                                   │
│    • operation_flow_update - прохождение операции по сервисам       │
└─────────────────────────────────────────────────────────────────────┘
```

### Диаграмма компонентов

```
sync_cluster_task ──► OperationFlowPublisher ──► Redis PubSub
                                                "service_mesh:operation_flow"
                                                       │
                                                       ▼
                              ServiceMeshConsumer (subscribe + forward)
                                                       │
                                                       ▼
                              WebSocket ws/service-mesh/
                                                       │
                                                       ▼
                              useServiceMesh hook (activeOperation state)
                                                       │
                                                       ▼
                              ServiceFlowDiagram (highlight nodes/edges)
```

### Формат события `operation_flow_update`

```json
{
  "version": "1.0",
  "type": "operation_flow_update",
  "operation_id": "uuid",
  "timestamp": "2025-12-07T10:30:00Z",

  "flow": {
    "current_service": "celery-worker",
    "path": [
      {"service": "frontend", "status": "completed", "timestamp": "..."},
      {"service": "api-gateway", "status": "completed", "timestamp": "..."},
      {"service": "orchestrator", "status": "completed", "timestamp": "..."},
      {"service": "celery-worker", "status": "active", "timestamp": "..."}
    ],
    "edges": [
      {"from": "frontend", "to": "api-gateway", "status": "completed"},
      {"from": "api-gateway", "to": "orchestrator", "status": "completed"},
      {"from": "orchestrator", "to": "celery-worker", "status": "active"}
    ]
  },

  "operation": {
    "type": "sync_cluster",
    "name": "Синхронизация кластера",
    "status": "processing",
    "progress": 45,
    "message": "Получение списка инфобаз...",
    "metadata": {}
  }
}
```

---

## План реализации

### Фаза 1: Backend - OperationFlowPublisher

**Файл:** `orchestrator/apps/operations/events.py`

**Задачи:**
- [ ] Создать класс `OperationFlowPublisher`
- [ ] Метод `publish_flow(operation_id, current_service, status, path, ...)`
- [ ] Публикация в Redis канал `service_mesh:operation_flow`
- [ ] Построение path и edges из списка сервисов

**Оценка:** 1 час

### Фаза 2: Backend - Интеграция в sync_cluster_task

**Файл:** `orchestrator/apps/databases/tasks.py`

**Задачи:**
- [ ] Импорт `flow_publisher`
- [ ] Публикация при переходе в PROCESSING (current: celery-worker)
- [ ] Публикация при обращении к RAS Adapter (current: ras-adapter)
- [ ] Публикация при COMPLETED/FAILED (current: orchestrator)

**Точки публикации:**
```python
# После получения task из очереди
flow_publisher.publish_flow(operation_id, "celery-worker", "processing",
    path=["frontend", "api-gateway", "orchestrator", "celery-worker"])

# При вызове ClusterService.sync_infobases()
flow_publisher.publish_flow(operation_id, "ras-adapter", "processing",
    path=["frontend", "api-gateway", "orchestrator", "celery-worker", "ras-adapter"])

# При успешном завершении
flow_publisher.publish_flow(operation_id, "orchestrator", "completed",
    path=["frontend", "api-gateway", "orchestrator", "celery-worker", "ras-adapter", "orchestrator"])
```

**Оценка:** 1 час

### Фаза 3: Backend - ServiceMeshConsumer Redis listener

**Файл:** `orchestrator/apps/operations/consumers.py`

**Задачи:**
- [ ] Добавить async task `_listen_operation_flow()`
- [ ] Подписка на Redis канал `service_mesh:operation_flow`
- [ ] Пересылка событий клиентам через WebSocket
- [ ] Graceful shutdown при disconnect

**Оценка:** 1.5 часа

### Фаза 4: Frontend - Типы и hook

**Файлы:**
- `frontend/src/types/serviceMesh.ts`
- `frontend/src/hooks/useServiceMesh.ts`

**Задачи:**
- [ ] Добавить типы: `OperationFlowEvent`, `OperationFlowPath`, `OperationFlowEdge`
- [ ] Состояние `activeOperation` в hook
- [ ] Обработка сообщения `operation_flow_update`
- [ ] Хранение истории последних 10 операций

**Оценка:** 1 час

### Фаза 5: Frontend - Визуализация диаграммы

**Файлы:**
- `frontend/src/components/service-mesh/ServiceFlowDiagram.tsx`
- `frontend/src/components/service-mesh/ServiceNode.tsx`
- `frontend/src/components/service-mesh/ServiceFlowDiagram.css`

**Задачи:**
- [ ] Props `activeOperation` в `ServiceFlowDiagram`
- [ ] Функция `getOperationEdgeStyle()` для стилей edges
- [ ] Функция `getOperationNodeStyle()` для стилей nodes
- [ ] CSS анимации: пульсация активного узла, затемнение неактивных
- [ ] Передача `operationStatus` в `ServiceNode`

**Визуальные эффекты:**
| Статус | Узел | Edge |
|--------|------|------|
| `active` | Синяя пульсация, масштаб 1.05 | Синий, анимированный, толщина 4 |
| `completed` | Зелёная рамка | Зелёный, толщина 3 |
| `failed` | Красная пульсация | Красный, анимированный |
| Не в пути | Затемнённый (opacity 0.4) | Серый, тонкий |

**Оценка:** 2 часа

### Фаза 6: Тестирование

**Задачи:**
- [ ] Запуск sync_cluster и проверка WebSocket событий
- [ ] Проверка визуализации в браузере
- [ ] Тест ошибочного сценария (RAS недоступен)
- [ ] Тест нескольких одновременных операций

**Оценка:** 1 час

---

## Чеклист готовности

### Backend
- [x] `OperationFlowPublisher` создан и протестирован
- [x] `sync_cluster_task` публикует события на каждом этапе
- [x] `ServiceMeshConsumer` пересылает flow events
- [x] Redis канал `service_mesh:operation_flow` работает

### Frontend
- [x] Типы `OperationFlow*` добавлены
- [x] `useServiceMesh` возвращает `activeOperation`
- [x] Диаграмма подсвечивает активный путь
- [x] CSS анимации работают

### Интеграция
- [x] WebSocket получает `operation_flow_update` при sync_cluster
- [x] Визуализация корректно отражает путь операции
- [x] Операция завершается → подсветка сбрасывается

---

## Риски и митигации

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Redis Pub/Sub не доставляет сообщения | Низкая | Fallback polling через REST каждые 5 сек |
| Большой объём событий | Средняя | Rate limiting: max 10 events/sec per operation |
| aioredis блокирует event loop | Низкая | Отдельный asyncio task |
| Потеря событий при reconnect | Средняя | Запрос текущего состояния при подключении |

---

## Альтернативы (отклонены)

### Отдельный WebSocket канал для операций
**Причина отклонения:** Увеличивает количество соединений, усложняет синхронизацию

### SSE вместо WebSocket для flow events
**Причина отклонения:** Уже есть работающий WebSocket, нет смысла добавлять SSE

### Polling REST API для статуса операции
**Причина отклонения:** Задержка 2-5 сек, не real-time визуализация

---

## Ссылки

- [Service Mesh страница](/service-mesh)
- [operations/events.py](../../orchestrator/apps/operations/events.py)
- [databases/tasks.py](../../orchestrator/apps/databases/tasks.py)
- [consumers.py](../../orchestrator/apps/operations/consumers.py)
- [ServiceFlowDiagram.tsx](../../frontend/src/components/service-mesh/ServiceFlowDiagram.tsx)
