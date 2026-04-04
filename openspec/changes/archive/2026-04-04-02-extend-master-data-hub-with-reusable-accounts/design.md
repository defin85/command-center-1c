## Context
Расширение reusable-data hub бухгалтерскими счетами требует не просто ещё одного enum значения. Для первой новой entity family нужен отдельный canonical identity contract, compatibility markers, binding scope и runtime-safe publication contract.

Если пропустить этот слой и сразу перейти к factual bridge, система получит неустойчивую модель, где:
- `Ref_Key` начнёт играть роль cross-infobase identity;
- `chart_identity` останется скрытым metadata blob;
- `GLAccountSet` не будет иметь first-class revision contract;
- document policy и publication не смогут безопасно использовать canonical account tokens.

Этот change не создаёт отдельное account-хранилище. Он расширяет общий master-data hub первой reusable account family.

## Goals / Non-Goals

### Goals
- Ввести `GLAccount` и `GLAccountSet` как first-class reusable-data surfaces внутри общего hub.
- Зафиксировать persisted compatibility и binding scope contract для reusable accounts.
- Добавить API, bootstrap import и publication/document-policy support для account refs.
- Сохранить fail-closed запрет на mutating sync directions для accounts.

### Non-Goals
- Не переводить factual runtime на `GLAccountSet` в этом change.
- Не делать route-level UI foundation.
- Не materialize'ить `GLAccountSet` как direct IB object.

## Decisions

### Decision: `GLAccount` canonical identity отделена от target-local object ref
`GLAccount` в CC остаётся tenant-scoped semantic account. `ib_ref_key` / `Ref_Key` используется только как binding конкретной ИБ и не становится cross-infobase key.

### Decision: `chart_identity` является частью persisted binding scope
Для `GLAccount` scope key должен включать `chart_identity`, чтобы idempotent binding lookup не зависел от скрытых conventions и не смешивал разные charts of accounts.

### Decision: Compatibility class и runtime provenance разделяются
Operator-facing compatibility class для reusable accounts фиксируется как:
- `config_name`;
- `config_version`;
- `chart_identity`.

Runtime admission дополнительно использует pinned provenance и published-surface evidence, а не только совпадение compatibility class.

### Decision: `GLAccountSet` поставляется как первая profile/revision surface внутри hub
Этот change вводит profile, current draft, published revision и member contract для `GLAccountSet`, но не включает factual pinning/cutover. Цель здесь: расширить общий hub устойчивой persisted моделью до runtime bridge.

### Decision: Account tokens разрешены только после typed metadata validation
`master_data.gl_account.<canonical_id>.ref` допустим только для field paths, которые metadata snapshot распознаёт как ссылку на chart-of-accounts object. Name heuristics недостаточны.

### Decision: `GLAccount` bootstrap-only в shipped sync semantics
`GLAccount` может использовать bootstrap import и direct binding, но не получает automatic outbound/bidirectional sync. `GLAccountSet` остаётся CC-side profile без target sync entity semantics.

## Rollout
1. Добавить storage/API/contracts для `GLAccount` и `GLAccountSet`.
2. Включить bootstrap import и account token compile path.
3. Расширить publication account ref resolution.
4. Оставить factual bridge для следующего отдельного change.

## Risks / Trade-offs
- First-class `GLAccountSet` storage кажется избыточным без factual cutover.
  - Это осознанный шаг: runtime bridge должен строиться поверх устойчивой persisted модели, а не поверх draft-only metadata.
- Account compatibility contract добавляет operator-visible complexity.
  - Это лучше, чем implicit matching по `Code`, `Description` или `Ref_Key`.
