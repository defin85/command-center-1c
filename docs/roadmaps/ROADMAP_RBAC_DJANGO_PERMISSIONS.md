# Roadmap: RBAC ↔ Django permissions

> **Статус:** DRAFT  
> **Версия:** 1.0  
> **Создан:** 2025-12-30  
> **Обновлён:** 2025-12-30  
> **Автор:** Codex

---

## Цель

Сделать RBAC (ClusterPermission/DatabasePermission) единым источником истины,
но использовать стандартный интерфейс Django (`user.has_perm`) для всех проверок
в DRF, бизнес‑сервисах и UI‑гейтинге.

---

## Текущее состояние (кратко)

- RBAC хранится в Django моделях: `ClusterPermission`, `DatabasePermission`.
- Логика прав: `PermissionService` в `orchestrator/apps/databases/services.py`.
- Проверки в DRF: `HasDatabasePermission`, `HasClusterPermission`.
- Админские RBAC endpoints защищены `IsAdminUser` (is_staff).

---

## Принципы

- RBAC остаётся источником истины (никакой синхронизации в `auth_permission`).
- Проверки через `user.has_perm(<perm>, obj)` как единая точка входа.
- Объектные права: кластер/база данных.
- `is_staff` сохраняется как admin‑bypass (как сейчас).

---

## Карта permissions (первичная)

**Clusters:**
- `databases.view_cluster` → VIEW
- `databases.operate_cluster` → OPERATE
- `databases.manage_cluster` → MANAGE
- `databases.admin_cluster` → ADMIN

**Databases:**
- `databases.view_database` → VIEW
- `databases.operate_database` → OPERATE
- `databases.manage_database` → MANAGE
- `databases.admin_database` → ADMIN

**RBAC управление (не объектное):**
- `rbac.manage` → доступ к RBAC endpoints (list/grant/revoke)

---

## Roadmap

### Phase 1 — Core backend + mapping

**Цель:** включить `user.has_perm(...)` поверх RBAC.

Задачи:
- Добавить `apps/databases/auth_backends.py` с `RBACPermissionBackend`:
  - `has_perm(user, perm, obj=None)` с маппингом perm→PermissionLevel.
  - `has_module_perms(user, app_label)` для UI/админки.
- Описать карту perm→уровень (константы в `apps/databases/permissions_map.py`).
- Подключить backend в `AUTHENTICATION_BACKENDS`.
- Тесты на `has_perm` для cluster/database (VIEW/OPERATE/MANAGE/ADMIN).

Выход:
- `user.has_perm("databases.manage_database", database)` работает.
- `user.has_perm("databases.view_cluster", cluster)` работает.

---

### Phase 2 — DRF интеграция

**Цель:** единая проверка в API и объектная фильтрация.

Задачи:
- Переписать `HasDatabasePermission`/`HasClusterPermission` на `user.has_perm`.
- Добавить общий mixin/permission для action‑уровней.
- Фильтрация списков: использовать `PermissionService.filter_accessible_*`
  в queryset (list endpoints).
- Логирование отказов и единый error format.

Выход:
- Все API‑эндпоинты используют единый механизм.
- Утечки по list исключены (фильтрация по RBAC).

---

### Phase 3 — RBAC администрирование

**Цель:** убрать `IsAdminUser` как «магическое» условие, оставить RBAC‑perm.

Задачи:
- Заменить `IsAdminUser` в `apps/api_v2/views/rbac.py` на `rbac.manage`.
- Обновить UI‑гейтинг: RBAC страница доступна по `rbac.manage`.
- Добавить `EffectiveAccess` для UI везде, где нужны «права по объектам».

Выход:
- Управление RBAC доступно по явному permission.
- UI опирается на RBAC, а не на `is_staff`.

---

### Phase 4 — Наблюдаемость и rollout

**Цель:** безопасно включить, наблюдать, откатить при необходимости.

Задачи:
- Метрики отказов: `rbac_permission_denied_total`.
- Логи deny с `user_id`, `perm`, `object_id`.
- Фича‑флаг: `RBAC_PERMISSIONS_ENABLED` (по умолчанию off → затем on).
- Документация: `docs/architecture/RBAC_PERMISSIONS.md`.

Выход:
- Управляемый rollout + мониторинг.

---

## Риски и меры

- **Рассинхрон уровней** → единая карта perm→уровень, тесты.
- **Сломанные list endpoints** → обязательная фильтрация по RBAC.
- **UI на is_staff** → перевод на `rbac.manage` с fallbacks.

---

## Критерии готовности

- `user.has_perm` покрывает все RBAC‑кейсы.
- DRF endpoints не используют прямые проверки RBAC вне backend.
- UI открывает RBAC страницу только при наличии `rbac.manage`.
- Нет утечек данных в list endpoints при отсутствии прав.
