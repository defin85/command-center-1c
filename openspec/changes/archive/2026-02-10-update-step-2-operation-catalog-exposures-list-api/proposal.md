# Change: Шаг 2 — расширить API списка exposures для unified UI и масштабирования

## Why
После шага 1 UI становится единым реестром, но без обновления API остаются ограничения:
- client-side merge/filter для mixed-surface списка;
- лишние round-trip на definitions;
- неполный server-side search/sort/filter для единого реестра.

Это ухудшает производительность и предсказуемость при росте числа exposures.

## What Changes
- Расширить `GET /api/v2/operation-catalog/exposures/` для server-driven unified list:
  - поддержать unified staff-list без `surface` (канонически это эквивалент `all`);
  - сохранить `surface=all` как явный алиас для backward compatibility и читаемого deep-link;
  - добавить server-side `search`/`filters`/`sort` по полям unified списка;
  - сохранить `limit/offset` как основной механизм пагинации.
- Добавить явный include-механизм `include=definitions` с side-loading:
  - в ответе возвращать `definitions[]` (уникальные по `id`) рядом с `exposures[]`;
  - не встраивать definition inline в каждый exposure;
  - позволить UI насытить `definitionsById` из одного list-запроса без второго round-trip.
- Сохранить surface-aware RBAC и backward compatibility текущего контракта.

## Impact
- Affected specs:
  - `operation-definitions-catalog`
  - `operation-templates`
- Affected code:
  - Backend: `orchestrator/apps/api_v2/views/operation_catalog.py`, сериализаторы, query/filter layer
  - Frontend: data-layer `/templates` (перевод на server-driven list contract)
  - Tests: backend API tests + browser/integration tests для unified list

## Non-Goals
- Новый UI-редизайн `/templates` (уже в шаге 1).
- Изменение runtime execution/read paths (`/api/v2/ui/action-catalog/`, `/extensions/*`).
- Изменение canonical executor mapping (вне рамок этого change).
