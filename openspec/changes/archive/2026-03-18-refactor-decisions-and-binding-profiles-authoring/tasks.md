## 1. Shared authoring references

- [x] 1.1 Выделить общий слой загрузки и нормализации workflow/decision references для authoring surfaces.
- [x] 1.2 Вынести shared helpers для labels, inactive markers и selection semantics reusable revisions.
- [x] 1.3 Подготовить typed selector components для workflow revision и decision revision без ручного копирования opaque ids.

## 2. Binding profiles authoring UX

- [x] 2.1 Перевести workflow pin в `/pools/binding-profiles` на structured picker вместо ручного ввода `workflow_definition_key` и `workflow_revision_id`.
- [x] 2.2 Заменить primary path `Decision refs JSON` на slot-oriented editor с выбором revisions из `/decisions`.
- [x] 2.3 Спрятать raw/manual payload editing за explicit advanced mode без потери compatibility path.

## 3. Decisions page decomposition

- [x] 3.1 Разделить `/decisions` на focused hooks/panels для catalog/detail, metadata context, editor state и legacy import.
- [x] 3.2 Сохранить текущие fail-closed инварианты: metadata fallback, handoff в `/databases`, rollover gating и binding-aware read-only path.
- [x] 3.3 Выровнять catalog/detail/editor shell с `binding-profiles`, не смешивая разные task contexts в одном визуальном блоке.

## 4. Shared navigation and handoff

- [x] 4.1 Добавить явные handoff paths между `/decisions`, `/workflows` и `/pools/binding-profiles`, чтобы reference authoring не требовал copy-paste между страницами.
- [x] 4.2 Сохранить read-only visibility inactive/pinned revisions в selectors и detail surfaces.

## 5. Проверка

- [x] 5.1 Добавить frontend tests на structured selectors и запрет manual id entry как default path.
- [x] 5.2 Добавить/обновить tests на сохранение `Decisions` metadata-aware semantics после распила страницы.
- [x] 5.3 Выполнить релевантные `vitest`, `tsc --noEmit` и `openspec validate refactor-decisions-and-binding-profiles-authoring --strict --no-interactive`.
