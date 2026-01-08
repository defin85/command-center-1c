# Roadmap: Phase 7.5 — Администрирование RBAC (SPA-primary) и аудит
> **Статус:** DONE
> **Версия:** 1.2
> **Создан:** 2026-01-07
> **Обновлён:** 2026-01-08
> **Автор:** Codex
> **Реализация:** `5ceaee1` (MVP) + последующие коммиты Phase 7.5

Связанные документы/код:
- `docs/roadmaps/ROADMAP_PHASE7_RBAC_GOVERNANCE.md` (родительский roadmap Phase 7)
- `orchestrator/apps/api_v2/views/rbac.py` (текущий RBAC API v2: user->cluster/database)
- `orchestrator/apps/operations/models/admin_action_audit_log.py` + `orchestrator/apps/operations/services/admin_action_audit.py` (audit)
- `orchestrator/apps/core/rbac_backend.py` + `orchestrator/apps/core/rbac_permissions_map.py` (единая точка `user.has_perm(..., obj)`)
- `orchestrator/apps/core/permission_codes.py` (словари permission codes)

---

## Реальный статус (фикс)

Реализовано (DONE):
- SPA RBAC админка и доступ к ней гейтится по `databases.manage_rbac` (через `user.has_perm`), а не по `is_staff`.
- RBAC API v2 расширен: роли/capabilities, назначение ролей пользователям, refs для селектов SPA, bindings (user+group) для Clusters/Databases/Templates/Workflows/Artifacts, read‑API аудита.
- Write‑операции RBAC API: везде обязателен `reason` (включая direct user‑bindings для Cluster/Database и bulk endpoints); пишется `AdminActionAuditLog`.
- Self‑lockout guardrail: защита “последний RBAC admin” для `set-user-roles` и `set-role-capabilities` (409 `LAST_RBAC_ADMIN`, break-glass через superuser).
- Bulk endpoints: массовые grant/revoke group bindings (Clusters/Databases/Templates/Workflows/Artifacts) + агрегированный audit (без N событий на каждый объект).
- Effective access: include‑флаги + пагинация по databases через `limit/offset` + `source=direct|group|cluster` (+ `via_cluster_id` для наследования).
- SPA UX: доменно‑специфичные подсказки уровней `VIEW/OPERATE/MANAGE/ADMIN` + bulk‑формы для Clusters/Databases (role bindings).
- Contracts/generation: актуализирован OpenAPI, добавлен `drf-spectacular` postprocessing hook (orval‑friendly), генерация клиентов/роутов проходит.
- Тесты: добавлен pytest coverage для RBAC admin API.

Опционально (можно делать позже, не блокирует Phase 7.5):
- `preview-change` (dry-run) для bulk операций.
- UI‑tab “Effective access preview” (пользователь‑центричный просмотр с пагинацией).

## Analysis

### Контекст

Цель Phase 7.5 — сделать RBAC управляемым из SPA (без зависимости от Django Admin) и обеспечить прозрачный аудит
изменений прав/ролей/биндингов.

Исходное состояние (до реализации v1.0):
- В SPA есть `RBACPage`, но доступ к ней и к меню гейтился по `is_staff`.
- Backend `/api/v2/rbac/*` покрывал user-bindings только для `Cluster`/`Database` и `get-effective-access` только по ним.
- Для Templates/Workflows/Artifacts bindings уже существовали в моделях/сервисах, но не было SPA‑ориентированного admin API.
- Audit писался best-effort в `AdminActionAuditLog`, но read‑API для просмотра в SPA отсутствовал.

### Архитектурные драйверы

- **Производительность и простота:** Django-native (Groups + Permissions + Bindings), без внешних policy-сервисов на критическом пути.
- **Массовость:** главный объём — `Database`, затем `Templates/Workflows`, затем `Artifacts`.
- **Безопасность:** fail-closed, защита от self-lockout, минимум утечек через list.
- **Прозрачность:** человеко‑понятные подсказки уровней `VIEW/OPERATE/MANAGE/ADMIN` в UI + аудит всех изменений.

---

## Recommendations

### 1) Принять SPA-primary как источник истины для RBAC

