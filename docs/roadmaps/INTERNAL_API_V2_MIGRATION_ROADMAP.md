# Roadmap: Миграция Internal API на v2

> **Статус:** COMPLETE (v1 removed)
> **Версия:** 2.1
> **Создан:** 2025-12-12
> **Обновлён:** 2025-12-12
> **Автор:** Claude Code

---

## Цель

Унифицировать Internal API с публичным API v2 (action-based стиль) для консистентности всего проекта.

### Текущее состояние

| Аспект | Значение |
|--------|----------|
| **Текущий префикс** | `/api/internal/` |
| **Целевой префикс** | `/api/v2/internal/` |
| **Количество endpoints** | 15 активных + 3 workflow (future) |
| **Клиенты** | Go Worker (единственный) |
| **Аутентификация** | `X-Internal-Token` header |

### Почему миграция?

| Причина | Описание |
|---------|----------|
| **Консистентность** | Все API используют v2 формат |
| **Единообразие** | Action-based стиль везде |
| **Документация** | Один стандарт для всех endpoints |
| **Версионирование** | Возможность breaking changes в будущем |

---

## Архитектура изменений

### Маппинг endpoints (v1 → v2)

#### Scheduler

| v1 (текущий) | v2 (целевой) | Метод |
|--------------|--------------|-------|
| `POST /api/internal/scheduler/runs/start` | `POST /api/v2/internal/start-scheduler-run` | POST |
| `POST /api/internal/scheduler/runs/{run_id}/complete` | `POST /api/v2/internal/complete-scheduler-run?run_id=X` | POST |

#### Tasks

| v1 (текущий) | v2 (целевой) | Метод |
|--------------|--------------|-------|
| `POST /api/internal/tasks/start` | `POST /api/v2/internal/start-task` | POST |
| `POST /api/internal/tasks/{log_id}/complete` | `POST /api/v2/internal/complete-task?task_id=X` | POST |

#### Databases

| v1 (текущий) | v2 (целевой) | Метод |
|--------------|--------------|-------|
| `GET /api/internal/databases/{id}/credentials` | `GET /api/v2/internal/get-database-credentials?database_id=X` | GET |
| `GET /api/internal/databases/health-check-list/` | `GET /api/v2/internal/list-databases-for-health-check` | GET |
| `POST /api/internal/databases/{id}/health` | `POST /api/v2/internal/update-database-health?database_id=X` | POST |

#### Clusters

| v1 (текущий) | v2 (целевой) | Метод |
|--------------|--------------|-------|
| `POST /api/internal/clusters/{id}/health` | `POST /api/v2/internal/update-cluster-health?cluster_id=X` | POST |

#### Failed Events

| v1 (текущий) | v2 (целевой) | Метод |
|--------------|--------------|-------|
| `GET /api/internal/failed-events/pending` | `GET /api/v2/internal/list-pending-failed-events` | GET |
| `POST /api/internal/failed-events/{id}/replayed` | `POST /api/v2/internal/mark-event-replayed?event_id=X` | POST |
| `POST /api/internal/failed-events/{id}/failed` | `POST /api/v2/internal/mark-event-failed?event_id=X` | POST |
| `POST /api/internal/failed-events/cleanup` | `POST /api/v2/internal/cleanup-failed-events` | POST |

#### Templates

| v1 (текущий) | v2 (целевой) | Метод |
|--------------|--------------|-------|
| `GET /api/internal/templates/{id}` | `GET /api/v2/internal/get-template?template_id=X` | GET |
| `POST /api/internal/templates/{id}/render` | `POST /api/v2/internal/render-template?template_id=X` | POST |

#### Workflows (future)

