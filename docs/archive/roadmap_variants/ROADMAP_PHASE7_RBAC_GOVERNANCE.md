# Roadmap: Phase 7 — RBAC и governance (универсальные роли + schema-driven команды)
> **Статус:** DRAFT
> **Версия:** 1.0
> **Создан:** 2026-01-07
> **Автор:** Codex

Связанные документы:
- `docs/roadmaps/ROADMAP_IBCMD_SCHEMA_DRIVEN_COMMANDS.md` (Phase 7 в составе schema-driven IBCMD/CLI)

---

## Контекст и цель

Нужно получить модель прав, похожую на 1C:
- администратор **создаёт роль** (Django Group),
- в роли задаёт **права** (что можно делать) и **доступ к объектам** (над чем можно делать),
- пользователь получает доступ просто через назначение ролей,
- проверки прав единообразны и консистентны с Django (`user.has_perm(...)`),
- для schema-driven команд (driver catalogs v2) опасные команды **полностью скрыты** для non-staff.

Ограничения/драйверы:
- минимальная латентность (без внешних policy-сервисов на критическом пути),
- 700+ баз: нельзя плодить записи/проверки на каждую базу без иерархий и batch,
- audit и управляемость изменений (governance),
- coverage > 70%.

---

## Требования (зафиксировано)

1) Роли: только Django groups + `is_staff`.
2) 4-eyes (двухэтапное согласование) не требуется.
3) `risk_level=dangerous` команды:
   - non-staff: **не видят** в каталоге,
   - non-staff: **не могут исполнить** (enforce на backend).

---

## Модель доступа (рекомендуемая)

Разделяем "что" и "над чем":

### 1) Capabilities ("что можно")

Источник истины: Django permissions (`auth_permission`) и назначение permissions группам/пользователям.

Пример:
- `operations.execute_safe_operation`
- `operations.execute_dangerous_operation`
- `operations.manage_driver_catalogs`
- `templates.manage_operation_template`
- `templates.manage_workflow_template`
- `templates.execute_workflow_template`
- `artifacts.manage_artifact`
- `artifacts.upload_artifact_version`
- `artifacts.download_artifact_version`
- `databases.manage_rbac`

Примечания:
- `view_*` не кастомизируем: используем стандартные Django permissions `view_<model>`.
- Константы кодов: `orchestrator/apps/core/permission_codes.py`.

### 2) Scope ("над чем можно")

Источник истины: bindings (RoleBinding) + уровни `PermissionLevel` (VIEW/OPERATE/MANAGE/ADMIN).

Важно для массовых объектов: используем **иерархии**, чтобы не выдавать права поштучно на 700+ объектов.

Иерархии (MVP):
- `Cluster -> Database` (права на кластер распространяются на базы в кластере)
- `WorkflowTemplate -> WorkflowExecution` (права на шаблон распространяются на исполнения)
- `Artifact -> ArtifactVersion/ArtifactAlias` (права на артефакт распространяются на версии/алиасы)

---

## Архитектурный выбор: Django-native vs Casbin/OPA

Выбранный вариант для Phase 7: **Django-native (Groups + Permissions + Bindings)**.

Почему:
- консистентность с Django permissions (admin/UI/DRF),
- минимум инфраструктуры и сетевых зависимостей,
- лучше контролируемая производительность (batch + кэш).

Casbin/OPA рассматриваются как опции на будущее, если:
- потребуется enforcement в нескольких сервисах/языках без общего слоя,
- появятся сложные ABAC-условия и необходимость централизованной политики.

---

## План работ (этапы)

### Phase 7.1 — Нормализация ролей и capability-permissions

Цель: единый словарь permissions и принципов, чтобы API не жил на `is_staff`.

Задачи:
- Зафиксировать naming convention: `<app>.<action>_<resource>` или `<app>.<action>`.
- Сформировать матрицу capabilities для основных доменов:
  - Databases/Clusters: view/operate/manage/admin
  - Templates/Workflows: view/manage/execute
  - Artifacts: view/manage/upload/download/delete
  - Driver catalogs: view (staff-only), import/promote/overrides.update (staff-only)
  - Operations: execute_safe/execute_dangerous/cancel/view_logs
