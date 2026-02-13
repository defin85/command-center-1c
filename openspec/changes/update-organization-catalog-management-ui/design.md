## Context
- Текущая реализация `PoolCatalogPage` поддерживает только read-only операции (list/detail/graph), но backend уже предоставляет mutating API для организаций.
- На backend уже зафиксированы доменные ограничения:
  - обязательные `inn` и `name` для upsert;
  - tenant-scoped проверка `database_id`;
  - уникальность связи `organization <-> database` как `1:1`.
- Цель change: закрыть UX/операционный разрыв без расширения backend-контракта.

## Goals / Non-Goals
- Goals:
  - Дать оператору UI-путь для create/edit/sync организаций без использования curl.
  - Снизить число backend round-trip ошибок за счёт preflight-проверок на клиенте.
  - Сделать mutating действия tenant-safe и предсказуемыми.
- Non-Goals:
  - Проектировать новый ingestion pipeline “прямой импорт из ИБ”.
  - Менять контракт `POST /api/v2/pools/organizations/upsert/` и `POST /api/v2/pools/organizations/sync/`.

## Decisions
### Decision 1: Reuse existing `/pools/catalog` page as single operator workspace
- Почему:
  - текущая информация (фильтры, таблица, детали) уже находится на странице;
  - минимальный UX friction и минимальные изменения маршрутизации.
- Следствие:
  - create/edit/sync controls размещаются в секции `Organizations`, граф пулов остаётся отдельным read-only блоком.

### Decision 2: Upsert через `Drawer + Form`, bulk sync через `Modal`
- Почему:
  - соответствует текущим паттернам проекта на Ant Design;
  - позволяет сохранить контекст списка организаций при редактировании;
  - bulk sync не требует отдельной страницы на первом этапе.
- Следствие:
  - create/edit: один form contract под payload `upsert`;
  - sync: модалка с вводом payload (JSON/file), preflight и отчётом результата.

### Decision 3: Tenant-safe guard в UI для mutating действий
- Почему:
  - mutating API требует корректный tenant context;
  - уменьшает риск неявных cross-tenant мутаций у staff-пользователей.
- Следствие:
  - при отсутствии `active_tenant_id` mutating controls disabled;
  - показывается warning с причиной и инструкцией выбрать tenant.

### Decision 4: Preflight-валидация ограничивается базовыми проверками
- Почему:
  - минимальная реализация должна быть простой и надёжной;
  - backend остаётся source-of-truth для доменных конфликтов.
- Проверки:
  - структура `rows` как непустой массив;
  - обязательные `inn`/`name` в каждой строке;
  - допустимые `status` (`active|inactive|archived`);
  - базовая проверка формата `database_id` (если задан).

### Decision 5: Явный error mapping backend-кодов в UI
- Почему:
  - операторам нужны actionable сообщения вместо generic “failed”.
- Покрываемые коды:
  - `DATABASE_ALREADY_LINKED`
  - `DUPLICATE_ORGANIZATION_INN`
  - `DATABASE_NOT_FOUND`
  - `VALIDATION_ERROR`
  - `TENANT_CONTEXT_REQUIRED`

## Alternatives Considered
- Отдельная новая страница “Organizations Admin”:
  - Плюс: изоляция mutating UI.
  - Минус: дублирование существующего каталога и фильтров, больше миграционных затрат.
  - Решение: отклонено как избыточное для текущего scope.
- Прямой sync из ИБ (кнопка “pull from 1C”):
  - Плюс: меньше ручных действий для оператора.
  - Минус: требует новый backend контракт, доступы и политику безопасности.
  - Решение: вынесено за рамки change.

## Risks / Trade-offs
- Риск: preflight может не поймать все доменные ошибки.
  - Митигация: backend остаётся финальным валидатором, UI показывает детальные доменные ошибки.
- Риск: bulk sync с большим payload ухудшит UX.
  - Митигация: стартово ограничить размер payload и дать прозрачный отчёт результата.
- Риск: недостаточное тестовое покрытие mutating сценариев.
  - Митигация: добавить browser smoke и unit-тесты для error mapping/preflight.

## Rollout Plan
1. Добавить UI controls и интеграцию upsert/sync на `/pools/catalog`.
2. Добавить tenant-safe disable path и предупреждения.
3. Добавить preflight + error mapping.
4. Добавить frontend тесты ключевых сценариев.
5. Провести валидацию OpenSpec change и подготовить к apply stage.

