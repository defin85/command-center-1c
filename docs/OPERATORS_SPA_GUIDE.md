# Operator Guide (SPA‑primary)

Цель: повседневное администрирование делается **только через SPA**, а Django Admin — **break‑glass** (write только для staff).

## Доступ и вход

- Вход в SPA: `http://localhost:15173` (dev) → логин через JWT (API Gateway).
- Если что-то “не открывается/403” — проверь, что у пользователя есть права (RBAC) и что токен актуален.

## Основные экраны и типовые действия

### Clusters (`/clusters`)
- **Discover Clusters**: поиск кластеров на RAS (подхватывает новые).
- **Sync**: синхронизация инфобаз кластера.
- **Reset sync status**: “unlock stuck sync” (точечно или bulk по выбранным).

### Databases (`/databases`)
- Просмотр/поиск баз, фильтры по статусу/health.
- Операторские операции выполняются через Operations (ниже).

### Extensions (`/extensions`)
- Основной путь для массового `extensions.set_flags`: workflow-first запуск с явным runtime input (`flags_values` + `apply_mask`).
- Точечный режим (single DB) оставлен как fallback для аварийных случаев.
- Progress/результат отслеживать в `/operations`.
- Детальный runbook: [extensions-set-flags-workflow-first.md](./extensions-set-flags-workflow-first.md)

### Operations (`/operations`)
- **All Operations**: список batch-операций.
- **Live Monitor**: мониторинг конкретной операции (ссылка вида `/operations?tab=monitor&operation=<id>`).

### Templates (`/templates`)
- Просмотр шаблонов операций.
- **Sync from registry** (staff-only): синхронизация шаблонов из in-code registry.
- Create/Edit для custom CLI templates выполняется через тот же tabbed editor, что и Action Catalog (`Basics / Executor / Params / Safety & Fixed / Preview`).
- В editor больше нет ручного выбора `driver`: для `executor.kind=designer_cli` используется canonical `driver=cli`.

### Action Catalog (`/templates?surface=action_catalog`)
- Управление actions выполняется на едином экране `/templates` во вкладке `Action Catalog` (staff-only).
- Source of truth: `operation_exposure(surface=\"action_catalog\")` + `operation_definition` (без runtime setting `ui.action_catalog`).
- Guided + Raw JSON, diff/preview и Save через unified operation-catalog API.
- `driver` не выбирается вручную: backend/UI используют canonical mapping `ibcmd_cli->ibcmd`, `designer_cli->cli`, `workflow->driver not applicable`.
- Подробная инструкция: [ACTION_CATALOG_GUIDE.md](./ACTION_CATALOG_GUIDE.md)

### Command Schemas (`/settings/command-schemas`)
- Редактирование схем команд для `cli`/`ibcmd` (driver catalogs v2) через UI (save/validate/preview/diff/rollback).
- Доступ: `is_staff=true` + право `operations.manage_driver_catalogs` (иначе будет 403/скрытый пункт меню).
- Любые write-действия требуют `reason` и попадают в audit log.

#### Как импортировать ITS (base catalog)
- В UI: `/settings/command-schemas` → выбрать driver (`CLI`/`IBCMD`) → `Import ITS...` → выбрать ITS JSON → указать `reason` → `Import`.
- Endpoint: `POST /api/v2/settings/command-schemas/import-its/`
- Body: `driver=cli|ibcmd`, `its_payload={...}`, `save=true|false`, `reason="..."`
- Примечания:
  - `cli`: импортирует legacy catalog и публикует v2 base artifact.
  - `ibcmd`: строит v2 base artifact из ITS и публикует его.

#### CLI: как опубликовать legacy catalog (bootstrap)
Если для `cli` уже есть `config/cli_commands.json`, но base-артефакта еще нет, редактор покажет предупреждение и предложит опубликовать base.

- В UI: вкладка `CLI` → `Publish...` → указать `reason` → подтвердить.
- Через API: `POST /api/v2/settings/command-schemas/bootstrap-cli/`
  - Body: `reason="..."`

#### Как откатывать overrides (rollback)
- В UI: `Rollback` → выбрать версию `ovr-*` → указать `reason` → применить.
- Через API: `POST /api/v2/settings/command-schemas/overrides/rollback/`
  - Body: `driver`, `version` (или `version_id`), `reason`, опционально `expected_etag` (409 при конфликте).

