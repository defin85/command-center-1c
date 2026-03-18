# Change: refactor-decisions-and-binding-profiles-authoring

## Почему

Сейчас authoring surfaces для `Decisions` и `binding-profiles` развиваются разными паттернами, хотя решают близкую задачу: редактирование versioned reusable resources с pinned references на workflow/decision revisions.

Это уже даёт два практических дефекта:
- `/decisions` держит слишком много ответственности в одной странице: catalog/detail, metadata-aware fallback, editor orchestration, legacy import и binding usage diagnostics живут вместе;
- `/pools/binding-profiles` заставляет пользователя вручную переносить opaque ids и raw JSON между `/workflows`, `/decisions` и profile editor.

В итоге оператору и аналитику приходится копировать `workflow_revision_id`, `decision_table_id`, `decision_revision` и фрагменты payload между страницами, хотя в проекте уже есть готовые reference catalogs и selector-паттерны.

## Что меняется

- Вводится общий frontend слой authoring references для workflow revisions и decision revisions, который можно переиспользовать в `/decisions`, `/workflows` и `/pools/binding-profiles`.
- `/pools/binding-profiles` переходит с ручного ввода workflow pin и `Decision refs JSON` на structured selectors и slot-oriented editor.
- Raw/manual payload editing сохраняется только как explicit advanced mode, а не как default path.
- `/decisions` реорганизуется в набор focused hooks/panels с сохранением текущего fail-closed поведения для metadata context и handoff в `/databases`.
- Catalog/detail/revision/usage patterns для `Decisions` и `binding-profiles` выравниваются по UX, но без навязывания одного универсального mega-editor.

## Impact

- Affected specs:
  - `workflow-decision-modeling`
  - `pool-binding-profiles`
- Related active changes:
  - `add-binding-profiles-and-pool-attachments` остаётся функциональной базой для `/pools/binding-profiles`; этот change уточняет и упрощает authoring UX поверх уже введённой модели.
- Affected code:
  - `frontend/src/pages/Decisions/**`
  - `frontend/src/pages/Pools/PoolBindingProfiles*`
  - shared workflow authoring selectors/helpers under `frontend/src/components/workflow/**`
  - frontend query/reference loading layer