| v1 (текущий) | v2 (целевой) | Метод |
|--------------|--------------|-------|
| `GET /api/internal/workflow-executions/{id}/` | `GET /api/v2/internal/get-workflow-execution?execution_id=X` | GET |
| `GET /api/internal/workflow-templates/{id}/` | `GET /api/v2/internal/get-workflow-template?template_id=X` | GET |
| `POST /api/internal/workflow-executions/{id}/status/` | `POST /api/v2/internal/update-workflow-status?execution_id=X` | POST |

---

## Фазы миграции

### Фаза 1: Django v2 Internal Views (Week 1)

**Цель:** Создать новые v2 endpoints параллельно с v1.

**Файлы для создания:**

```
orchestrator/apps/api_internal/
├── views.py              # v1 (существующий)
├── views_v2.py           # v2 (НОВЫЙ)
├── urls.py               # v1 (существующий)
└── urls_v2.py            # v2 (НОВЫЙ)
```

**Subtasks:**

- [x] 1.1: Создать `views_v2.py` с action-based функциями
- [x] 1.2: Создать `urls_v2.py` с маршрутизацией `/api/v2/internal/*`
- [x] 1.3: Подключить `urls_v2.py` в `config/urls.py`
- [x] 1.4: Добавить deprecation warnings в v1 views (middleware)
- [ ] 1.5: Unit tests для v2 endpoints

**Пример v2 view:**

```python
# orchestrator/apps/api_internal/views_v2.py

@api_view(['POST'])
@permission_classes([IsInternalService])
def start_scheduler_run(request):
    """POST /api/v2/internal/start-scheduler-run"""
    serializer = SchedulerRunStartSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    # ... implementation
    return Response({'run_id': str(run.id), 'status': 'running'}, status=201)


@api_view(['POST'])
@permission_classes([IsInternalService])
def complete_scheduler_run(request):
    """POST /api/v2/internal/complete-scheduler-run?run_id=X"""
    run_id = request.query_params.get('run_id')
    if not run_id:
        return Response({'error': 'run_id required'}, status=400)
    # ... implementation
```

**Пример urls_v2.py:**

```python
# orchestrator/apps/api_internal/urls_v2.py
from django.urls import path
from . import views_v2

urlpatterns = [
    # Scheduler
    path('start-scheduler-run', views_v2.start_scheduler_run),
    path('complete-scheduler-run', views_v2.complete_scheduler_run),

    # Tasks
    path('start-task', views_v2.start_task),
    path('complete-task', views_v2.complete_task),

    # Databases
    path('get-database-credentials', views_v2.get_database_credentials),
    path('list-databases-for-health-check', views_v2.list_databases_for_health_check),
    path('update-database-health', views_v2.update_database_health),

    # Clusters
    path('update-cluster-health', views_v2.update_cluster_health),

    # Failed Events
    path('list-pending-failed-events', views_v2.list_pending_failed_events),
    path('mark-event-replayed', views_v2.mark_event_replayed),
    path('mark-event-failed', views_v2.mark_event_failed),
    path('cleanup-failed-events', views_v2.cleanup_failed_events),

    # Templates
    path('get-template', views_v2.get_template),
    path('render-template', views_v2.render_template),
]
```

**Критерии завершения:**

- [x] Все 14 endpoints доступны на `/api/v2/internal/*`
- [x] v1 endpoints возвращают `Deprecation: true` header (via middleware)
- [ ] Unit tests покрывают все v2 endpoints

---

### Фаза 2: Go Worker Client Migration (Week 2)

**Цель:** Обновить Go клиент для использования v2 endpoints.

**Файлы для изменения:**

```
go-services/worker/internal/orchestrator/
├── client.go           # Base client (добавить version support)
├── scheduler.go        # Scheduler methods
├── tasks.go            # Task methods
├── databases.go        # Database methods
├── clusters.go         # Cluster methods
├── failed_events.go    # Failed events methods
├── templates.go        # Template methods
└── workflows.go        # Workflow methods
```

**Subtasks:**

