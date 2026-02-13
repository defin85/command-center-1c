# Change: Довести UI каталога организаций до операционного управления

## Why
Страница `/pools/catalog` предоставляет только read-only просмотр каталога организаций и графа пулов, при этом API для изменения данных уже существует (`/api/v2/pools/organizations/upsert/`, `/api/v2/pools/organizations/sync/`).

В результате операторы вынуждены выполнять мутации через ручные HTTP-запросы, что повышает риск ошибок, усложняет массовую синхронизацию и снижает прозрачность tenant-safe поведения.

## What Changes
- Расширить UI `/pools/catalog` до операторского режима управления организациями:
  - добавить create/edit форму организации (upsert) на базе существующего API;
  - добавить bulk sync модалку для синхронизации списка организаций;
  - добавить явный результат синхронизации (`created/updated/skipped`, общее число строк).
- Зафиксировать tenant-safe поведение mutating действий в UI:
  - mutating controls отключаются при отсутствии активного tenant context;
  - пользователь получает явное пояснение причины блокировки.
- Зафиксировать preflight-валидацию payload в UI до отправки bulk sync:
  - базовая проверка обязательных полей и статусов;
  - ранняя остановка при некорректном payload с user-facing ошибками.
- Зафиксировать маппинг доменных backend-ошибок (`DATABASE_ALREADY_LINKED`, `DUPLICATE_ORGANIZATION_INN`, `DATABASE_NOT_FOUND`, `VALIDATION_ERROR`) в понятные UI-сообщения.
- Добавить frontend тесты (unit/browser smoke) для ключевых пользовательских сценариев управления каталогом.

## Impact
- Affected specs:
  - `organization-pool-catalog`
- Affected code (expected):
  - `frontend/src/pages/Pools/PoolCatalogPage.tsx`
  - `frontend/src/api/intercompanyPools.ts` (без изменения контракта, только интеграция)
  - `frontend/src/api/queries/databases.ts` (переиспользование для выбора `database_id`)
  - `frontend/tests/**` (новые/обновлённые UI тесты)

## Non-Goals
- Добавление нового backend endpoint для прямого pull из ИБ в рамках этого change.
- Изменение доменных инвариантов каталога организаций (`organization <-> database` остаётся `1:1`).
- Введение новой RBAC-модели за пределами tenant-safe guard в UI.

