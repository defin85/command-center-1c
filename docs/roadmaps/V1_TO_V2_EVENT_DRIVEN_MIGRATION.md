# V1 → V2 и Event-Driven Migration Roadmap

> Полная миграция с REST API v1 на v2 и переход на Event-Driven архитектуру через Redis Streams

**Статус:** ✅ P0, P1, P2, P3 ЗАВЕРШЕНЫ | P4 (follow-up) в очереди
**Приоритет:** Low (P4 optional cleanup)
**Создан:** 2025-12-15
**Обновлён:** 2025-12-15 (v1.6)

---

## Executive Summary

Проект находится в состоянии "dual-mode" — часть компонентов уже использует Event-Driven архитектуру через Redis Streams, но остаются критичные места с прямыми HTTP вызовами и legacy v1 API endpoints. Данный roadmap описывает план полной унификации.

### Ключевые цели

1. **Удалить все `/api/v1/*` endpoints** — переход на action-based v2 API
2. **Заменить HTTP-sync вызовы на Redis Streams** — для inter-service коммуникации
3. **Унифицировать Timeline трассировку** — все операции должны записывать события
4. **Очистить legacy код** — удалить архивные компоненты

---

## Текущее состояние

### Что уже готово (✅)

| Компонент | Статус |
|-----------|--------|
| Redis Streams инфраструктура | ✅ 10+ streams определено |
| Event Subscriber (Django) | ✅ Consumer Groups работают |
| Worker dual-mode | ✅ Streams + HTTP fallback |
| RAS-Adapter v2 API | ✅ v1 endpoints удалены |
| API Gateway v2 routing | ✅ `/api/v2/*` основной путь |
| Timeline трассировка (Go) | ✅ `shared/tracing/timeline.go` |
| **sync_cluster Timeline events** | ✅ `cluster.sync.*` события |
| **Frontend .started/.processing status** | ✅ EventStatus + STATUS_COLORS |
| **Credentials fetch для RAS** | ✅ `shared/credentials/` + ras-adapter handlers |
| **Transport key validation** | ✅ Unified hex encoding в worker + ras-adapter |

### Что требует миграции (🔴)

| Компонент | Проблема | Файл |
|-----------|----------|------|
| ~~Worker → Orchestrator~~ | ~~HTTP GET credentials~~ | ~~✅ Решено: ras-adapter fetch от Orchestrator~~ |
| Worker → Orchestrator | HTTP GET cluster-info | `worker/internal/processor/cluster_resolver.go:198` |
| Batch-Service → Orchestrator | HTTP POST callback | `batch-service/internal/infrastructure/django/client.go:43` |
| ~~Worker sync_cluster~~ | ~~Нет timeline events~~ | ~~✅ Добавлены `cluster.sync.*` события~~ |
| Django databases API | v1 endpoints активны | `orchestrator/apps/databases/urls.py` |
| Batch-Service API | v1 endpoints активны | `batch-service/internal/api/router.go` |

---

## Архитектура: AS-IS vs TO-BE

### AS-IS (Текущая — смешанная)

```
┌─────────────┐     HTTP /api/v1/credentials     ┌──────────────┐
│   Worker    │ ──────────────────────────────→  │ Orchestrator │
│             │     HTTP /api/v1/cluster-info    │              │
│             │ ──────────────────────────────→  │              │
└─────────────┘                                   └──────────────┘
       │
       │ HTTP /api/v2/*
       ▼
┌─────────────┐
│ RAS-Adapter │  ← Прямой HTTP вызов, timeline НЕ записывается
└─────────────┘

┌───────────────┐   HTTP /api/v1/callback     ┌──────────────┐
│ Batch-Service │ ─────────────────────────→  │ Orchestrator │
└───────────────┘                              └──────────────┘
```

### TO-BE (Целевая — Event-Driven)