RBAC администрирование должно быть доступно не “всем staff”, а по capability:
- доступ к RBAC админке/эндпоинтам: `databases.manage_rbac` (через `user.has_perm`).

`is_staff` остаётся отдельным механизмом для staff-only доменов (например, управление driver catalogs),
но не должен быть “магическим ключом” для RBAC страницы.

### 2) Сохранить `VIEW/OPERATE/MANAGE/ADMIN` и сделать подсказки (UX слой)

Уровни остаются как иерархия scope (каждый следующий включает предыдущий).
Чтобы убрать “непрозрачность”, SPA показывает доменно‑специфичные подсказки:

#### Databases / Clusters
- `VIEW`: видеть и читать (списки/детали/метаданные/статусы)
- `OPERATE`: выполнять операции (например lock/unlock/terminate и т.п.), без изменения конфигурации
- `MANAGE`: менять настройки/конфигурацию объекта
- `ADMIN`: разрушительные/владельческие действия (удаление/восстановление и т.п.); если домен не поддерживает — трактуется как “самый высокий уровень”

#### WorkflowTemplate / OperationTemplate
- `VIEW`: читать шаблон
- `OPERATE`: исполнять workflow (для workflow templates)
- `MANAGE`: создавать/редактировать/публиковать
- `ADMIN`: самый высокий уровень (если домен не различает отдельно)

#### Artifacts
- `VIEW`: видеть артефакт/версии (read)
- `OPERATE`: upload/публикация версий (операционные действия)
- `MANAGE`: управлять артефактом (настройки/алиасы/soft-delete)
- `ADMIN`: самый высокий уровень (если домен не различает отдельно)

### 3) Расширить RBAC API v2 до полного набора SPA‑админ операций

Все “write” операции должны:
- требовать `databases.manage_rbac`,
- требовать поле `reason` (ticket/обоснование),
- писать `AdminActionAuditLog` с нормализованным `action`, `target_type`, `target_id`, `metadata`.

#### 3.1 Roles / Capabilities (Django Groups + Django permissions)

Нужно дать SPA возможность:
- смотреть роли (groups),
- назначать/снимать capabilities (permissions) на роли,
- назначать/снимать роли пользователям,
- (рекомендуемо) создавать/переименовывать/архивировать роли в SPA.

Рекомендуемые endpoints (action-based стиль v2):
- `GET /api/v2/rbac/list-roles/`
- `POST /api/v2/rbac/create-role/` (`name`, `reason`)
- `POST /api/v2/rbac/update-role/` (`group_id`, `name|is_active`, `reason`)
- `POST /api/v2/rbac/delete-role/` (safe-delete: только если нет members/perms/bindings; `reason`)
- `GET /api/v2/rbac/list-capabilities/` (curated список из `permission_codes.py` + метаданные для UI)
- `POST /api/v2/rbac/set-role-capabilities/` (`group_id`, `permission_codes[]`, `mode=replace|add|remove`, `reason`)
- `POST /api/v2/rbac/set-user-roles/` (`user_id`, `group_ids[]`, `mode=replace|add|remove`, `reason`)

Примечания по безопасности:
- запретить удаление/снятие последней роли, которая даёт `databases.manage_rbac` (“последний админ RBAC”),
  либо требовать break-glass (superuser/staff) сценарий.

#### 3.2 Bindings (scope) для пользователей и групп

Нужно покрыть всеми доменами (минимум):
- `ClusterGroupPermission` / `DatabaseGroupPermission`
- `OperationTemplateGroupPermission` / `WorkflowTemplateGroupPermission`
- `ArtifactGroupPermission`
- user-bindings для Templates/Workflows/Artifacts (по аналогии с databases)

Рекомендуемые endpoints (примерная матрица):
- `GET /api/v2/rbac/list-<resource>-permissions/` (user bindings)
- `POST /api/v2/rbac/grant-<resource>-permission/`
- `POST /api/v2/rbac/revoke-<resource>-permission/`
- `GET /api/v2/rbac/list-<resource>-group-permissions/` (group bindings)
- `POST /api/v2/rbac/grant-<resource>-group-permission/`
- `POST /api/v2/rbac/revoke-<resource>-group-permission/`

