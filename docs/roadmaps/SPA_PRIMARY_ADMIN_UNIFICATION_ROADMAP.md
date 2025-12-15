# Roadmap: Унификация администрирования (SPA-primary)

> **Статус:** DRAFT
> **Версия:** 0.1
> **Создан:** 2025-12-15
> **Обновлён:** 2025-12-15
> **Автор:** Codex CLI (GPT-5.2)

---

## Цель

Сделать SPA (frontend) **единственной основной консолью** для повседневного администрирования и операций (операторский UX), а Django Admin — **вспомогательным инструментом** (break-glass / диагностика / read-only), чтобы исключить дублирование функций и расхождение правил.

## Принципы (индустриальный стандарт)

1. **API-first**: любые мутации делаются только через `/api/v2/*` (action-based), независимо от UI.
2. **Single source of truth**: бизнес-правила, RBAC, инварианты, аудит — в сервисном слое/API, а не “в одном из UI”.
3. **Contract-driven**: OpenAPI (`contracts/**`) отражает реальную безопасность/пейлоады; SPA максимально использует generated client.
4. **Django Admin = break-glass**: минимум мутаций, по возможности read-only; без “обходных” side-effects.
5. **Безопасность и аудит**: все админ-действия трассируемы (audit), права применяются одинаково, нет “скрытых путей”.

---

## Текущее состояние (кратко)

### Где есть дублирование

| Домен | Сейчас в SPA | Сейчас в Django Admin | Проблема |
|------:|--------------|-----------------------|----------|
| Clusters | CRUD + sync/discover | CRUD + actions (sync/reset и т.п.) | двойной UX и риск расхождения правил |
| Workflows/Templates | CRUD + validate (частично) | CRUD + validate + sync from registry | дублирование flows и источников истины |
| RBAC (ClusterPermission/DatabasePermission) | отсутствует UI | есть управление | SPA не может быть “primary console” без RBAC |

### Contract drift (важно закрыть рано)

- OpenAPI `securitySchemes` сейчас только `cookieAuth`, при этом SPA использует `Authorization: Bearer <JWT>` и refresh.
- В контракте у некоторых action endpoints отсутствуют requestBody (например, cluster discovery), из-за чего SPA вынужден обходить генерацию.

---

## Целевая модель ответственности (Target Operating Model)

### SPA (primary)

- Управление сущностями и повседневные операции: Clusters/Databases/Operations/Workflows/Templates, maintenance actions.
- RBAC: выдача/отзыв прав, просмотр эффективных прав, “кто имеет доступ к чему”.
- Аудит действий (как минимум просмотр + фильтры; запись — на стороне API).

### Django Admin (secondary)

- Read-only по основным доменным моделям (Cluster/Database/WorkflowTemplate/OperationTemplate) или строго ограниченные мутации только для superuser.
- Диагностика и служебные модели (например, логи/инциденты) — по необходимости.
- Никаких уникальных “операторских” flows, которые отсутствуют в SPA.

---

## Workstreams (потоки работ)

### WS1 — Аутентификация и идентичность (SPA ↔ API)

**Цель:** выровнять реальную схему auth и её описание в OpenAPI.

- Определить целевую схему: `bearerAuth` (JWT) как основная для SPA; cookies — только если реально используются/нужны.
- Обновить OpenAPI: добавить `bearerAuth`, корректно описать security на `/api/v2/*`.
- Добавить/стандартизировать endpoint “кто я” (например, `/api/v2/system/me/`) для UI-ролей/фич-флагов (если нужно).

### WS2 — OpenAPI → Generated client (снижение “ручных обходов”)

**Цель:** чтобы SPA использовал generated client для v2, а не ручные `apiClient.post('/api/v2/...')`.

- Внести в контракт отсутствующие `requestBody` и схемы ответов там, где сейчас SPA делает обход.
- Согласовать naming/operationIds так, чтобы не было коллизий и “нечитаемых” имён.

### WS3 — RBAC v2 (must-have для SPA-primary)

**Цель:** управлять доступами из SPA, а не через Django Admin.

- v2 endpoints:
  - list/grant/revoke для ClusterPermission и DatabasePermission
  - просмотр эффективных прав пользователя на кластеры/базы
  - bulk операции (опционально) + пагинация/фильтры