```
┌─────────────┐                                 ┌──────────────┐
│   Worker    │                                 │ Orchestrator │
│             │  commands:worker:get-credentials│              │
│             │ ────────────────────────────→   │              │
│             │  events:orchestrator:credentials│              │
│             │ ←────────────────────────────   │              │
└─────────────┘                                 └──────────────┘
       │
       │ commands:ras-adapter:*
       ▼
┌─────────────┐
│ RAS-Adapter │  ← Event-driven, timeline записывается автоматически
│             │
│             │  events:ras-adapter:completed
└─────────────┘ ────────────────────────────→ Worker/Orchestrator

┌───────────────┐  events:batch-service:*     ┌──────────────┐
│ Batch-Service │ ─────────────────────────→  │ Orchestrator │
└───────────────┘  (уже работает!)            └──────────────┘
```

---

## Фазы миграции

### Phase 1: Event-Driven для критичных HTTP вызовов

**Цель:** Заменить синхронные HTTP вызовы между сервисами на Redis Streams

#### 1.1 Credentials через Streams

**Текущее:** Worker делает HTTP GET к Orchestrator для получения credentials базы

**Целевое:**
```
Worker                          Redis                           Orchestrator
  │                               │                                   │
  │ XADD commands:orchestrator:   │                                   │
  │      get-credentials          │                                   │
  ├──────────────────────────────→│                                   │
  │                               │ XREAD (blocking)                  │
  │                               │←──────────────────────────────────┤
  │                               │                                   │
  │                               │ Process & respond                 │
  │                               │──────────────────────────────────→│
  │                               │                                   │
  │                               │ XADD events:orchestrator:         │
  │                               │      credentials-response         │
  │                               │←──────────────────────────────────┤
  │ XREAD (with timeout)          │                                   │
  │←──────────────────────────────┤                                   │
```

**Задачи:**
- [ ] Создать stream `commands:orchestrator:get-credentials`
- [ ] Создать stream `events:orchestrator:credentials-response`
- [ ] Django: добавить handler в Event Subscriber
- [ ] Worker: заменить HTTP client на Stream client
- [ ] Worker: добавить timeout и fallback на HTTP (graceful degradation)

**Файлы для изменения:**
```
go-services/worker/internal/credentials/client.go        # Основной клиент
go-services/worker/internal/credentials/stream_client.go # Новый Stream клиент
orchestrator/apps/operations/event_subscriber.py         # Новый handler
orchestrator/apps/databases/services/credentials.py      # Service для ответа
```

#### 1.2 Cluster Info через Streams ✅ ЗАВЕРШЕНО

**Текущее:** ~~Worker делает HTTP GET для получения cluster-info перед операциями~~

**Реализовано:** Streams-first с HTTP fallback
- Stream `commands:orchestrator:get-cluster-info` для запросов
- Stream `events:orchestrator:cluster-info-response` для ответов
- Django handler в event_subscriber.py
- ClusterInfoWaiter с request-response паттерном
- Feature flag `USE_STREAMS_CLUSTER_INFO` (default: true)

**Задачи:**
- [x] Создать stream `commands:orchestrator:get-cluster-info`
- [x] Создать stream `events:orchestrator:cluster-info-response`
- [x] Django: добавить handler `handle_get_cluster_info()`
- [x] Worker: добавить `cluster_info_waiter.go` с Streams поддержкой
- [x] HTTP fallback при timeout (5 секунд)

**Файлы изменены:**
```
go-services/shared/events/channels.go                    # Константы streams
go-services/worker/internal/processor/cluster_resolver.go
go-services/worker/internal/processor/cluster_info_waiter.go  # Новый
orchestrator/apps/operations/event_subscriber.py
```

#### 1.3 Batch-Service Callback через Streams ✅ ЗАВЕРШЕНО

**Текущее:** ~~Batch-service делает HTTP POST callback в Orchestrator~~

**Реализовано:** HTTP callback удалён, только Event-Driven через Redis Streams

**Задачи:**
- [x] Удалить HTTP callback client в batch-service (`django/client.go`)
- [x] Убедиться что все события публикуются в streams (install-started, installed, failed)
- [x] Django: убрать `/api/v1/extensions/installation/callback/` endpoint

**Файлы удалены:**
```
go-services/batch-service/internal/infrastructure/django/client.go      # УДАЛЁН
go-services/batch-service/internal/infrastructure/django/client_test.go # УДАЛЁН
orchestrator/apps/databases/tests/test_extension_callback.py            # УДАЛЁН
```

