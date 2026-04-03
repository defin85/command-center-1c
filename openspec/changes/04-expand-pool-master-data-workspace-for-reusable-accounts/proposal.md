# Change: 04. Расширить pool master-data workspace под reusable accounts отдельным UI change

## Why
UI-часть umbrella change смешивает доменную account-модель с незавершённой platform migration для `/pools/master-data`. Сейчас route всё ещё живёт на legacy page composition, а отдельный active change уже делает canonical shell для этой страницы.

Чтобы не зафиксировать второй competing page foundation, UI expansion нужно вынести в отдельный change и жёстко привязать к platform prerequisite.

Этот change фиксирует отдельную UI-фазу расширения reusable-data hub для account surfaces.

## What Changes
- Расширить `/pools/master-data` внутри canonical shell новыми рабочими зонами `GLAccount` и `GLAccountSet`.
- Добавить UI для account bindings, `chart_identity`, compatibility markers и `GLAccountSet` revision lifecycle.
- Расширить token picker поддержкой `master_data.gl_account.*.ref`.
- Расширить bootstrap import UI поддержкой `GLAccount`.
- Подключить token picker, sync affordances и entity catalogs к generated reusable-data registry contract.
- Дочистить оставшийся shared UI helper tail после `01-add-reusable-data-registry-and-capability-gates`:
  - использовать registry `label` как operator-facing caption вместо raw `entity_type`;
  - убрать string-specific defaults вроде special-case исключения `'binding'`, если требуемое поведение уже выражается через registry contract и page intent.
- Показать capability-gated sync/readiness states для reusable accounts без generic mutating controls.
- Не вводить новый route-level shell, новый parallel layout contract или альтернативную page foundation.

## Impact
- Affected specs:
  - `pool-master-data-hub-ui`
- Affected code:
  - `frontend/src/pages/Pools/**`
  - `frontend/src/components/platform/**`
  - `frontend/tests/browser/**`
  - `contracts/**`
- Related changes:
  - depends on `refactor-ui-platform-workflow-template-workspaces`
  - depends on `01-add-reusable-data-registry-and-capability-gates`
  - depends on `02-extend-master-data-hub-with-reusable-accounts`

## Non-Goals
- Поставка самого canonical shell для `/pools/master-data`.
- Изменение backend runtime semantics publication или factual execution.
- Введение второго primary design system или page foundation.
