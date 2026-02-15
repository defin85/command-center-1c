## 1. UI controls для управления организациями
- [x] 1.1 Добавить в `PoolCatalogPage` mutating controls: `Add organization`, `Edit`, `Sync catalog`.
- [x] 1.2 Реализовать `Drawer + Form` для create/edit c payload `upsert` (`inn`, `name`, `status`, `database_id`, optional поля).
- [x] 1.3 Подключить список баз для выбора `database_id` через существующий query-layer (`list-databases`) без нового API.
- [x] 1.4 Зафиксировать в UI/документации authz-границу change: без новой RBAC-модели, в рамках текущего доступа к `/pools/catalog`.

## 2. Bulk sync UX
- [x] 2.1 Реализовать `Sync catalog` modal c вводом bulk payload в формате JSON (`rows[]`) и базовой preflight-валидацией строк.
- [x] 2.2 Отображать результат sync (`created`, `updated`, `skipped`, `total_rows`) и обновлять список организаций после успешной операции.
- [x] 2.3 Реализовать user-friendly обработку ошибок preflight и backend validation (включая field-level serializer errors).
- [x] 2.4 Добавить UI-лимит размера bulk payload (MVP: до 1000 строк за один submit).

## 3. Tenant-safe поведение
- [x] 3.1 Добавить guard: для staff mutating actions disabled без активного tenant context (`active_tenant_id`).
- [x] 3.2 Для non-staff сохранить поведение на server-resolved tenant context без лишней UI-блокировки.
- [x] 3.3 Добавить предупреждение с причиной блокировки и ожидаемым действием пользователя.

## 4. Доменные ошибки и UX-прозрачность
- [x] 4.1 Добавить маппинг backend error codes (`DATABASE_ALREADY_LINKED`, `DUPLICATE_ORGANIZATION_INN`, `DATABASE_NOT_FOUND`, `ORGANIZATION_NOT_FOUND`, `TENANT_NOT_FOUND`, `VALIDATION_ERROR`, `TENANT_CONTEXT_REQUIRED`) в понятные UI-сообщения.
- [x] 4.2 Добавить безопасный fallback для неизвестных ошибок без потери контекста операции.

## 5. Тесты и валидация
- [x] 5.1 Добавить frontend unit-тесты для preflight-валидации и error mapping.
- [x] 5.2 Добавить browser smoke-тесты для сценариев create/edit/sync, tenant-disabled path для staff и non-staff path без лишней блокировки на `/pools/catalog`.
- [x] 5.3 Прогнать `openspec validate update-organization-catalog-management-ui --strict --no-interactive`.
