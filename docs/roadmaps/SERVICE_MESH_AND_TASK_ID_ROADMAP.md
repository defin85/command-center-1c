# Roadmap: Service Mesh UI + Переименование task_id

> **Доработка визуализации Service Mesh и удаление legacy naming (celery_task_id)**

**Дата создания:** 2025-12-08
**Дата завершения:** 2025-12-08
**Статус:** ✅ COMPLETE
**Приоритет:** Medium
**Связан с:** CELERY_REMOVAL_ROADMAP.md (Phase 6 completed)

---

## Executive Summary

После полного удаления Celery (Phase 6) остались:
1. **Legacy naming** — поле `celery_task_id` в моделях, API, frontend (30+ файлов)
2. **Некорректная схема Service Mesh** — топология не соответствует реальной архитектуре
3. **UX проблема** — схема обрезается панелями, нет fullscreen режима

---

## 1. Текущие проблемы

### 1.1. Legacy naming `celery_task_id`

| Компонент | Файлы | Количество |
|-----------|-------|------------|
| Django Models | `batch_operation.py`, `task.py` | 2 |
| Django Migrations | `0001_initial.py` | 1 |
| Django Views | `operations.py`, `workflows.py`, `extensions.py`, `clusters.py` | 4 |
| Django Serializers | `serializers.py` | 1 |
| Django Admin | `admin.py` | 1 |
| Workflow Handlers | `odata.py` + tests | 2 |
| OpenAPI Contract | `openapi.yaml` | 1 |
| Frontend Types | `api/generated/*.ts` | 4 |
| Frontend Utils | `operationTransforms.ts` | 1 |
| **Итого** | | **17+ файлов** |

### 1.2. Некорректная топология Service Mesh

**Текущее состояние (скриншот 2025-12-08):**
```
        [API Gateway]
             │
          [Worker]  ──────  [Orchestrator]
         /    |    \
   [RAS] [Batch] [Redis]
```

**Проблемы:**
- ❌ API Gateway → Worker напрямую (неверно — запросы идут через Orchestrator)
- ❌ Orchestrator справа от Worker, а не в центре потока данных
- ❌ Не показан реальный data flow: API Gateway → Orchestrator → Redis → Worker

**Целевая архитектура:**
```
                    [Frontend]
                        │
                   [API Gateway]
                   /    │    \
           [Orch]   [Worker]  [RAS Adapter]
              │        │           │
              │    [Batch Svc]     │
              │        │           │
           [PostgreSQL]    [Redis]
```

### 1.3. UX: Схема обрезается

- Панель навигации слева обрезает часть схемы
- Панель Recent Operations снизу скрывает нижние ноды
- Нет возможности просмотреть схему в fullscreen

---

## 2. Целевое состояние

### 2.1. Переименование поля

```
celery_task_id → task_id
```

- Универсальное название для Go Worker и любого future executor
- Обратная совместимость через миграцию Django

### 2.2. Правильная топология

**SERVICE_TOPOLOGY (prometheus_client.py):**
```python
SERVICE_TOPOLOGY = [
    # Level 0 → 1: Client → Gateway
    ('frontend', 'api-gateway'),

    # Level 1 → 2: Gateway → Services
    ('api-gateway', 'orchestrator'),
    ('api-gateway', 'worker'),
    ('api-gateway', 'ras-adapter'),

    # Level 2: Orchestrator connections
    ('orchestrator', 'postgresql'),
    ('orchestrator', 'redis'),

    # Level 2 → 3: Worker connections
    ('worker', 'redis'),
    ('worker', 'ras-adapter'),
    ('worker', 'batch-service'),

    # Level 3: Batch service
    ('batch-service', 'postgresql'),
]
```

**DEFAULT_SERVICE_POSITIONS (serviceMesh.ts):**
```typescript
export const DEFAULT_SERVICE_POSITIONS = {
  // Level 0: Client
  'frontend': { x: 400, y: 50 },

  // Level 1: Entry Point
  'api-gateway': { x: 400, y: 150 },

  // Level 2: Core Services (horizontal spread)
  'orchestrator': { x: 150, y: 300 },
  'worker': { x: 400, y: 300 },
  'ras-adapter': { x: 650, y: 300 },

  // Level 3: Worker children
  'batch-service': { x: 400, y: 450 },

  // Level 4: Infrastructure (horizontal spread)
  'postgresql': { x: 200, y: 600 },
  'redis': { x: 500, y: 600 },
}
```

### 2.3. Fullscreen режим

- Кнопка "Fullscreen" в правом верхнем углу схемы
- Использовать Fullscreen API браузера
- Скрывать header и sidebar в fullscreen
- ESC для выхода

---

## 3. План реализации

### Phase 1: Fullscreen режим (Frontend) — 1 час

| # | Задача | Файлы |
|---|--------|-------|
| 1.1 | Добавить кнопку Fullscreen | `ServiceMeshTab.tsx` |
| 1.2 | Реализовать Fullscreen API | `hooks/useFullscreen.ts` (new) |
| 1.3 | Стили для fullscreen | `ServiceMesh.module.css` или inline |

**Реализация:**
```tsx
// Кнопка уже есть в правом нижнем углу (zoom controls)
// Добавить рядом кнопку FullscreenOutlined
<Button icon={<FullscreenOutlined />} onClick={toggleFullscreen} />
```

