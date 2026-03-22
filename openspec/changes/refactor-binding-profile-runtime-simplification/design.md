## Context

Текущая capability `Binding Profiles` решает правильную доменную задачу: reusable profile revision отделена от pool-local attachment, а runtime boundary остаётся explicit и fail-closed.

Но в реализации вокруг этой модели появились три источника лишней сложности:

1. Attachment остаётся семантически “тонким”, но физически хранит дубли reusable runtime payload (`workflow`, `decisions`, `parameters`, `role_mapping`) рядом с profile refs.
2. Default read path для attachment-ов может materialize'ить generated one-off profile/revision как side effect, если встречает legacy canonical row без refs.
3. `/pools/binding-profiles` получает usage через broad tenant pool list hydration и client-side filtering, хотя оператору нужен scoped profile-centric view.

Эти решения создают второй фактический source-of-truth вокруг attachment-а, усложняют reasoning про lineage и нарушают принцип side-effect-free read path.

## Goals / Non-Goals

- Goals:
  - сохранить саму модель `binding_profile` / `binding_profile_revision` / pool attachment;
  - вернуть attachment к роли thin activation layer;
  - сделать default read/runtime path side-effect-free;
  - выделить dedicated scoped usage projection для `/pools/binding-profiles`;
  - зафиксировать rollout без migration/backfill слоя для historical bindings.

- Non-Goals:
  - не откатывать capability `Binding Profiles`;
  - не менять explicit runtime identity `pool_workflow_binding_id`;
  - не менять idempotency contract `attachment revision + binding_profile_revision_id`;
  - не вводить attachment-local overrides для reusable logic;
  - не делать automatic dedupe historical bindings между пулами;
  - не сохранять затронутые legacy `pool`, attachment и `binding_profile*` данные ценой отдельного migration/backfill flow.

## Decisions

### 1. Attachment остаётся authoritative только для pool-local activation state

Canonical mutable state attachment-а ограничивается:
- `binding_id`;
- `pool_id`;
- `status`;
- selector scope;
- `effective_from/effective_to`;
- reference на pinned `binding_profile_revision_id`;
- audit/concurrency fields.

Reusable execution logic остаётся authoritative только в pinned `binding_profile_revision`.

Assumption:
- change МОЖЕТ сохранить transitional denormalized columns в storage на ограниченный период, если shipped path больше не трактует их как authoritative source и не требует их как mutate surface.

### 2. `resolved_profile` остаётся только derived projection

Operator-facing/read-model payload MAY включать `resolved_profile` или эквивалентный convenience summary, чтобы UI/runtime consumers не делали ручной stitching.

Но такой projection:
- строится из pinned `binding_profile_revision_id`;
- остаётся read-only;
- не превращается во второй mutable source-of-truth;
- не требует повторной отправки reusable logic при pool-local mutate.

Иначе модель “profile + attachment” снова вырождается в “profile + почти такой же attachment payload”.

### 3. Default read/runtime path становится side-effect-free без remediation/backfill слоя

List/detail/preview/runtime resolution не должны создавать generated profile/revision rows как implicit remediation.

Если canonical attachment row не может быть корректно прочитан из-за отсутствующих/битых profile refs, shipped path должен:
- fail-closed;
- вернуть blocking diagnostic.

Этот refactor не включает shipped remediation/backfill tooling для таких rows. Rollout предполагает destructive reset затронутых historical `pool`, attachment и `binding_profile*` данных до включения нового контракта.

### 4. Usage для `/pools/binding-profiles` выносится в dedicated scoped projection

Profile detail workspace должен получать usage через profile-scoped backend read model, а не через broad pool catalog hydration.

Projection должна возвращать:
- attachment count;
- revision-in-use summary;
- список attachment-ов, pinned на выбранный profile;
- handoff context в `/pools/catalog`.

Это уменьшает coupling между profile catalog и pool catalog и убирает ненужный client-side full scan.

## Alternatives Considered

### 1. Оставить текущую денормализацию и просто задокументировать её

Rejected:
- сохраняет второй фактический source-of-truth;
- не убирает сложность reasoning про attachment vs profile;
- продолжает подталкивать shipped path к implicit data healing.

### 2. Сохранить отдельный remediation/backfill flow для legacy residue

Rejected:
- добавляет ещё один переходный слой ради данных, которые допускается удалить до rollout;
- prolongs legacy contract, который change как раз должен упростить;
- создаёт лишний implementation scope без постоянной ценности.

### 3. Оставить usage aggregation на клиенте

Rejected:
- `/pools/binding-profiles` зависит от unrelated pool catalog payload;
- стоимость detail path растёт вместе с размером tenant pool catalog;
- UI слой берёт на себя лишний aggregation logic, который лучше держать в backend projection.

## Risks / Trade-offs

- Derived projection может добавить read-time join/projection cost.
  - Mitigation: сначала использовать straightforward query/projection path; отдельный cache/projection pipeline вводить только при подтверждённой нагрузке.

- Fail-closed для rows без profile refs делает legacy residue недоступным.
  - Mitigation: hard reset затронутых данных до rollout и понятные blocking diagnostics, если residue всё же останется.

- Scoped usage contract добавит ещё один backend read surface.
  - Mitigation: это компенсируется упрощением frontend path и устранением broad cross-surface hydration.

## Rollout Plan

1. Зафиксировать в specs, что attachment read-model derived, а default reads side-effect-free.
2. Убрать из shipped read/runtime path implicit generated profile materialization и любой remediation/backfill compatibility layer.
3. До включения нового контракта удалить затронутые `pool`, `pool_workflow_binding` и `binding_profile*` данные вместо in-place migration.
4. Добавить dedicated usage read contract для `/pools/binding-profiles`.
5. Перевести frontend profile detail на scoped usage projection и убрать full pool catalog scan из default path.