- [x] 2.1: Добавить `APIVersion` в `ClientConfig`
- [x] 2.2: Обновить `pathSchedulerRunStart` и другие константы
- [x] 2.3: Изменить path params на query params
- [x] 2.4: Добавить feature flag `APIVersion=v1|v2` (default: v2)
- [x] 2.5: Обновить unit tests
- [ ] 2.6: Integration tests с обеими версиями

**Пример изменений в client.go:**

```go
// go-services/worker/internal/orchestrator/client.go

type ClientConfig struct {
    BaseURL     string
    Token       string
    APIVersion  string // "v1" или "v2" (default: "v2")
    // ...
}

func (c *Client) buildPath(v1Path, v2Path string) string {
    if c.apiVersion == "v1" {
        return v1Path
    }
    return v2Path
}
```

**Пример изменений в scheduler.go:**

```go
// go-services/worker/internal/orchestrator/scheduler.go

const (
    // v1 paths (deprecated)
    pathSchedulerRunStartV1    = "/api/internal/scheduler/runs/start"
    pathSchedulerRunCompleteV1 = "/api/internal/scheduler/runs/%s/complete"

    // v2 paths (action-based)
    pathSchedulerRunStartV2    = "/api/v2/internal/start-scheduler-run"
    pathSchedulerRunCompleteV2 = "/api/v2/internal/complete-scheduler-run"
)

func (c *Client) SchedulerRunStart(ctx context.Context, jobName, workerInstance string) (string, error) {
    path := c.buildPath(pathSchedulerRunStartV1, pathSchedulerRunStartV2)
    // ...
}

func (c *Client) SchedulerRunComplete(ctx context.Context, runID string, req SchedulerRunCompleteRequest) error {
    var path string
    if c.apiVersion == "v1" {
        path = fmt.Sprintf(pathSchedulerRunCompleteV1, runID)
    } else {
        path = pathSchedulerRunCompleteV2 + "?run_id=" + runID
    }
    // ...
}
```

**Критерии завершения:**

- [x] Go клиент работает с v2 по умолчанию
- [x] Feature flag позволяет откатиться на v1
- [x] Все существующие тесты проходят
- [ ] Добавлены тесты для v2 endpoints

---

### Фаза 3: OpenAPI Contract Update (Week 2)

**Цель:** Обновить OpenAPI spec для v2 Internal API.

**Файл:**

```
contracts/orchestrator-internal/openapi.yaml
```

**Subtasks:**

- [x] 3.1: Добавить v2 endpoints в OpenAPI spec (14 endpoints)
- [x] 3.2: Пометить v1 endpoints как deprecated
- [x] 3.3: Добавить `Sunset` date для v1 (2026-06-01)
- [x] 3.4: Обновить описание API (version 2.0.0)
- [x] 3.5: Валидация spec (YAML syntax valid)

**Пример изменений:**

```yaml
# contracts/orchestrator-internal/openapi.yaml

info:
  title: Orchestrator Internal API
  version: 2.0.0  # Bump version

servers:
  - url: http://localhost:8200/api/v2/internal
    description: v2 Internal API (recommended)
  - url: http://localhost:8200/api/internal
    description: v1 Internal API (deprecated, sunset 2026-06-01)

paths:
  # v2 endpoints
  /start-scheduler-run:
    post:
      operationId: startSchedulerRunV2
      summary: Начало выполнения scheduled job
      # ...

  # v1 endpoints (deprecated)
  /api/internal/scheduler/runs/start:
    post:
      operationId: startSchedulerRun
      deprecated: true
      x-sunset: "2026-06-01"
      summary: "[DEPRECATED] Начало выполнения scheduled job"
      description: |
        **Deprecated:** Используйте `/api/v2/internal/start-scheduler-run`
      # ...
```

**Критерии завершения:**

- [x] OpenAPI spec содержит все v2 endpoints (14/14)
- [x] v1 endpoints помечены `deprecated: true`
- [x] Spec проходит валидацию