- Зафиксировать policy по `view_*`: используем стандартные Django permissions `view_<model>` (без кастомных `view_*`).
- Добавить/уточнить Django permissions (миграциями или через `Meta.permissions`).
- Документировать mapping permission -> required `PermissionLevel` (см. подплан "RBAC ↔ Django permissions" ниже).

Выход:
- Permissions есть, назначаются ролям (Groups) в админке/SPA.

---

### Phase 7.2 — Универсальные bindings (scope) для ролей и пользователей

Цель: выдать доступ к объектам не хардкодом, а через универсальные привязки.

Рекомендуемый MVP-дизайн данных:
- Сохранить текущие `ClusterPermission`/`DatabasePermission` (user-level) как fast-path.
- Добавить group-level аналоги:
  - `ClusterGroupPermission(group, cluster, level, granted_by, notes, granted_at)`
  - `DatabaseGroupPermission(group, database, level, ...)`
- Для остальных доменов использовать отдельные таблицы (по перф и простоте):
  - `OperationTemplatePermission(user, template, level, ...)`
  - `OperationTemplateGroupPermission(group, template, level, ...)`
  - `WorkflowTemplatePermission(user, workflow_template, level, ...)` (наследуется на executions)
  - `WorkflowTemplateGroupPermission(group, workflow_template, level, ...)` (наследуется на executions)
  - `ArtifactPermission(user, artifact, level, ...)` (наследуется на versions/aliases)
  - `ArtifactGroupPermission(group, artifact, level, ...)` (наследуется на versions/aliases)

Почему так:
- кластеры/базы уже оптимизированы под batch и фильтрацию,
- workflow/artifacts можно подключать по мере готовности без большого рефактора.

Задачи:
- Расширить `PermissionService`:
  - учитывать права групп пользователя,
  - поддержать inheritance (cluster->database, template->execution, artifact->version/alias),
  - сохранить batch-check API.
- Добавить индексы под bulk-check и list-filtering.

Выход:
- Можно назначить группе OPERATE на кластер и получить доступ ко всем базам кластера.
- Можно назначить группе доступ к WorkflowTemplate и автоматически к его executions.
- Можно назначить группе доступ к Artifact и автоматически к версиям/алиасам.

---

### Phase 7.3 — Единая точка проверок: `user.has_perm(..., obj)`

Цель: DRF и сервисы проверяют права единообразно.

Задачи:
- Реализовать `RBACPermissionBackend` (см. подплан "RBAC ↔ Django permissions" ниже), расширив его:
  - поддержкой Templates/Workflows/Artifacts,
  - поддержкой group-bindings,
  - поддержкой inheritance.
- Вынести mapping perm->required_level в единый модуль (конфиг/таблица/константы).
- Перевести DRF permissions (где возможно) на `user.has_perm(...)`.

Выход:
- Уменьшается хардкод "если staff" и "если created_by".
- Появляется единый контракт для backend и UI-гейтинга.

---

#### Подплан: RBAC ↔ Django permissions (встроено)

Ранее это был отдельный документ `docs/roadmaps/ROADMAP_RBAC_DJANGO_PERMISSIONS.md`. Теперь подплан встроен сюда,
чтобы Phase 7 имел один источник истины.

##### Цель

Сделать объектный RBAC (уровни/скоуп) единым источником истины, но использовать стандартный интерфейс Django
(`user.has_perm(<perm>, obj)`) для всех проверок в DRF, бизнес‑сервисах и UI‑гейтинге.

##### Текущее состояние (as-is)

- RBAC хранится в Django моделях: `ClusterPermission`, `DatabasePermission` (и будущие group-bindings).
- Логика прав: `PermissionService` в `orchestrator/apps/databases/services.py`.
- Проверки в DRF: часть эндпоинтов использует `PermissionService`, часть — `IsAdminUser`/`is_staff`.

##### Принципы

