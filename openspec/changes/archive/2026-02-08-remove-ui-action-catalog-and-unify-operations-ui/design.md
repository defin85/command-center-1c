## Context
Unified persistent контракт уже внедрён: templates и actions живут в `operation_definition` + `operation_exposure`.
При этом в системе остаются legacy артефакты:
- runtime setting key `ui.action_catalog`;
- отдельный staff-only UI `/settings/action-catalog`.

Это приводит к дублированию UX и лишним зависимостям от runtime settings в коде и тестах.

## Goals / Non-Goals
- Goals:
  - Удалить `ui.action_catalog` как поддерживаемый runtime setting key.
  - Оставить единый source of truth для actions: `operation_exposure(surface="action_catalog")`.
  - Объединить operator UI в один экран `/templates` с surface-переключением.
- Non-Goals:
  - Редизайн runtime consumer UX в `/databases` (использование effective action catalog сохраняется).
  - Изменение семантики plan/apply для `extensions.set_flags`.

## Decisions
- Decision 1: Один management UI
  - Route `/templates` становится единственной точкой управления template/action exposures.
  - Route `/settings/action-catalog` удаляется без compatibility redirect.
- Decision 2: Полный decommission `ui.action_catalog`
  - Ключ исключается из runtime settings registry и API-контрактов override/read/write.
  - В коде не остаётся fallback/чтения этого ключа для action resolution.
- Decision 3: Surface-aware RBAC в одном экране
  - В едином UI действия для `surface="action_catalog"` доступны только staff.
  - Пользователи без staff прав видят только template surface.

## Migration Plan
1. Обновить OpenSpec дельты и контракты.
2. Удалить backend runtime-setting key path (`ui.action_catalog`) и legacy тесты.
3. Консолидировать frontend UI в `/templates`, удалить отдельную страницу action-catalog.
4. Обновить OpenAPI/clients/tests и подтвердить поведение e2e.

## Risks / Trade-offs
- Риск: сломанные закладки/прямые ссылки на `/settings/action-catalog`.
  - Митигация: явно зафиксировать breaking в release notes.
- Риск: частичные удаления legacy кода оставят "мертвые" тесты/контракты.
  - Митигация: целевой grep/поиск по `ui.action_catalog` и обязательное обновление тестов/OpenAPI.
- Риск: смешение прав в едином UI.
  - Митигация: отдельный RBAC guard для surface `action_catalog` + frontend/backend проверки.

## Open Questions
- Нет блокирующих open questions для старта реализации.