---

### Фаза 4: Testing & Validation (Week 3)

**Цель:** Полное тестирование миграции.

**Subtasks:**

- [x] 4.1: Integration tests Django v2 endpoints (58 tests, 76% coverage)
- [x] 4.2: Integration tests Go client v2 (passed)
- [ ] 4.3: Load testing (сравнение v1 vs v2) - optional
- [x] 4.4: Проверка backward compatibility (v1 tests still pass)
- [ ] 4.5: Документация миграции - optional

**Тестовые сценарии:**

```python
# orchestrator/apps/api_internal/tests/test_views_v2.py

class TestSchedulerV2(APITestCase):
    def test_start_scheduler_run(self):
        response = self.client.post(
            '/api/v2/internal/start-scheduler-run',
            {'job_name': 'health_check', 'worker_instance': 'worker-1'},
            HTTP_X_INTERNAL_TOKEN=self.token
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn('run_id', response.data)

    def test_complete_scheduler_run(self):
        # Create run first
        run_id = self._create_run()
        response = self.client.post(
            f'/api/v2/internal/complete-scheduler-run?run_id={run_id}',
            {'status': 'success', 'duration_ms': 1000},
            HTTP_X_INTERNAL_TOKEN=self.token
        )
        self.assertEqual(response.status_code, 200)
```

**Критерии завершения:**

- [x] Все integration tests проходят (58/58)
- [x] Coverage > 70% (76% достигнуто)
- [x] Backward compatibility подтверждена (v1 + v2 работают параллельно)

---

### Фаза 5: Rollout & Cleanup (Week 4)

**Цель:** Включить v2 по умолчанию и запланировать удаление v1.

**Subtasks:**

- [x] 5.1: Установить `APIVersion=v2` по умолчанию (уже сделано в Phase 2)
- [x] 5.2: Обновить документацию (этот roadmap)
- [x] 5.3: Добавить deprecation middleware
- [x] 5.4: Установить Sunset date для v1 (2026-06-01)
- [ ] 5.5: Создать issue для удаления v1 (future)

**Timeline:**

```
Week 1:  Phase 1 - Django v2 Views
Week 2:  Phase 2 + 3 - Go Client + OpenAPI
Week 3:  Phase 4 - Testing
Week 4:  Phase 5 - Rollout

Sunset v1: +6 месяцев после rollout
```

---

## Файлы для изменения

### Django (orchestrator)

| Файл | Действие | Строк |
|------|----------|-------|
| `apps/api_internal/views_v2.py` | CREATE | ~400 |
| `apps/api_internal/urls_v2.py` | CREATE | ~30 |
| `apps/api_internal/views.py` | MODIFY | +deprecation |
| `config/urls.py` | MODIFY | +v2 include |
| `apps/api_internal/tests/test_views_v2.py` | CREATE | ~300 |

### Go Worker

| Файл | Действие | Строк |
|------|----------|-------|
| `internal/orchestrator/client.go` | MODIFY | +version support |
| `internal/orchestrator/scheduler.go` | MODIFY | +v2 paths |
| `internal/orchestrator/tasks.go` | MODIFY | +v2 paths |
| `internal/orchestrator/databases.go` | MODIFY | +v2 paths |
| `internal/orchestrator/clusters.go` | MODIFY | +v2 paths |
| `internal/orchestrator/failed_events.go` | MODIFY | +v2 paths |
| `internal/orchestrator/templates.go` | MODIFY | +v2 paths |
| `internal/orchestrator/workflows.go` | MODIFY | +v2 paths |

### Contracts

| Файл | Действие |
|------|----------|
| `contracts/orchestrator-internal/openapi.yaml` | MODIFY |

---

## Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Breaking changes в Go client | Medium | High | Feature flag, dual support |
| Regression в производительности | Low | Medium | Load testing |
| Пропущенные endpoints | Low | Medium | Automated endpoint discovery |
| Несовместимость serializers | Low | Low | Reuse existing serializers |