### Phase 2: Исправление топологии — 2 часа

| # | Задача | Файлы |
|---|--------|-------|
| 2.1 | Обновить SERVICE_TOPOLOGY | `prometheus_client.py` |
| 2.2 | Обновить DEFAULT_SERVICE_POSITIONS | `serviceMesh.ts` |
| 2.3 | Проверить отображение всех нод | Manual testing |
| 2.4 | Обновить тесты | `test_prometheus_client.py` |

**Ключевые изменения:**
- Frontend должен появиться на схеме (сейчас не показывается)
- PostgreSQL должен появиться на схеме
- Пересмотреть связи для правильного data flow

### Phase 3: Переименование task_id (Backend) — 3 часа

| # | Задача | Файлы |
|---|--------|-------|
| 3.1 | Создать миграцию Django | `operations/migrations/000X_rename_celery_task_id.py` |
| 3.2 | Обновить модели | `batch_operation.py`, `task.py` |
| 3.3 | Обновить serializers | `serializers.py` |
| 3.4 | Обновить views | `operations.py`, `workflows.py`, `extensions.py`, `clusters.py` |
| 3.5 | Обновить admin | `admin.py` |
| 3.6 | Обновить workflow handlers | `odata.py` |
| 3.7 | Обновить тесты | `test_*.py` |

**Миграция Django:**
```python
# Rename field without data loss
operations.AlterField(
    model_name='batchoperation',
    name='celery_task_id',
    field=models.CharField(...),
)
migrations.RenameField(
    model_name='batchoperation',
    old_name='celery_task_id',
    new_name='task_id',
)
```

### Phase 4: Переименование task_id (OpenAPI + Frontend) — 2 часа

| # | Задача | Файлы |
|---|--------|-------|
| 4.1 | Обновить OpenAPI schema | `contracts/orchestrator/openapi.yaml` |
| 4.2 | Обновить описания (Celery → Go Worker) | `openapi.yaml` |
| 4.3 | Регенерировать клиенты | `./contracts/scripts/generate-all.sh` |
| 4.4 | Обновить operationTransforms | `operationTransforms.ts` |
| 4.5 | Проверить TypeScript типы | `npm run typecheck` |

### Phase 5: Тестирование и документация — 1 час

| # | Задача |
|---|--------|
| 5.1 | Запустить все тесты (pytest, go test, npm test) |
| 5.2 | Manual testing Service Mesh page |
| 5.3 | Обновить CLAUDE.md (если нужно) |
| 5.4 | Обновить CELERY_REMOVAL_ROADMAP.md (отметить завершение) |

---

## 4. Файлы для изменения

### Backend (Django)

```
orchestrator/
├── apps/operations/
│   ├── models/
│   │   ├── batch_operation.py      # celery_task_id → task_id
│   │   └── task.py                 # celery_task_id → task_id
│   ├── migrations/
│   │   └── 000X_rename_task_id.py  # NEW: migration
│   ├── serializers.py              # field rename
│   ├── admin.py                    # field rename
│   └── tests/
│       └── test_*.py               # update references
├── apps/api_v2/views/
│   ├── operations.py               # celery_task_id → task_id
│   ├── workflows.py                # celery_task_id → task_id
│   ├── extensions.py               # celery_task_id → task_id
│   └── clusters.py                 # celery_task_id → task_id
├── apps/templates/workflow/handlers/backends/
│   ├── odata.py                    # celery_task_id → task_id
│   └── tests/test_odata_backend.py
└── apps/operations/services/
    └── prometheus_client.py        # SERVICE_TOPOLOGY update
```

### Frontend

```
frontend/src/
├── types/
│   └── serviceMesh.ts              # DEFAULT_SERVICE_POSITIONS
├── components/service-mesh/
│   └── ServiceMeshTab.tsx          # Fullscreen button
├── hooks/
│   └── useFullscreen.ts            # NEW: fullscreen hook
├── utils/
│   └── operationTransforms.ts      # celery_task_id → task_id
└── api/generated/                  # Regenerated from OpenAPI
```

### Contracts

```
contracts/orchestrator/
└── openapi.yaml                    # Schema + descriptions update
```

---

## 5. Риски

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Breaking API change | Высокая | Версионирование, deprecation notice |
| Migration failure | Низкая | Тестирование на staging, backup |
| Frontend type errors | Средняя | Regenerate + typecheck before commit |

---

## 6. Definition of Done

- [ ] Fullscreen кнопка работает на Service Mesh
- [ ] Все 8 сервисов отображаются на схеме (включая Frontend, PostgreSQL)
- [ ] Топология соответствует реальной архитектуре
- [ ] `celery_task_id` переименован в `task_id` везде
- [ ] Миграция Django применена успешно
- [ ] Все тесты проходят
- [ ] OpenAPI документация обновлена
- [ ] TypeScript компиляция без ошибок

---

## 7. Приоритизация

**Рекомендуемый порядок:**

1. **Phase 1 (Fullscreen)** — быстрый UX fix, независимый
2. **Phase 2 (Топология)** — визуальное исправление
3. **Phase 3-4 (task_id)** — technical debt cleanup

Phases 1-2 можно делать параллельно с Phase 3-4.

---

**Создан:** 2025-12-08
**Автор:** Claude Opus 4.5