- Capabilities (что можно): Django permissions + назначение группам/пользователям.
- Scope/levels (над чем можно): RBAC модели/bindings + `PermissionLevel`.
- Объектные права не синхронизируются в `auth_permission` (только capabilities).
- `is_staff` остаётся admin‑bypass там, где это осознанно нужно (но постепенно заменяется явными permissions).

##### Карта permissions (минимум для Database/Cluster)

Clusters:
- `databases.view_cluster` → VIEW (Django default `view_<model>`)
- `databases.operate_cluster` → OPERATE
- `databases.manage_cluster` → MANAGE
- `databases.admin_cluster` → ADMIN

Databases:
- `databases.view_database` → VIEW (Django default `view_<model>`)
- `databases.operate_database` → OPERATE
- `databases.manage_database` → MANAGE
- `databases.admin_database` → ADMIN

Примечание:
- Строки permissions централизованы в `orchestrator/apps/core/permission_codes.py` (чтобы не плодить хардкод).

RBAC управление (не объектное):
- `databases.manage_rbac` → доступ к RBAC endpoints (list/grant/revoke и group-bindings)

##### Шаги реализации

###### 7.3.1 — Core backend + mapping

Цель: включить `user.has_perm(...)` поверх RBAC.

Задачи:
- Добавить `apps/databases/auth_backends.py` с `RBACPermissionBackend`:
  - `has_perm(user, perm, obj=None)` с маппингом perm→PermissionLevel,
  - `has_module_perms(user, app_label)` для UI/админки.
- Описать карту perm→уровень (константы в `apps/databases/permissions_map.py`).
- Подключить backend в `AUTHENTICATION_BACKENDS`.
- Тесты на `has_perm` для cluster/database (VIEW/OPERATE/MANAGE/ADMIN).

Выход:
- `user.has_perm("databases.manage_database", database)` работает.
- `user.has_perm("databases.view_cluster", cluster)` работает.

---

###### 7.3.2 — DRF интеграция

Цель: единая проверка в API и объектная фильтрация.

Задачи:
- Переписать `HasDatabasePermission`/`HasClusterPermission` на `user.has_perm`.
- Добавить общий mixin/permission для action‑уровней.
- Фильтрация списков: использовать `PermissionService.filter_accessible_*` в queryset (list endpoints).
- Логирование отказов и единый error format.

Выход:
- Все API‑эндпоинты используют единый механизм.
- Утечки по list исключены (фильтрация по RBAC).

---

###### 7.3.3 — RBAC администрирование

Цель: убрать `IsAdminUser` как «магическое» условие, оставить явный permission.

Задачи:
- Заменить `IsAdminUser` в `apps/api_v2/views/rbac.py` на `databases.manage_rbac` через `user.has_perm`.
- Обновить UI‑гейтинг: RBAC страница доступна по `databases.manage_rbac`.
- Добавить `EffectiveAccess` endpoints для UI везде, где нужны «права по объектам».

Выход:
- Управление RBAC доступно по явному permission.
- UI опирается на RBAC, а не на `is_staff`.

---

###### 7.3.4 — Наблюдаемость и rollout

Цель: безопасно включить, наблюдать, откатить при необходимости.

Задачи:
- Метрики отказов: `rbac_permission_denied_total`.
- Логи deny с `user_id`, `perm`, `object_id`.
- Фича‑флаг: `RBAC_PERMISSIONS_ENABLED` (по умолчанию off → затем on).
- Документация: `docs/architecture/RBAC_PERMISSIONS.md`.

Выход:
- Управляемый rollout + мониторинг.

---

### Phase 7.4 — RBAC для schema-driven команд (driver catalogs v2)

Цель: управлять доступностью команд через каталог, скрывать dangerous для non-staff, enforce на исполнении.

Задачи (backend):
- Зафиксировать `command.permissions` (v2):
  - `allowed_roles: string[]` (group names + `staff`)
  - `denied_roles: string[]`
  - (опц.) `min_db_level: operate|manage|admin` (переопределение risk->level)
  - (опц.) `allowed_envs/denied_envs`
  - `tags: string[]` для UI/поиска/аудита
- Реализовать `filter_catalog_for_user(user, catalog)`:
  - non-staff: удалять команды `risk_level=dangerous`,
  - применять allow/deny списки,
  - скрывать `disabled=true`.