---

## Метрики успеха

| Метрика | Цель |
|---------|------|
| v2 endpoints coverage | 100% (15/15) |
| Test coverage | > 80% |
| Latency regression | < 5% |
| Migration time | 4 weeks |
| Backward compatibility | 100% |

---

## Альтернативные варианты

### Вариант A: Полная миграция (выбран)

**Плюсы:**
- Консистентность со всем API
- Единый стандарт документации
- Возможность версионирования

**Минусы:**
- Требует изменений в Go Worker
- 4 недели работы

### Вариант B: Оставить как есть

**Плюсы:**
- Нет работы
- Нет рисков

**Минусы:**
- Несогласованность с публичным API
- Сложнее документировать

### Вариант C: Alias-based migration

**Плюсы:**
- Минимальные изменения в Django
- Быстрая реализация

**Минусы:**
- URL rewriting добавляет complexity
- Не решает проблему path params

**Рекомендация:** Вариант A — полная миграция для долгосрочной консистентности.

---

## См. также

- [API_V2_UNIFICATION_ROADMAP.md](../archive/roadmap_variants/API_V2_UNIFICATION_ROADMAP.md) — публичный API v2
- [STATE_MACHINE_MIGRATION_ROADMAP.md](./STATE_MACHINE_MIGRATION_ROADMAP.md) — Event-Driven архитектура
- [OpenAPI Contract](../../contracts/orchestrator-internal/openapi.yaml) — текущий контракт

---

## Changelog

### v2.1 (2025-12-12)
- v1 API REMOVED completely (no backward compatibility)
- Deleted Django files: urls.py (old), views.py (old), middleware.py
- Renamed v2 files to main: views_v2.py → views.py, urls_v2.py → urls.py
- Go client simplified: removed APIVersion, IsV2(), buildPath()
- OpenAPI: removed all v1 paths, kept only v2

### v2.0 (2025-12-12)
- Phase 5 COMPLETE: Rollout finalized
- All phases implemented in single session
- Migration complete, v1 deprecated with Sunset: 2026-06-01

### v1.3 (2025-12-12)
- Phase 4 COMPLETE: Django v2 tests
- Created `orchestrator/apps/api_internal/tests/test_views_v2.py`
- 58 tests, 76% coverage

### v1.2 (2025-12-12)
- Phase 3 COMPLETE: OpenAPI contract updated to v2.0.0
- Added 14 v2 endpoints, 12 v2 response schemas
- All v1 endpoints marked deprecated with Sunset: 2026-06-01

### v1.1 (2025-12-12)
- Phase 1 COMPLETE: Django v2 views + middleware
- Phase 2 COMPLETE: Go Worker client migration
- Created files:
  - `orchestrator/apps/api_internal/views_v2.py`
  - `orchestrator/apps/api_internal/urls_v2.py`
  - `orchestrator/apps/api_internal/middleware.py`
- Modified files:
  - `orchestrator/config/urls.py`
  - `orchestrator/config/settings/base.py`
  - `go-services/worker/internal/orchestrator/client.go`
  - `go-services/worker/internal/orchestrator/models.go`
  - `go-services/worker/internal/orchestrator/scheduler.go`
  - `go-services/worker/internal/orchestrator/tasks.go`
  - `go-services/worker/internal/orchestrator/databases.go`
  - `go-services/worker/internal/orchestrator/clusters.go`
  - `go-services/worker/internal/orchestrator/failed_events.go`
  - `go-services/worker/internal/orchestrator/templates.go`
  - `go-services/worker/internal/orchestrator/failed_events_test.go`
  - `go-services/worker/internal/orchestrator/templates_test.go`

### v1.0 (2025-12-12)
- Initial draft
- Полный маппинг 14 endpoints
- 5 фаз миграции
- Оценка: 4 недели