**Файлы изменены:**
```
orchestrator/apps/databases/urls.py   # Удалён callback endpoint
orchestrator/apps/databases/views.py  # Удалена функция installation_callback
```

---

### Phase 2: Timeline трассировка для всех операций

**Цель:** Все операции должны записывать события в timeline для визуализации в Service Mesh

#### 2.1 sync_cluster Timeline ✅ ЗАВЕРШЕНО

**Текущее:** ~~`sync_cluster.go` не записывает timeline events при вызове RAS-Adapter~~

**Реализовано:** Timeline events добавлены с naming convention `cluster.sync.*`

**Задачи:**
- [x] Добавить timeline events в `processSyncCluster()`
- [x] События: `cluster.sync.started`, `cluster.sync.resolving.started`, `cluster.sync.fetching.started`, `cluster.sync.completed`, `cluster.sync.failed`
- [x] Metadata типы: `map[string]interface{}` для сохранения числовых типов
- [x] `duration_ms` в failed событиях

**Файлы для изменения:**
```
go-services/worker/internal/processor/sync_cluster.go
```

**Пример кода:**
```go
func (p *TaskProcessor) processSyncCluster(ctx context.Context, msg *models.OperationMessage) *models.OperationResultV2 {
    // Добавить в начале:
    p.timeline.Record(ctx, msg.OperationID, "sync_cluster.started", map[string]string{
        "cluster_id": payload.ClusterID,
    })

    // После ListClusters:
    p.timeline.Record(ctx, msg.OperationID, "ras.list_clusters.completed", map[string]string{
        "ras_server": payload.RASServer,
    })

    // После ListInfobases:
    p.timeline.Record(ctx, msg.OperationID, "ras.list_infobases.completed", map[string]string{
        "count": fmt.Sprintf("%d", infobasesResp.Count),
    })

    // В конце:
    p.timeline.Record(ctx, msg.OperationID, "sync_cluster.completed", map[string]string{
        "infobases_count": fmt.Sprintf("%d", infobasesResp.Count),
    })
}
```

#### 2.2 Frontend: Добавить `.started` статус ✅ ЗАВЕРШЕНО

**Текущее:** ~~`getEventStatus()` не распознаёт `.started` события~~

**Реализовано:**
- EventStatus тип расширен: `'processing'` для `.started` и `.processing` суффиксов
- STATUS_COLORS: `processing: '#faad14'` (оранжевый/amber)
- EVENT_LABELS: добавлены метки для `cluster.sync.*` событий

**Задачи:**
- [x] Добавить `.started` → `'processing'` (оранжевый цвет)
- [x] Обновить `EVENT_LABELS` для новых событий
- [x] Добавить `STATUS_COLORS.processing`

**Файлы изменены:**
```
frontend/src/types/operationTimeline.ts      # EventStatus type
frontend/src/utils/timelineTransforms.ts     # getEventStatus() + EVENT_LABELS
frontend/src/components/service-mesh/WaterfallTimeline.tsx  # STATUS_COLORS
```

#### 2.3 Orchestrator Timeline Events

**Текущее:** Orchestrator не записывает события при создании операций

**Целевое:** Добавить события `orchestrator.created`, `orchestrator.completed`

**Задачи:**
- [ ] Создать Redis client для timeline в Django
- [ ] Добавить запись при создании BatchOperation
- [ ] Добавить запись при завершении операции

**Файлы для изменения:**
```
orchestrator/apps/operations/services/timeline_writer.py  # Новый
orchestrator/apps/operations/services/operation_service.py
orchestrator/apps/operations/event_subscriber.py
```

---

### Phase 3: Миграция V1 → V2 API Endpoints

**Цель:** Удалить все `/api/v1/*` endpoints, оставить только `/api/v2/*`

#### 3.1 Django Orchestrator

**V1 endpoints для удаления:**

