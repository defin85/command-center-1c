# Operator Guide (SPA‑primary)

Цель: повседневное администрирование делается **только через SPA**, а Django Admin — **break‑glass** (write только для superuser).

## Доступ и вход

- Вход в SPA: `http://localhost:5173` (dev) → логин через JWT (API Gateway).
- Если что-то “не открывается/403” — проверь, что у пользователя есть права (RBAC) и что токен актуален.

## Основные экраны и типовые действия

### Clusters (`/clusters`)
- **Discover Clusters**: поиск кластеров на RAS (подхватывает новые).
- **Sync**: синхронизация инфобаз кластера.
- **Reset sync status**: “unlock stuck sync” (точечно или bulk по выбранным).

### Databases (`/databases`)
- Просмотр/поиск баз, фильтры по статусу/health.
- Операторские операции выполняются через Operations (ниже).

### Operations (`/operations`)
- **All Operations**: список batch-операций.
- **Live Monitor**: мониторинг конкретной операции (ссылка вида `/operations?tab=monitor&operation=<id>`).

### Templates (`/templates`)
- Просмотр шаблонов операций.
- **Sync from registry** (staff-only): синхронизация шаблонов из in-code registry.

### RBAC (`/rbac`)
- Выдача/отзыв прав на кластеры/базы.
- Проверка effective access.

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

- **Audit log** ключевых действий пишется в БД (`AdminActionAuditLog`) и доступен для просмотра в Django Admin (read-only для не‑superuser).
- **Prometheus metrics**: `cc1c_orchestrator_admin_actions_total{action=...,outcome=...}` — счётчик админ-действий (success/error).

## Django Admin (break‑glass)

- Любые write‑действия в админке предназначены только для superuser и могут быть заблокированы для обычных пользователей.
- Если “нужно срочно починить руками”, зафиксируй причину, действие и результат (audit/тикет) и вернись к SPA‑пути.