#### Рекомендации (permissions / risk_level)
- `risk_level=dangerous` ставь только для реально опасных действий; UI требует подтверждение при смене safe->dangerous.
- `disabled=true` используй как break-glass выключатель; включение disabled команды требует подтверждение.
- `permissions` держи максимально строгими: минимизируй `allowed_roles/allowed_envs`, не ослабляй `min_db_level` без явной причины.

#### Аудит и метрики
- Audit endpoint: `GET /api/v2/settings/command-schemas/audit/` (фильтр по `driver=cli|ibcmd`).
- Prometheus:
  - `cc1c_orchestrator_admin_actions_total{action="driver_catalog.overrides.update|driver_catalog.overrides.rollback|driver_catalog.promote|driver_catalog.import_its",outcome="success|error"}`
  - `cc1c_orchestrator_driver_catalog_editor_conflicts_total{driver=...,action="overrides.update|overrides.rollback"}`
  - `cc1c_orchestrator_driver_catalog_editor_validation_failed_total{driver=...,stage="overrides.update|import_its|validate",kind="invalid_overrides|invalid_effective|invalid_parsed"}`
  - `cc1c_orchestrator_driver_catalog_editor_errors_total{driver=...,action=...,code=...}` (все error-коды, включая `PERMISSION_DENIED`, `BASE_CATALOG_MISSING`, `INVALID_ALIAS`, `VERSION_NOT_FOUND`, `SAVE_FAILED`)

### RBAC (`/rbac`)
- Выдача/отзыв прав на ресурсы (clusters/databases/templates/workflows/artifacts).
- Проверка **effective access** (итоговый доступ + источники).
- Любые изменения требуют **reason** и попадают в **Audit** (вкладка `Audit`).

#### Как выдать доступ на конкретную ИБ (Database)
- Открой `/rbac` → режим **Назначения** → вкладка **Доступ к объектам**.
- Выбери тип ресурса: **Databases**.
- Вариант A (обычно проще): режим **Кто → Где**
  - выбери **User/Role**;
  - в `Resource` выбери нужную ИБ;
  - укажи `Level` и `Reason`, нажми `Grant`.
- Вариант B: режим **Где → Кто**
  - слева выбери ИБ (дерево clusters→databases);
  - справа смотри назначения и выдавай доступ через блок “Выдать доступ”.
- После изменений обязательно проверь вкладку **Effective access** (см. ниже).

#### Как смотреть effective access
- `/rbac` → режим **Назначения** → вкладка **Effective access**.
- Выбери пользователя и тип ресурса (например, **Databases**).
- Опционально укажи конкретный ресурс для фильтра (для clusters/databases — через дерево).
- В таблице: строка = **итог**, раскрытие строки = **источники** (direct/group/cluster/database/...).

### DLQ (`/dlq`)
- Просмотр DLQ сообщений воркера (Redis Stream) с фильтрами.
- **Retry** (single/bulk): безопасный re-enqueue операции (sequential).
- Для операций с `operation_id` есть переход в Live Monitor.

### Tracing (Jaeger)
- Трейсы доступны через proxy в API Gateway (`/api/v2/tracing/*`) и используются SPA (Trace viewer).

## Что делать, если…

- **Sync “застрял”**: `/clusters` → `Reset sync status` → затем `Sync`.
- **Операция упала**: `/operations` → открыть details/monitor → если падение из DLQ — `/dlq` → `Retry`.
- **Нужно выдать доступ пользователю**: `/rbac` (grant/revoke) → перепроверить effective access.

## Контроль (аудит/метрики)

- **Audit log** ключевых действий пишется в БД (`AdminActionAuditLog`) и доступен для просмотра в Django Admin (read-only для не‑staff).
- **Prometheus metrics**: `cc1c_orchestrator_admin_actions_total{action=...,outcome=...}` — счётчик админ-действий (success/error).

## Django Admin (break‑glass)

- Любые write‑действия в админке предназначены только для staff и могут быть заблокированы для обычных пользователей.
- Если “нужно срочно починить руками”, зафиксируй причину, действие и результат (audit/тикет) и вернись к SPA‑пути.
