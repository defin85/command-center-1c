## Context
Доменные сущности уже унифицированы (`operation_definition` + `operation_exposure`), но management API остаётся разделённым:
- templates CRUD/list через `/api/v2/templates/*`,
- action exposure management через `/api/v2/operation-catalog/*`,
- editor hints под action-specific path.

Это усложняет сопровождение, тестирование и дальнейшую эволюцию RBAC.

## Goals / Non-Goals
- Goals:
  - Один backend management-контур для exposure (`operation-catalog`) для обеих surfaces.
  - Surface-aware RBAC без потери текущей модели прав для template surface.
  - Удаление legacy template CRUD/list и action-specific hints path.
- Non-Goals:
  - Изменение runtime endpoint `/api/v2/ui/action-catalog/`.
  - Изменение бизнес-семантики extensions actions, plan/apply и effective catalog.

## Decisions
- Decision 1: `operation-catalog` становится primary management API
  - `surface=template` проверяется через template permissions (`view/manage`, включая object-level semantics).
  - `surface=action_catalog` остаётся staff-only.
- Decision 2: Generic hints endpoint
  - Capability hints доступны по neutral path `/api/v2/ui/operation-exposures/editor-hints/`.
  - Action-specific hints path удаляется, чтобы убрать связку API-слоя с legacy naming.
- Decision 3: Legacy template CRUD/list удаляются
  - `/api/v2/templates/list-templates|create-template|update-template|delete-template` де-комиссируются как дублирующий management слой.
  - Источник управления template exposures только один: operation-catalog API.

## Migration Plan
1. Добавить/обновить operation-catalog RBAC для `surface=template`.
2. Перевести frontend `/templates` на unified API.
3. Ввести generic hints endpoint и переключить frontend.
4. Удалить legacy template CRUD/list + old hints path.
5. Обновить OpenAPI, codegen, тесты.

## Risks / Trade-offs
- Риск: регрессии object-level template permissions при переносе в operation-catalog.
  - Митигация: отдельные backend тесты на view/manage и object-level ограничения.
- Риск: breaking изменения для внешних/скриптовых клиентов, использующих `/api/v2/templates/*`.
  - Митигация: явные breaking notes в релизе и обновление SDK/typed clients в том же change.
- Риск: неконсистентные query keys/кэш на фронте после миграции endpoint’ов.
  - Митигация: единый нейминг query keys по `operation-catalog` + явная invalidation стратегия.