- Единые проверки: использовать существующие permission классы/сервис (`apps.databases.permissions`, `PermissionService`) и расширить где нужно.
- Аудит: протоколировать grant/revoke (кто/что/когда/почему).

### WS4 — Миграция “admin-actions” в v2 + SPA

**Цель:** все operator-grade actions доступны из SPA и идут через v2.

Кандидаты:
- “Sync from registry” для OperationTemplate (вместо admin action/button).
- Reset sync status / unstick operations (вместо admin action).
- Import/sync from cluster (если это must-have операторский сценарий) — как асинхронная job с прогрессом.

### WS5 — Ужесточение Django Admin (de-duplication)

**Цель:** после появления эквивалента в SPA — убрать/запретить дубли в Admin.

- Отключить actions, add/change/delete (где применимо), оставить только просмотр.
- Явно пометить модели/страницы предупреждением “Use SPA console”.
- Ограничить доступ: отдельная группа “break-glass admins”, минимум пользователей.

---

## Инвентаризация: SPA-экраны ↔ v2 endpoints ↔ источники дублирования

> Цель секции: быстро увидеть, что уже покрыто SPA, что живёт только в Django Admin, и где OpenAPI мешает generated client.

### Основные маршруты SPA (текущие)

| Route | Экран | Код |
|------:|-------|-----|
| `/clusters` | Clusters CRUD + Sync + Discover | `frontend/src/pages/Clusters/Clusters.tsx` |
| `/databases` | Databases list + RAS actions + extension install | `frontend/src/pages/Databases/Databases.tsx` |
| `/operations` | Operations center (list/monitor/wizard) | `frontend/src/pages/Operations/OperationsPage.tsx` |
| `/workflows` | Workflow templates list/manage | `frontend/src/pages/Workflows/WorkflowList.tsx` |
| `/workflows/:id` | Workflow designer/editor | `frontend/src/pages/Workflows/WorkflowDesigner.tsx` |
| `/system-status` | System health | `frontend/src/pages/SystemStatus/SystemStatus.tsx` |
| `/service-mesh` | Realtime service mesh | `frontend/src/pages/ServiceMesh/ServiceMeshPage.tsx` |

### Дублирующие функции (SPA vs Django Admin)

| Домен | SPA (сейчас) | Django Admin (сейчас) | Решение в SPA-primary |
|------:|--------------|------------------------|------------------------|
| Clusters | CRUD + sync/discover | CRUD + actions (sync/reset) | SPA = основной; admin = read-only после паритета |
| Databases | list + actions (operate) + extension install | CRUD + health-check actions + “sync from cluster” wizard | операционные flows в SPA; импорт/редкие правки — отдельный v2 action или убрать |
| Workflows | list/edit/clone/delete/validate (через v2) | CRUD + validate | SPA = основной; admin = read-only |
| Operation templates | использует list-templates (reference) | CRUD + “sync from registry” | вынести “sync from registry” в v2 + добавить UI |
| RBAC (ClusterPermission/DatabasePermission) | нет UI | есть управление | must-have: v2 RBAC endpoints + UI, затем ужесточить admin |

---

## Backlog: выравнивание OpenAPI (contracts) для SPA-primary

### 1) Security schemes (auth) — критично

**Симптом:** OpenAPI описывает только `cookieAuth`, а SPA использует `Authorization: Bearer <JWT>` и refresh (`frontend/src/api/client.ts`).

**Действия:**
- [ ] В `contracts/orchestrator/openapi.yaml` добавить `bearerAuth` (HTTP bearer, JWT).
- [ ] Для `/api/v2/*` endpoints указать `security` как “cookieAuth OR bearerAuth” (если бэкенд реально поддерживает оба), либо только bearerAuth.
- [ ] Опционально: добавить endpoint “me” (кто я / роли / фичи), чтобы SPA не хардкодил “admin” в UI.

### 2) Request body / schemas gaps — убрать ручные обходы

