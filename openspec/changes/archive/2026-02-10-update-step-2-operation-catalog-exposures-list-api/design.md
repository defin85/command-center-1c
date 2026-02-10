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
  - `surface=template|action_catalog|all`:
    - канонически staff unified-list вызывается без `surface`,
    - `surface=all` поддерживается как явный алиас (backward compatibility/deep-link);
  - `search`, `filters`, `sort`, `limit`, `offset`;
  - `include=definitions` (расширяемый include-механизм).
- Response:
  - `exposures[]`, `count`, `total`;
  - при `include=definitions`: top-level `definitions[]` (side-loading, unique-by-id для текущей страницы `exposures[]`).
  - `exposures[]` сохраняет связь через `definition_id`; inline embedding definition в exposure не используется.

### Response Shape Example (`include=definitions`)
```json
{
  "exposures": [
    { "id": "exp-1", "definition_id": "def-1", "surface": "template" },
    { "id": "exp-2", "definition_id": "def-1", "surface": "action_catalog" }
  ],
  "definitions": [
    { "id": "def-1", "executor_kind": "ibcmd_cli", "executor_payload": {} }
  ],
  "count": 2,
  "total": 100
}
```

## RBAC
- `surface=action_catalog` и `surface=all` остаются staff-only.
- Запрос без `surface` (канонический staff unified-list) доступен только staff.
- non-staff с template-view правами работает через `surface=template`.
- include definition данных не должен раскрывать лишнее non-staff пользователям.

## Compatibility Strategy
- Старые клиенты продолжают работать без новых параметров.
- Новые поля в ответе добавляются расширяюще (без удаления существующих).
- UI переводится на новый контракт после backend readiness.

## Trade-offs
- Side-loading `definitions[]` устраняет дублирование payload при повторном использовании одной definition в нескольких exposures.
- Такой shape напрямую совместим с уже существующей frontend-нормализацией (`definitionsById`) и снижает объём переписывания UI data-layer.
- Цена решения: клиент должен выполнить явный join по `definition_id`, но это уже текущий рабочий паттерн в коде.