| Endpoint | Замена v2 | Action |
|----------|-----------|--------|
| `GET /api/v1/databases/` | `POST /api/v2/databases/list-databases/` | Удалить |
| `GET /api/v1/databases/{id}/` | `POST /api/v2/databases/get-database/` | Удалить |
| `GET /api/v1/databases/{id}/credentials` | Stream-based | Удалить |
| `GET /api/v1/databases/{id}/cluster-info/` | Stream-based | Удалить |
| `POST /api/v1/databases/batch-install-extension/` | `POST /api/v2/operations/execute-batch/` | Удалить |
| `POST /api/v1/extensions/installation/callback/` | Stream events | Удалить |
| `GET /api/v1/operations/{id}/stream` | WebSocket `/ws/operations/` | Удалить |

**Задачи:**
- [ ] Убедиться что все v2 endpoints работают
- [ ] Обновить Frontend на v2 (если не обновлён)
- [ ] Удалить v1 URL patterns из `urls.py`
- [ ] Удалить v1 views

**Файлы для изменения:**
```
orchestrator/apps/databases/urls.py
orchestrator/apps/databases/views.py
orchestrator/apps/operations/urls.py
orchestrator/apps/operations/views.py
```

#### 3.2 Batch-Service

**V1 endpoints для удаления/переименования:**

| Текущий | Новый v2 | Примечание |
|---------|----------|-----------|
| `POST /api/v1/extensions/install` | `POST /api/v2/install-extension` | Action-based |
| `POST /api/v1/extensions/batch-install` | `POST /api/v2/batch-install-extensions` | Action-based |
| `POST /api/v1/extensions/delete` | `POST /api/v2/delete-extension` | Action-based |
| `GET /api/v1/extensions/list` | `GET /api/v2/list-extensions` | Action-based |
| `POST /api/v1/extensions/rollback` | `POST /api/v2/rollback-extension` | Action-based |
| `POST /api/v1/extensions/storage/upload` | `POST /api/v2/upload-extension` | Action-based |
| `GET /api/v1/extensions/storage` | `GET /api/v2/list-storage` | Action-based |

**Задачи:**
- [ ] Создать v2 router group в `router.go`
- [ ] Дублировать handlers на v2 пути
- [ ] Обновить OpenAPI spec
- [ ] Deprecation period (30 дней)
- [ ] Удалить v1 routes

**Файлы для изменения:**
```
go-services/batch-service/internal/api/router.go
go-services/batch-service/internal/api/handlers/*.go  # Обновить swagger аннотации
contracts/batch-service/openapi.yaml
```

#### 3.3 API Gateway

**V1 routes для удаления:**

| Route | Статус |
|-------|--------|
| `/api/v1/public/status` | Заменить на `/api/v2/get-status` |
| `/api/v1/operations/*` | Прокси на Orchestrator v2 |

**Задачи:**
- [ ] Обновить proxy rules
- [ ] Добавить deprecation headers для v1
- [ ] Удалить v1 routes после sunset date

**Файлы для изменения:**
```
go-services/api-gateway/internal/routes/routes.go
contracts/api-gateway/openapi.yaml
```

---

### Phase 4: Cleanup и документация

#### 4.1 Удаление архивного кода

**Задачи:**
- [ ] Удалить `go-services/archive/cluster-service/`
- [ ] Очистить неиспользуемые imports
- [ ] Удалить deprecated тесты

#### 4.2 Обновление документации

**Задачи:**
- [ ] Архивировать `docs/roadmaps/API_V2_UNIFICATION_ROADMAP.md`
- [ ] Обновить `docs/REST_API_COMPARISON.md` — удалить v1
- [ ] Обновить `docs/FRONTEND_API_V2_MAPPING.md` — пометить как completed
- [ ] Обновить README.md всех сервисов
- [ ] Обновить OpenAPI specs — удалить v1 paths

#### 4.3 Обновление контрактов

**Задачи:**
- [ ] `contracts/api-gateway/openapi.yaml` — удалить v1 paths
- [ ] `contracts/orchestrator/openapi.yaml` — проверить полноту v2
- [ ] `contracts/batch-service/openapi.yaml` — создать v2 spec
- [ ] Regenerate API clients

---

## Новые Redis Streams (Phase 1)

### Request-Response Streams