- Исполнение (`ibcmd_cli`):
  - команду резолвить только из уже отфильтрованного каталога,
  - при deny отвечать как "unknown command" (не раскрывать наличие).
- Кэширование:
  - сделать ETag roles-aware (base_version_id + overrides_version_id + roles_hash),
  - `Cache-Control: private`.
- Аудит:
  - в `BatchOperation.metadata` писать: `command_id`, `risk_level`, `scope`, `actor_roles`,
    `catalog_base_version`, `catalog_overrides_version`.
- Метрики/логи deny для команд.

Задачи (governance):
- Управление каталогами остаётся staff-only, но добавить:
  - обязательный `reason` (ticket/описание) в endpoints update/promote/overrides,
  - audit log на каждую операцию (частично уже есть).

Выход:
- non-staff не видит dangerous команды и не может их запускать.
- Доступ к safe командам можно ограничивать ролями через overrides без деплоя.

---

### Phase 7.5 — Администрирование RBAC (SPA-primary) и аудит

Цель: управлять ролями/доступами безопасно и прозрачно.

Задачи:
- Расширить `/api/v2/rbac/*`:
  - добавить операции для group-bindings (list/grant/revoke),
  - добавить effective-access endpoints для UI по Templates/Workflows/Artifacts.
- Гейтинг RBAC админки:
  - перейти с `IsAdminUser` на явный permission (`databases.manage_rbac`) через `user.has_perm`.
- Включить audit (admin_action_audit) для:
  - всех grant/revoke,
  - bulk-операций (важно при массовых назначениях),
  - экспорт/импорт настроек (если добавится).

Выход:
- Управление доступами не завязано на "все staff могут всё" (по необходимости).
- Есть трассируемость "кто дал/забрал доступ и зачем".

---

### Phase 7.6 — Rollout, фича-флаги, качество

Цель: безопасно включить, наблюдать, откатывать.

Задачи:
- Фича-флаги:
  - `RBAC_PERMISSIONS_ENABLED` (включает backend `user.has_perm` поверх RBAC),
  - `DRIVER_CATALOG_RBAC_ENABLED` (включает фильтрацию каталога по ролям),
  - `RBAC_GROUP_BINDINGS_ENABLED` (учёт group-bindings в PermissionService).
- Тесты:
  - unit: `filter_catalog_for_user`, roles-aware ETag, RBAC backend mappings,
  - API: non-staff не видит/не запускает dangerous, staff видит,
  - API: group-binding даёт доступ к cluster->databases,
  - regression: list endpoints не текут.
- Наблюдаемость:
  - метрики deny (`rbac_permission_denied_total`, `driver_command_denied_total`),
  - structured logs deny (user_id, roles, perm, object/ref).
- План отката:
  - отключить фича-флаги,
  - откатить alias overrides/base в artifacts (для каталога команд).

Выход:
- Управляемый запуск без простоя и с ясным rollback.

---

## Критерии готовности (Definition of Done)

- Роли управляются через Django Groups, capabilities через Django permissions.
- Для Database/Cluster и минимум для WorkflowTemplate/Artifact доступны group-bindings.
- `user.has_perm(..., obj)` работает для основных доменов и используется в DRF.
- `filter_catalog_for_user` скрывает dangerous от non-staff и enforce на execute.
- ETag driver-commands учитывает роли пользователя (нет stale кэша при смене групп).
- Все админские изменения RBAC и каталогов имеют audit и reason.
- Покрытие тестами не ниже целевого.

---

## Риски и меры

- Риск: N+1 и тяжёлые list-фильтры (массовые объекты).
  - Мера: batch-check, индексы, контейнеры и inheritance, request-cache.
- Риск: рассинхрон "что" (Django perms) и "над чем" (bindings).
  - Мера: единый контракт `authorize(user, perm, obj)` и единая матрица mapping.
- Риск: ошибка в overrides каталога скрывает команды всем.
  - Мера: rollback alias `active`, минимальные дефолты (safe visible, dangerous staff-only).
