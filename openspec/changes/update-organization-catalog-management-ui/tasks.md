## 1. UI controls для управления организациями
- [ ] 1.1 Добавить в `PoolCatalogPage` mutating controls: `Add organization`, `Edit`, `Sync catalog`.
- [ ] 1.2 Реализовать `Drawer + Form` для create/edit c payload `upsert` (`inn`, `name`, `status`, `database_id`, optional поля).
- [ ] 1.3 Подключить список баз для выбора `database_id` через существующий query-layer (`list-databases`) без нового API.

## 2. Bulk sync UX
- [ ] 2.1 Реализовать `Sync catalog` modal c вводом bulk payload (JSON/file) и базовой preflight-валидацией строк.
- [ ] 2.2 Отображать результат sync (`created`, `updated`, `skipped`, `total_rows`) и обновлять список организаций после успешной операции.
- [ ] 2.3 Реализовать user-friendly обработку ошибок preflight и backend validation.

## 3. Tenant-safe поведение
- [ ] 3.1 Добавить guard: mutating actions disabled без активного tenant context.
- [ ] 3.2 Добавить предупреждение с причиной блокировки и ожидаемым действием пользователя.

## 4. Доменные ошибки и UX-прозрачность
- [ ] 4.1 Добавить маппинг backend error codes (`DATABASE_ALREADY_LINKED`, `DUPLICATE_ORGANIZATION_INN`, `DATABASE_NOT_FOUND`, `VALIDATION_ERROR`, `TENANT_CONTEXT_REQUIRED`) в понятные UI-сообщения.
- [ ] 4.2 Добавить безопасный fallback для неизвестных ошибок без потери контекста операции.

## 5. Тесты и валидация
- [ ] 5.1 Добавить frontend unit-тесты для preflight-валидации и error mapping.
- [ ] 5.2 Добавить browser smoke-тесты для сценариев create/edit/sync и tenant-disabled path на `/pools/catalog`.
- [ ] 5.3 Прогнать `openspec validate update-organization-catalog-management-ui --strict --no-interactive`.