```yaml
# Credentials
commands:orchestrator:get-credentials:
  format:
    correlation_id: string  # Для матчинга ответа
    operation_id: string
    database_id: string

events:orchestrator:credentials-response:
  format:
    correlation_id: string
    database_id: string
    odata_url: string
    username: string
    password: string  # encrypted
    success: bool
    error: string?

# Cluster Info
commands:orchestrator:get-cluster-info:
  format:
    correlation_id: string
    database_id: string

events:orchestrator:cluster-info-response:
  format:
    correlation_id: string
    database_id: string
    cluster_id: string
    ras_server: string
    ras_cluster_uuid: string
    success: bool
    error: string?
```

### Consumer Groups

```yaml
# Orchestrator слушает commands
orchestrator-commands-group:
  streams:
    - commands:orchestrator:get-credentials
    - commands:orchestrator:get-cluster-info
  consumers:
    - orchestrator-1
    - orchestrator-2  # Для HA

# Worker слушает responses
worker-responses-group:
  streams:
    - events:orchestrator:credentials-response
    - events:orchestrator:cluster-info-response
  consumers:
    - worker-{id}  # Каждый worker свой consumer
```

---

## Риски и митигация

| Риск | Вероятность | Импакт | Митигация |
|------|-------------|--------|-----------|
| Timeout при Stream request/response | Medium | High | Fallback на HTTP с логированием |
| Потеря сообщений в Streams | Low | High | Consumer Groups + ACK + DLQ |
| Breaking changes для Frontend | Medium | Medium | Версионирование API, deprecation headers |
| Увеличение latency | Medium | Low | Async где возможно, кеширование |

---

## Метрики успеха

| Метрика | Текущее | Целевое |
|---------|---------|---------|
| V1 endpoints | 15+ | 0 |
| HTTP inter-service calls | 3 | 0 (только через Gateway) |
| Timeline coverage | ~60% | 100% |
| Event-driven operations | ~70% | 100% |

---

## Приоритет задач

### P0 (Критичные — делать первыми) ✅ ЗАВЕРШЕНО
1. ~~Timeline events для sync_cluster~~ ✅ `cluster.sync.*` события добавлены
2. ~~Frontend: распознавание `.started` статуса~~ ✅ EventStatus + STATUS_COLORS + EVENT_LABELS
3. ~~Credentials для RAS операций~~ ✅ `shared/credentials/` + ras-adapter fetch от Orchestrator

### P1 (Высокий — после P0) ✅ ЗАВЕРШЕНО
4. ~~Cluster-info через Streams~~ ✅ Streams-first с HTTP fallback
5. ~~Удаление batch-service HTTP callback~~ ✅ HTTP callback удалён
6. ~~Django v1 endpoints deprecation~~ ✅ V1 удалены из OpenAPI spec (Django уже на v2)

### P2 (Средний — после P1) ✅ ЗАВЕРШЕНО
7. ~~Batch-service v2 API migration~~ ✅ Flat internal API (удалено версионирование)
8. ~~API Gateway cleanup~~ ✅ Удалён legacy ProxyToOrchestrator, flat RAS routes
9. ~~Documentation update~~ ✅ Roadmap обновлён

### P3 (Низкий — cleanup) ✅ ЗАВЕРШЕНО
10. ~~Archive deletion~~ ✅ Удалено: cluster-service (archive/), unused batch-service handlers
11. ~~Test cleanup~~ ✅ Архивировано: 9 test files в tests/archive/v1_api_tests/
12. ~~OpenAPI regeneration~~ ✅ Specs validated, clients regenerated (no changes needed)

### P4 (Follow-up — dead code removal)
13. [ ] Удалить мёртвые ViewSets из Django apps

**Проблема:** ViewSets зарегистрированы в `urls.py` файлах приложений, но эти URL файлы НЕ подключены в `config/urls.py`. Функционал дублируется в v2 API.

**Файлы для удаления/очистки:**

