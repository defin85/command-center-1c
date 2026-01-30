# Change: Единая точка ответственности за tenant context

## Why
Сейчас tenant context устанавливается в нескольких местах (аутентификация/permission/проверки в отдельных view), из‑за чего:
- поведение становится неочевидным и легко ломается тестами/утилитами (например, `force_authenticate`),
- часть кода опирается на thread-local tenant, часть — на `request.tenant_id`,
- повышается риск “тихих” рассинхронизаций и неполной tenant-изоляции.

Цель — сделать tenant context **единой точкой ответственности** (single source of truth) с прозрачным контрактом и минимальным числом механизмов.

## What Changes
- Зафиксировать контракт tenant context: как он выбирается (header → preference → membership), когда обязателен, какие ошибки возвращаются.
- Свести установку tenant context к **одному механизму** (и одному месту в коде), исключив дублирующие “подстраховки” в permission/view.
- Обновить тестовую инфраструктуру так, чтобы она проверяла реальный pipeline (без зависимости от `force_authenticate`).
- Обновить OpenAPI контракт `contracts/orchestrator/openapi.yaml` (security schemes + заголовки tenant, если применимо).

## Impact
- Затронутые области: `apps.tenancy.*`, tenant-scoped API v2 эндпоинты, тесты `apps/api_v2/tests/*`, OpenAPI экспорт/генерация маршрутов gateway.
- Потенциально breaking: изменение того, где и как выставляется `request.tenant_id`/thread-local tenant (при сохранении внешнего API поведения).

## Non-Goals
- Не меняем модель tenancy (Tenant/TenantMember) и бизнес-логику plan/apply/snapshots.
- Не добавляем мультиязычность UI.

