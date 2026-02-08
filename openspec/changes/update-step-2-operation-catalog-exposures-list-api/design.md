## Context
Шаг 1 даёт единый UI-реестр, но без обновления API список остаётся ограничен:
- неоднородные client-side фильтры,
- дополнительный запрос definitions,
- отсутствие полного server-driven contract для mixed-surface списка.

Шаг 2 закрепляет API как источник истины для list state.

## Goals
- Server-driven list для unified exposures.
- Predictable filtering/sorting/pagination на backend.
- Минимизация round-trip через include definition данных.
- Сохранение существующих RBAC и обратной совместимости.

## Non-Goals
- Новый UI shell/редизайн страницы.
- Изменение runtime execution/read model.

## Proposed API Behavior
- Endpoint: `GET /api/v2/operation-catalog/exposures/`
- Query params:
  - `surface=template|action_catalog|all` (или `all` по умолчанию только для staff);
  - `search`, `filters`, `sort`, `limit`, `offset`;
  - `include_definition=true` (или эквивалентное include-поле).
- Response:
  - `exposures[]`, `count`, `total`;
  - при include: definition данные (inline или `included_definitions` по `definition_id`).

## RBAC
- `surface=action_catalog` и `surface=all` остаются staff-only.
- non-staff с template-view правами работает через `surface=template`.
- include definition данных не должен раскрывать лишнее non-staff пользователям.

## Compatibility Strategy
- Старые клиенты продолжают работать без новых параметров.
- Новые поля в ответе добавляются расширяюще (без удаления существующих).
- UI переводится на новый контракт после backend readiness.

## Trade-offs
- Inline definition упрощает клиент, но может дублировать payload.
- `included_definitions` экономит размер ответа, но усложняет клиентский маппинг.
- Для первого шага API-расширения предпочтителен предсказуемый и простой вариант, затем можно оптимизировать при необходимости.