Bulk (обязательно для массовых действий):
- `POST /api/v2/rbac/bulk-grant-<resource>-group-permission/` (список object ids, `level`, `reason`)
- `POST /api/v2/rbac/bulk-revoke-<resource>-group-permission/` (список object ids, `reason`)

Практика:
- bulk endpoints должны быть идемпотентными (повторный вызов безопасен),
  и возвращать `created/updated/skipped` счётчики.

#### 3.3 Effective access (для UI‑preview и диагностики)

Рекомендуем расширить текущий `get-effective-access` так, чтобы UI мог:
- видеть итоговый доступ пользователя по доменам (databases/clusters/templates/workflows/artifacts),
- понимать источник (direct/group/inherited),
- получать ответ дозировано (флаги include_* + пагинация для databases).

Рекомендуемые изменения:
- `GET /api/v2/rbac/get-effective-access/`:
  - параметры: `user_id?`, `include_clusters?`, `include_databases?`, `include_templates?`, `include_workflows?`, `include_artifacts?`
  - параметры: `limit/offset` для массивов с высокой кардинальностью (`databases`)
  - поля ответа: `level`, `source` (`direct|group|cluster|inherited`), (опц.) `via` (например `cluster_id` для наследования)

Дополнительно (по необходимости UX):
- `POST /api/v2/rbac/preview-change/` (dry-run): показывает, что изменится при применении bulk/grant.

### 4) Добавить read‑API для аудита (SPA)

Сделать endpoint для просмотра `AdminActionAuditLog`:
- `GET /api/v2/rbac/list-admin-audit/` (или отдельный `/api/v2/audit/admin-actions/`)

Фильтры (минимум):
- `action`, `outcome`, `actor_username|actor_id`, `target_type`, `target_id`, `since`, `until`, `search`, `limit`, `offset`

Нормализовать поля audit metadata:
- `reason` (обязательно для write),
- `subject_type/subject_id` (user/group),
- `object_type/object_id` (cluster/database/template/artifact),
- `old_level/new_level`, `bulk_count`, `permission_codes`, `request_id` (если есть).

---

## Implementation Considerations

### Backend

- Авторизация:
  - все `/api/v2/rbac/*` endpoints — `IsAuthenticated` + `_ensure_manage_rbac` (через `user.has_perm(databases.manage_rbac)`).
  - staff-only админские разделы остаются отдельно (например driver catalogs).
- “Справочники” для селектов SPA:
  - либо переиспользовать существующие list endpoints с правильным гейтингом,
  - либо добавить `rbac/ref/*` endpoints (возвращают только `id/name`), чтобы RBAC UI не зависел от staff-only списков.
- Аудит:
  - использовать `log_admin_action()` везде, включая bulk.
  - не писать чувствительные данные (пароли, токены, секреты).

### Frontend (SPA)

Разбить RBAC UI на табы:
- **Users**: назначение ролей пользователям, поиск, массовые операции.
- **Roles**: список ролей, управление capabilities, подсказки по назначению.
- **Bindings**: user/group bindings по доменам (Database/Cluster/Templates/Artifacts), bulk.
- **Effective access**: просмотр итогового доступа (user-centric).
- **Audit**: фильтруемый просмотр изменений RBAC.

Подсказки уровней (`VIEW/OPERATE/MANAGE/ADMIN`):
- реализовать как статическую матрицу в SPA (быстро и без новых API),
- либо вернуть из `list-capabilities`/`rbac/config` endpoint (если нужно централизовать).

### Безопасность и “break-glass”

- Запретить:
  - удалить роль, если есть участники/perms/bindings,
  - снять/удалить последний источник `databases.manage_rbac` без явного break-glass пути.
- Оставить Django Admin доступ суперпользователю как аварийный канал (операционная мера).

---

## Risks

- **Self-lockout** (потеряли доступ к RBAC): нужен guardrail “последний админ” + break-glass.
- **Тяжёлые выборки** (effective access по 700+ DB): нужны include_* флаги, пагинация, и выборка через service-layer/batch.
- **Аудит‑шум** (bulk): агрегировать события (одно событие на bulk с счётчиками), а не N событий на каждый объект.
- **Несогласованность capabilities vs scope**: в UI всегда показывать оба слоя (capabilities и bindings) и давать preview.