**Текущие обходы в SPA:**
- `POST /api/v2/clusters/discover-clusters/` — SPA отправляет body, но OpenAPI не описывает requestBody → ручной `apiClient.post` (`frontend/src/api/queries/clusters.ts`).
- `POST /api/v2/extensions/install-single/` — используется SPA, но отсутствует в OpenAPI → ручной `apiClient.post` (`frontend/src/api/queries/databases.ts`).
- `GET /api/v2/tracing/*` (Jaeger proxy через Gateway) — используется SPA, но отсутствует в OpenAPI → ручной клиент (`frontend/src/api/endpoints/jaeger.ts`).

**Действия:**
- [ ] Добавить schema + requestBody для `discover-clusters` (и ответы/ошибки).
- [ ] Добавить endpoint `extensions/install-single` в OpenAPI (request/response).
- [ ] Принять решение по tracing/jaeger proxy:
  - Вариант A: добавить `/api/v2/tracing/*` в `contracts/orchestrator/openapi.yaml` как proxy endpoints (минимальные схемы).
  - Вариант B: завести отдельный контракт для API Gateway и генерировать второй клиент (предпочтительнее архитектурно, но дороже).

### 3) Generated client adoption — “нулевые” выигрыши

После фикса контрактов:
- [ ] Заменить ручной `GET /api/v2/system/config/` на generated `getSystemConfig` (`frontend/src/api/queries/clusters.ts`).
- [ ] Заменить ручной `GET/POST` там, где endpoints уже есть в контракте (operations/dashboard/файлы/расширения).

---

## Backlog: паритет SPA для функций, которые сейчас “только в Admin”

### RBAC UI + v2 endpoints (must-have)

- [ ] `GET /api/v2/rbac/list-cluster-permissions` (+ фильтры: user/cluster/level)
- [ ] `POST /api/v2/rbac/grant-cluster-permission`
- [ ] `POST /api/v2/rbac/revoke-cluster-permission`
- [ ] `GET /api/v2/rbac/list-database-permissions`
- [ ] `POST /api/v2/rbac/grant-database-permission`
- [ ] `POST /api/v2/rbac/revoke-database-permission`
- [ ] `GET /api/v2/rbac/effective-access?user_id=...` (кластеры/базы + уровень)

> Реализация должна опираться на текущий `PermissionService` и уровни (VIEW/OPERATE/MANAGE/ADMIN).

---

## Contract Tasks (OpenAPI): точные endpoints + схемы

> Эта секция — “готовое ТЗ” для изменения `contracts/orchestrator/openapi.yaml` (и при необходимости нового `contracts/api-gateway/openapi.yaml`).

### CT1 — Добавить `bearerAuth` (JWT) в OpenAPI

**Файл:** `contracts/orchestrator/openapi.yaml`

**Изменение:** расширить `components.securitySchemes`:

```yaml
components:
  securitySchemes:
    cookieAuth:
      type: apiKey
      in: cookie
      name: sessionid
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

**Правило:** для `/api/v2/*` указать `security` как один из:
- только `bearerAuth` (если cookies не нужны SPA), или
- `[{ bearerAuth: [] }, { cookieAuth: [] }]` (если реально поддерживаются оба).

### CT2 — RBAC endpoints (ClusterPermission/DatabasePermission)

**Файл:** `contracts/orchestrator/openapi.yaml`

#### Пути (action-based, v2)

```yaml
/api/v2/rbac/list-cluster-permissions/:
  get:
    operationId: v2_rbac_list_cluster_permissions_retrieve
    tags: [v2]
    security: [{ bearerAuth: [] }, { cookieAuth: [] }]
    parameters:
      - in: query
        name: user_id
        schema: { type: integer }
      - in: query
        name: cluster_id
        schema: { type: string }
      - in: query
        name: level
        schema: { $ref: '#/components/schemas/PermissionLevel' }
      - in: query
        name: search
        schema: { type: string }
      - in: query
        name: limit
        schema: { type: integer, default: 50 }
      - in: query
        name: offset
        schema: { type: integer, default: 0 }
    responses:
      '200': { content: { application/json: { schema: { $ref: '#/components/schemas/ClusterPermissionListResponse' } } } }
      '401': { description: Unauthorized }

/api/v2/rbac/grant-cluster-permission/:
  post:
    operationId: v2_rbac_grant_cluster_permission_create
    tags: [v2]
    security: [{ bearerAuth: [] }, { cookieAuth: [] }]
    requestBody:
      required: true
      content:
        application/json:
          schema: { $ref: '#/components/schemas/GrantClusterPermissionRequest' }
    responses:
      '200': { content: { application/json: { schema: { $ref: '#/components/schemas/ClusterPermissionUpsertResponse' } } } }
      '400': { content: { application/json: { schema: { $ref: '#/components/schemas/ErrorResponse' } } } }
      '401': { description: Unauthorized }
      '403': { description: Forbidden }

/api/v2/rbac/revoke-cluster-permission/:
  post:
    operationId: v2_rbac_revoke_cluster_permission_create
    tags: [v2]
    security: [{ bearerAuth: [] }, { cookieAuth: [] }]
    requestBody:
      required: true
      content:
        application/json:
          schema: { $ref: '#/components/schemas/RevokeClusterPermissionRequest' }
    responses:
      '200': { content: { application/json: { schema: { $ref: '#/components/schemas/RevokePermissionResponse' } } } }
      '400': { content: { application/json: { schema: { $ref: '#/components/schemas/ErrorResponse' } } } }
      '401': { description: Unauthorized }
      '403': { description: Forbidden }

/api/v2/rbac/list-database-permissions/:
  get:
    operationId: v2_rbac_list_database_permissions_retrieve
    tags: [v2]
    security: [{ bearerAuth: [] }, { cookieAuth: [] }]
    parameters:
      - in: query
        name: user_id
        schema: { type: integer }
      - in: query
        name: database_id
        schema: { type: string }
      - in: query
        name: cluster_id
        schema: { type: string }
      - in: query
        name: level
        schema: { $ref: '#/components/schemas/PermissionLevel' }
      - in: query
        name: search
        schema: { type: string }
      - in: query
        name: limit
        schema: { type: integer, default: 50 }
      - in: query
        name: offset
        schema: { type: integer, default: 0 }
    responses:
      '200': { content: { application/json: { schema: { $ref: '#/components/schemas/DatabasePermissionListResponse' } } } }
      '401': { description: Unauthorized }

/api/v2/rbac/grant-database-permission/:
  post:
    operationId: v2_rbac_grant_database_permission_create
    tags: [v2]
    security: [{ bearerAuth: [] }, { cookieAuth: [] }]
    requestBody:
      required: true
      content:
        application/json:
          schema: { $ref: '#/components/schemas/GrantDatabasePermissionRequest' }
    responses:
      '200': { content: { application/json: { schema: { $ref: '#/components/schemas/DatabasePermissionUpsertResponse' } } } }
      '400': { content: { application/json: { schema: { $ref: '#/components/schemas/ErrorResponse' } } } }
      '401': { description: Unauthorized }
      '403': { description: Forbidden }

/api/v2/rbac/revoke-database-permission/:
  post:
    operationId: v2_rbac_revoke_database_permission_create
    tags: [v2]
    security: [{ bearerAuth: [] }, { cookieAuth: [] }]
    requestBody:
      required: true
      content:
        application/json:
          schema: { $ref: '#/components/schemas/RevokeDatabasePermissionRequest' }
    responses:
      '200': { content: { application/json: { schema: { $ref: '#/components/schemas/RevokePermissionResponse' } } } }
      '400': { content: { application/json: { schema: { $ref: '#/components/schemas/ErrorResponse' } } } }
      '401': { description: Unauthorized }
      '403': { description: Forbidden }

/api/v2/rbac/get-effective-access/:
  get:
    operationId: v2_rbac_get_effective_access_retrieve
    tags: [v2]
    security: [{ bearerAuth: [] }, { cookieAuth: [] }]
    parameters:
      - in: query
        name: user_id
        schema: { type: integer }
        description: Optional (default: current user)
      - in: query
        name: include_databases
        schema: { type: boolean, default: true }
      - in: query
        name: include_clusters
        schema: { type: boolean, default: true }
    responses:
      '200': { content: { application/json: { schema: { $ref: '#/components/schemas/EffectiveAccessResponse' } } } }
      '401': { description: Unauthorized }
      '403': { description: Forbidden }
```

#### Схемы (`components.schemas`)

```yaml
PermissionLevel:
  type: string
  description: Permission level (RBAC)
  enum: [VIEW, OPERATE, MANAGE, ADMIN]

GrantClusterPermissionRequest:
  type: object
  required: [user_id, cluster_id, level]
  properties:
    user_id: { type: integer }
    cluster_id: { type: string }
    level: { $ref: '#/components/schemas/PermissionLevel' }
    notes: { type: string }

RevokeClusterPermissionRequest:
  type: object
  required: [user_id, cluster_id]
  properties:
    user_id: { type: integer }
    cluster_id: { type: string }

GrantDatabasePermissionRequest:
  type: object
  required: [user_id, database_id, level]
  properties:
    user_id: { type: integer }
    database_id: { type: string }
    level: { $ref: '#/components/schemas/PermissionLevel' }
    notes: { type: string }

RevokeDatabasePermissionRequest:
  type: object
  required: [user_id, database_id]
  properties:
    user_id: { type: integer }
    database_id: { type: string }

UserRef:
  type: object
  required: [id, username]
  properties:
    id: { type: integer }
    username: { type: string }

ClusterRef:
  type: object
  required: [id, name]
  properties:
    id: { type: string }
    name: { type: string }

DatabaseRef:
  type: object
  required: [id, name]
  properties:
    id: { type: string }
    name: { type: string }
    cluster_id: { type: string }

ClusterPermission:
  type: object
  required: [user, cluster, level, granted_at]
  properties:
    user: { $ref: '#/components/schemas/UserRef' }
    cluster: { $ref: '#/components/schemas/ClusterRef' }
    level: { $ref: '#/components/schemas/PermissionLevel' }
    granted_by: { $ref: '#/components/schemas/UserRef' }
    granted_at: { type: string, format: date-time }
    notes: { type: string }

DatabasePermission:
  type: object
  required: [user, database, level, granted_at]
  properties:
    user: { $ref: '#/components/schemas/UserRef' }
    database: { $ref: '#/components/schemas/DatabaseRef' }
    level: { $ref: '#/components/schemas/PermissionLevel' }
    granted_by: { $ref: '#/components/schemas/UserRef' }
    granted_at: { type: string, format: date-time }
    notes: { type: string }

ClusterPermissionListResponse:
  type: object
  required: [permissions, count, total]
  properties:
    permissions:
      type: array
      items: { $ref: '#/components/schemas/ClusterPermission' }
    count: { type: integer }
    total: { type: integer }

DatabasePermissionListResponse:
  type: object
  required: [permissions, count, total]
  properties:
    permissions:
      type: array
      items: { $ref: '#/components/schemas/DatabasePermission' }
    count: { type: integer }
    total: { type: integer }

RevokePermissionResponse:
  type: object
  required: [deleted]
  properties:
    deleted: { type: boolean }

ClusterPermissionUpsertResponse:
  type: object
  required: [created, permission]
  properties:
    created: { type: boolean }
    permission: { $ref: '#/components/schemas/ClusterPermission' }

DatabasePermissionUpsertResponse:
  type: object
  required: [created, permission]
  properties:
    created: { type: boolean }
    permission: { $ref: '#/components/schemas/DatabasePermission' }

EffectiveAccessClusterItem:
  type: object
  required: [cluster, level]
  properties:
    cluster: { $ref: '#/components/schemas/ClusterRef' }
    level: { $ref: '#/components/schemas/PermissionLevel' }

EffectiveAccessDatabaseItem:
  type: object
  required: [database, level, source]
  properties:
    database: { $ref: '#/components/schemas/DatabaseRef' }
    level: { $ref: '#/components/schemas/PermissionLevel' }
    source:
      type: string
      enum: [direct, cluster]

EffectiveAccessResponse:
  type: object
  required: [user, clusters, databases]
  properties:
    user: { $ref: '#/components/schemas/UserRef' }
    clusters:
      type: array
      items: { $ref: '#/components/schemas/EffectiveAccessClusterItem' }
    databases:
      type: array
      items: { $ref: '#/components/schemas/EffectiveAccessDatabaseItem' }
```

**Примечание по правам:** доступ к RBAC управлению должен быть ограничен (минимум `is_staff`/`is_superuser`), при этом чтение эффективных прав текущего пользователя может быть разрешено всем `IsAuthenticated`.

### CT3 — Templates: “sync from registry” как v2 action

**Файл:** `contracts/orchestrator/openapi.yaml`

**Путь:**

```yaml
/api/v2/templates/sync-from-registry/:
  post:
    operationId: v2_templates_sync_from_registry_create
    tags: [v2]
    security: [{ bearerAuth: [] }, { cookieAuth: [] }]
    requestBody:
      required: false
      content:
        application/json:
          schema:
            type: object
            properties:
              dry_run: { type: boolean, default: false }
    responses:
      '200': { content: { application/json: { schema: { $ref: '#/components/schemas/TemplateSyncResponse' } } } }
      '401': { description: Unauthorized }
      '403': { description: Forbidden }
```

**Схема ответа:**

```yaml
TemplateSyncResponse:
  type: object
  required: [created, updated, unchanged, message]
  properties:
    created: { type: integer }
    updated: { type: integer }
    unchanged: { type: integer }
    message: { type: string }
```

### CT4 — Clusters: `discover-clusters` добавить requestBody (убрать обход в SPA)

**Файл:** `contracts/orchestrator/openapi.yaml`

**Добавить requestBody к существующему пути** `/api/v2/clusters/discover-clusters/`:

```yaml
requestBody:
  required: true
  content:
    application/json:
      schema: { $ref: '#/components/schemas/DiscoverClustersRequest' }
```

**Схема:**

```yaml
DiscoverClustersRequest:
  type: object
  required: [ras_server, cluster_service_url]
  properties:
    ras_server: { type: string, example: "localhost:1545" }
    cluster_service_url: { type: string, example: "http://localhost:8188" }
    cluster_user: { type: string }
    cluster_pwd: { type: string }
```

### CT5 — Gateway proxy: `/api/v2/tracing/*` (Jaeger) — вынести в отдельный контракт

**Проблема:** SPA использует `/api/v2/tracing/*`, но это прокси в API Gateway, не в Orchestrator.

**Решение (рекомендуемое):**
- [ ] Создать `contracts/api-gateway/openapi.yaml`
- [ ] Описать `/api/v2/tracing/traces` и `/api/v2/tracing/traces/{traceId}` (минимальные схемы, совместимые с Jaeger API)
- [ ] Добавить генерацию второго клиента и использовать его в `frontend/src/api/endpoints/jaeger.ts`

**Альтернатива (быстро, но менее чисто):** временно описать tracing endpoints в `contracts/orchestrator/openapi.yaml` как proxy.

### “Sync from registry” для OperationTemplate

- [ ] v2 action endpoint (например, `POST /api/v2/templates/sync-from-registry`)
- [ ] UI кнопка/страница в SPA (с результатом created/updated/unchanged)
- [ ] После паритета: отключить action/button в Django Admin

### “Reset sync status / unstick” для Clusters

- [ ] UI в SPA для `POST /api/v2/clusters/reset-sync-status/` (точечно или bulk)
- [ ] После паритета: отключить аналогичный admin action

---

## Admin UX Backlog (SPA): DLQ Console (из Observability)

> Источник: `docs/roadmaps/OBSERVABILITY_ROADMAP.md` (пункты 1.2.5–1.2.6 перенесены сюда).

### Цель

Дать операторам в SPA:
- список DLQ-сообщений (с фильтрами/поиском),
- безопасный retry (переотправка/повторная обработка) с аудитом,
без необходимости заходить в Django Admin.

### Задачи (MVP)

- [ ] Добавить v2 endpoints для DLQ (list/get/retry) + описать в OpenAPI
- [ ] SPA: экран `DLQ` (таблица: operation_id, error_code, error_message, worker_id, failed_at, original_message_id)
- [ ] SPA: действие `Retry` (одиночное + bulk) с подтверждением и rate limit
- [ ] SPA: связка с Operations Center (переход к `operation_id`, если существует)
- [ ] Аудит retry: кто/когда/что перезапустил (минимум metadata в BatchOperation или отдельная модель)

### Контракт (черновик, action-based)

> Реализация может быть “proxy view” поверх Redis Stream `commands:worker:dlq` (read) и механизма re-enqueue (write).

- [ ] `GET /api/v2/dlq/list/` (фильтры: `operation_id`, `error_code`, `since`, `limit`, `offset`)
- [ ] `POST /api/v2/dlq/retry/` (body: `original_message_id` или `operation_id`; режим: `requeue|replay`; `reason`)

---

## Фазы и сроки (ориентир 10 недель)

> Сроки ориентировочные; критичный фактор — “WS3 RBAC + WS2 contracts”.

### Фаза 0 (Week 0–1): Инвентаризация и фиксация целевой модели

- [ ] Зафиксировать список “что считается админ-функцией” и где она должна жить (SPA vs Admin).
- [ ] Определить target auth схему для SPA (`bearerAuth`).
- [ ] Сформировать список contract drift пунктов (минимальный набор для генерации клиентов без обходов).

### Фаза 1 (Week 1–3): Contract + Auth выравнивание

- [ ] Обновить OpenAPI: `bearerAuth` + security для `/api/v2/*`.
- [ ] Добавить недостающие requestBody/response схемы (например, cluster discovery).
- [ ] Перевести максимум ручных вызовов SPA на generated client (там, где контракт уже корректен).

### Фаза 2 (Week 3–6): RBAC v2 + SPA UI

- [ ] Реализовать v2 RBAC endpoints (grant/revoke/list/effective permissions).
- [ ] Добавить UI в SPA для управления правами (минимум: выдача/отзыв + просмотр).
- [ ] Добавить тесты на RBAC и запреты (DoD: нельзя выполнить операции без уровня OPERATE/MANAGE/ADMIN).

### Фаза 3 (Week 6–8): Миграция admin-actions → v2 + SPA

- [ ] Вынести “sync from registry” в v2 action + кнопку/страницу в SPA.
- [ ] Закрыть все operator-critical действия, которые сейчас возможны только через Django Admin.

### Фаза 4 (Week 8–10): De-duplication в Django Admin + финализация

- [ ] Отключить/урезать дублирующие модели/действия в Django Admin (read-only).
- [ ] Обновить документацию для операторов: “единый путь через SPA”.
- [ ] Добавить минимальный контроль: метрики/аудит по ключевым админ-действиям.

---

## Definition of Done (критерии готовности)

- SPA покрывает: Clusters/Databases/Workflows/Templates + все повседневные actions + RBAC управление.
- Django Admin не предоставляет “альтернативного пути” для тех же операторских flows (read-only/ограничено).
- OpenAPI отражает реальную auth модель (включая `bearerAuth`) и позволяет генерировать клиент без обходов.
- Проверки прав едины и применяются в v2 endpoints; RBAC тестами закрыт.
- Соблюдены критические ограничения домена (например, 1C транзакции < 15 сек; OData batch 100–500).

---

## Риски и меры

| Риск | Проявление | Мера |
|------|------------|------|
| Расхождение auth (cookie vs JWT) | “генерация есть, но не работает” | закрыть WS1/WS2 в начале |
| “Утечки” уникальных admin flows | оператор продолжает пользоваться Admin | WS5: запреты + коммуникация + баннеры |
| RBAC не готов → SPA не может быть primary | часть команды “вынужденно” идёт в Admin | WS3 как must-have до де-дупликации |
| Сложные операции (import/sync) | долгие/непредсказуемые процессы | делать async job + прогресс + retry/audit |

---

## Imported (незавершённые шаги, перенесённые из других roadmap)

> Эти пункты перенесены сюда как **зависимости SPA-primary**. Источники помечены “moved” в исходных документах.

### Из `docs/roadmaps/STATE_MACHINE_MIGRATION_ROADMAP.md`

- [ ] Integration tests (общие) — из Phase 0/1.x/2.x (отложенные пункты)
- [ ] Production readiness: SLO/latency/success-rate проверки (p99/p95 и т.п.)
- [ ] Удаление v1 HTTP endpoints в ras-adapter после deprecation period (если принято как цель)

### Из `docs/roadmaps/V1_TO_V2_EVENT_DRIVEN_MIGRATION.md`

- [ ] Credentials через Streams (commands/events + Django handler + Worker client) — убрать прямые HTTP зависимости
- [ ] Timeline записи в Django для BatchOperation (redis client + started/completed события)
- [ ] Финальная зачистка v1 (удалить v1 views/urls, обновить docs, обновить OpenAPI specs, regenerate clients)