| Файл | Что удалить | Строк |
|------|-------------|-------|
| `apps/databases/views.py` | `DatabaseViewSet`, `DatabaseGroupViewSet`, `ClusterViewSet` | ~700 |
| `apps/databases/urls.py` | Весь файл (router + urlpatterns) | ~37 |
| `apps/operations/views.py` | Legacy views с v1 комментариями | ~100 |
| `apps/templates/views.py` | Legacy template validation views | ~100 |
| `apps/templates/urls.py` | Весь файл | ~10 |
| `apps/templates/workflow/views.py` | Legacy workflow views | ~200 |

**Функции-standalone которые нужно проверить:**
- `batch_install_extension()` — возможно используется
- `list_extension_storage()`, `upload_extension()`, `delete_extension_storage()` — проверить

**Оценка:** ~1000+ строк мёртвого кода

**Риски:** Низкие — код не подключён, функционал в v2 API

---

## Связанные документы

- `docs/roadmaps/API_V2_UNIFICATION_ROADMAP.md` — предыдущий roadmap (частично выполнен)
- `docs/architecture/EVENT_DRIVEN_ARCHITECTURE.md` — архитектура событий
- `docs/ODATA_INTEGRATION.md` — интеграция с 1C
- `contracts/` — OpenAPI спецификации

---

**Версия:** 1.4
**Автор:** AI Assistant
**Ревью:** Требуется

---

## Changelog

### v1.6 (2025-12-15)
- Добавлена задача P4-13: удаление мёртвых ViewSets (~1000+ строк)
- Обнаружен dead code: ViewSets в apps/ не подключены к config/urls.py

### v1.5 (2025-12-15) — МИГРАЦИЯ ЗАВЕРШЕНА
- ✅ P3 (cleanup) полностью завершён:
  - P3-10: Удалён deprecated cluster-service (~500KB, 55 файлов)
  - P3-10: Удалены unused batch-service handlers (delete, extensions, list, rollback)
  - P3-11: Архивировано 9 test files в `tests/archive/v1_api_tests/`:
    - test_databases_api.py, test_service_mesh_views.py, test_templates_views.py
    - test_workflow_api.py, test_workflow_integration.py, test_jwt_service_auth.py
    - workflow_load_test.py, test_celery_tasks.py
    - Удалён obsolete test_sprint_1_2.py
  - P3-12: OpenAPI specs validated, clients regenerated
- Итого удалено: ~10,500 строк legacy кода
- Миграция V1 → V2 Event-Driven полностью завершена!

### v1.4 (2025-12-15)
- ✅ P2 задачи полностью завершены:
  - Batch-service: удалено версионирование, flat internal API (`/storage/*`, `/metadata/*`)
  - API Gateway: удалён legacy `ProxyToOrchestrator()` (~77 строк)
  - API Gateway: удалены дублирующиеся flat RAS routes
  - Roadmap обновлён

### v1.3 (2025-12-15)
- ✅ P1 задачи полностью завершены:
  - V1 endpoints удалены из API Gateway OpenAPI spec (11 endpoints)
  - Django и Frontend уже полностью на v2

### v1.2 (2025-12-15)
- ✅ P1 задачи частично завершены:
  - Cluster-info через Redis Streams (primary, HTTP fallback)
  - Batch-service HTTP callback удалён
- Добавлен `cluster_info_waiter.go` для request-response через Streams
- Django handler `handle_get_cluster_info()` в event_subscriber.py
- Feature flag `USE_STREAMS_CLUSTER_INFO` (default: true)
- Удалены файлы:
  - `batch-service/internal/infrastructure/django/client.go`
  - `orchestrator/apps/databases/tests/test_extension_callback.py`
  - Endpoint `/api/v1/extensions/installation/callback/`

### v1.1 (2025-12-15)
- ✅ P0 задачи завершены:
  - Timeline events для sync_cluster (`cluster.sync.*`)
  - Frontend `.started`/`.processing` статус
  - Credentials fetch для RAS операций
- Добавлен `shared/credentials/` пакет с:
  - HTTP client с кэшированием (TTL 2 min)
  - AES-GCM-256 encryption/decryption
  - Transport key validation (hex encoding)
  - Background cache cleanup
- Обновлены ras-adapter event handlers для fetch credentials
- Унифицирован transport key handling (hex) в worker и ras-adapter
