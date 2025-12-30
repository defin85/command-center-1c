# Phase 0 Report: Django 6.0 + async-first (Audit)

> **Статус:** COMPLETE
> **Версия:** 1.0
> **Создан:** 2025-12-30
> **Обновлён:** 2025-12-30
> **Автор:** Codex

---

## Область аудита

- Django/DRF/Channels в `orchestrator/`.
- SSE и WebSocket точки.
- Sync/async границы и sync-only зависимости.

---

## 1) Sync/async boundaries (текущие точки смешивания)

- `orchestrator/apps/api_v2/views/databases.py`
  - `database_stream` sync view вызывает `async_to_sync(_database_stream_async)`.
  - В async-стриме — `sync_to_async` для ORM (`User.objects.get`, `PermissionService`).
  - Используются **оба** клиента Redis: `redis` (sync) и `redis.asyncio` (async).
- `orchestrator/apps/api_v2/views/operations.py`
  - `operation_stream` — sync view с sync Redis и sync ORM (BatchOperation).
  - `operation_stream_mux` — async view с `redis.asyncio`.
  - `sync_to_async` для runtime settings (`_get_max_*_async`).
- `orchestrator/apps/api_v2/views/system.py`
  - Sync view вызывает async Prometheus клиент через `async_to_sync`.
- `orchestrator/apps/api_v2/views/service_mesh.py`
  - Sync view вызывает async Prometheus клиент через `asyncio.run`.
- `orchestrator/apps/monitoring/services.py`
  - Async сервисы, но DB/Redis checks обёрнуты в `sync_to_async`.
- `orchestrator/apps/operations/signals.py`
  - В sync сигнале используется `async_to_sync(channel_layer.group_send)`.
- `orchestrator/apps/operations/consumers.py`
  - `sync_broadcast_service_mesh_update` — sync wrapper вокруг async broadcast.
- `orchestrator/apps/core/middleware.py`
  - WebSocket auth использует `database_sync_to_async` для токенов/ORM.

Вывод: SSE и метрики сейчас смешивают sync и async, есть два разных Redis клиента
и async вызовы из sync контекста (async_to_sync/asyncio.run).

---

## 2) Sync-only библиотеки и места использования

**Sync-only (блокируют event loop без обёртки):**

- Django ORM (везде, где `Model.objects.*`).
- `django.core.cache` (Redis backend) — `orchestrator/apps/monitoring/services.py`.
- `redis` (sync клиент) — `orchestrator/apps/operations/event_subscriber.py`,
  `orchestrator/apps/databases/events.py`, `orchestrator/apps/operations/prometheus_metrics.py`,
  `orchestrator/apps/api_v2/views/operations.py` (SSE), `orchestrator/apps/api_v2/views/databases.py` (ticket).
- `requests`/`urllib3` — `orchestrator/apps/databases/odata/client.py` (OData).
- `minio` — `orchestrator/apps/artifacts/storage.py`.
- `psycopg2-binary` — драйвер БД (sync).

**Async-capable (уже используются асинхронно):**

- `redis.asyncio` — SSE и WebSocket consumers.
- `aiohttp` — мониторинг HTTP сервисов.
- `httpx.AsyncClient` — Prometheus клиент (`apps/operations/services/prometheus_client.py`).
- Django Channels + Daphne — ASGI/WebSocket.

---

## 3) Совместимость зависимостей с Django 6.0 (предварительно)

Ниже список Django-специфичных библиотек, которые нужно проверить/обновить
под Django 6.0 (фактические версии пока не определены):

- `djangorestframework` (DRF)
- `drf-spectacular`
- `django-filter`
- `channels`, `channels-redis`, `daphne`
- `django-cors-headers`
- `django-environ`
- `django-prometheus`
- `whitenoise`
- `djangorestframework-simplejwt`
- `django-json-widget`
- `django-extensions`
- `django-encrypted-model-fields`
- `django-fsm-2`
- `django-pydantic-field`
- `opentelemetry-instrumentation-django`

---

## 4) Карта SSE и WebSocket потоков

**SSE (HTTP):**

- `/api/v2/databases/stream-ticket/` → `get_database_stream_ticket`
- `/api/v2/databases/stream/` → `database_stream` (async via wrapper)
- `/api/v2/operations/stream-ticket/` → `get_stream_ticket`
- `/api/v2/operations/stream/` → `operation_stream` (sync)
- `/api/v2/operations/stream-mux-ticket/` → `get_mux_stream_ticket`
- `/api/v2/operations/stream-mux/` → `operation_stream_mux` (async)
- `/api/v2/operations/stream-status/` → `get_stream_status`
- `/api/v2/operations/stream-mux-status/` → `get_stream_mux_status`
- `/api/v2/operations/stream-subscribe/` → `subscribe_operation_streams`
- `/api/v2/operations/stream-unsubscribe/` → `unsubscribe_operation_streams`

**SSE entrypoint (routing):**

- `orchestrator/config/urls.py` → `path('api/v2/', include('apps.api_v2.urls'))`
- `orchestrator/apps/api_v2/urls.py` (routes для stream endpoints)

**WebSocket:**

- `ws/workflow/<execution_id>/` → `apps/templates/consumers.py` (`WorkflowExecutionConsumer`)
- `ws/service-mesh/` → `apps/operations/consumers.py` (`ServiceMeshConsumer`)

**WebSocket entrypoint (ASGI):**

- `orchestrator/config/asgi.py` → `ProtocolTypeRouter` + `URLRouter`
- `orchestrator/apps/templates/routing.py`, `orchestrator/apps/operations/routing.py`

