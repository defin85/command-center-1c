## Context
`/pools/master-data` уже является частью отдельной platform migration волны. Поэтому этот change не должен заново решать route foundation, responsive shell или page-level layout contract. Его задача только post-prerequisite: взять уже migrated workspace и довести его доменные зоны и authoring surfaces до reusable accounts.

Сегодня backend и generated contracts для `GLAccount` / `GLAccountSet` уже shipped, но frontend still incomplete:
- route остаётся raw `Card + Tabs` canvas;
- `Bindings` UI знает только существующие scope variants и не показывает `chart_identity`;
- token catalog adapter не умеет `gl_account`;
- shared registry helpers продолжают использовать raw `entity_type` labels и string-specific defaults.

Без явного post-platform разделения UI rollout рискует:
- закрепить временный legacy shell как новую норму;
- разойтись с generated registry contract;
- дублировать sync affordances и token catalogs.
- закрепить мелкие legacy conventions в shared helper layer вместо того, чтобы дочистить их вместе с account expansion.

## Goals / Non-Goals

### Goals
- Стартовать только после landing canonical shell для `/pools/master-data`.
- Добавить operator-facing зоны `GLAccount` и `GLAccountSet`.
- Показать revision lifecycle, bindings и compatibility markers явно.
- Подключить UI к generated registry contract и capability matrix.
- Дочистить оставшиеся shared registry UI helpers, чтобы account expansion не тащил legacy labels/defaults как новый baseline.
- Сохранить один canonical route foundation для `/pools/master-data`.

### Non-Goals
- Не поставлять route shell вне зависимости от platform prerequisite.
- Не делать raw `Card + Tabs` долгосрочным foundation.
- Не переопределять shipped backend/API semantics reusable accounts.

## Decisions

### Decision: Change стартует только после platform prerequisite
Реализация `04` не начинается, пока `/pools/master-data` не будет migrated на canonical multi-zone shell в `refactor-ui-platform-workflow-template-workspaces`. Если prerequisite не landed, работа должна идти туда, а не в этот change.

### Decision: UI change расширяет только canonical shell
Все новые workspace zones, forms и remediation states должны встраиваться в shell из `refactor-ui-platform-workflow-template-workspaces`. Второй parallel page foundation запрещён.

### Decision: Backend/API/contracts переиспользуются как shipped baseline
`04` по умолчанию не владеет расширением backend schema. Frontend должен строиться поверх уже shipped endpoints, registry inspect contract и generated models. Contract changes допустимы только если обнаружится конкретный UI-blocking gap, а не "на всякий случай".

### Decision: Account authoring должен показывать binding scope и compatibility явно
Оператор должен видеть `chart_identity`, compatibility markers, binding coverage и immutable revision semantics `GLAccountSet`, а не редактировать их как opaque JSON.

### Decision: Bindings UI должен стать registry-shaped, а не entity-specific
Для account rollout недостаточно добавить новый `entity_type` в текущие формы. Presentation и authoring для binding scope должны собираться из registry contract, чтобы `chart_identity` становился first-class полем наряду с уже существующими role/owner scopes.

### Decision: Token picker и sync affordances читают generated registry contract
Frontend не должен держать отдельный handwritten catalog entity types и capabilities. UI decisions о token exposure и sync actions должны читаться из того же generated contract, что и backend.

### Decision: Shared registry UI helpers закрывают residual compatibility tail из foundation change
Этот change также забирает оставшийся неблокирующий UI-tail после `01-add-reusable-data-registry-and-capability-gates`, если он всё ещё живёт в shared helper layer:
- option labels читаются из registry `label`, а не из raw `entity_type`;
- bootstrap default selection не опирается на string-specific exclusion вроде `'binding'`, если page-level intent уже может быть выражен через registry contract;
- account expansion не должна закреплять эти legacy conventions как baseline для следующих reusable entity families.

### Decision: Unsupported registry-published token entities должны fail-closed всплывать как явный compatibility gap
Если registry публикует token-exposed entity type, а frontend compatibility adapter ещё не умеет его materialize'ить в picker catalog, система должна давать явную ошибку/тестовый провал, а не silently скрывать поддержку.

### Decision: Sync UX остаётся capability-gated
`GLAccount` не получает generic mutating outbound/bidirectional actions. `GLAccountSet` показывается как profile state, draft/publish lifecycle и runtime/readiness context, но не как mutating sync entity.

## Verification Gates
- prerequisite shell для `/pools/master-data` landed и даёт route-addressable active tab/remediation context.
- `/pools/master-data` живёт внутри canonical shell, а не во втором route foundation.
- `Bindings` UI показывает `chart_identity` как часть scope и не скрывает compatibility markers в opaque JSON.
- Mobile fallback продолжает работать через platform layer.
- Token picker, bindings UI и bootstrap import читают generated registry contract.
- `gl_account` больше не попадает в `unsupported_entity_types` compatibility gap.
- Operator-facing captions и defaults читаются из registry `label` и capability policy, а не из raw string conventions.
- Browser regression не показывает raw horizontal overflow как primary mode.

## Risks / Trade-offs
- UI change зависит от landing отдельного platform prerequisite.
  - Это намеренно: форкнуть foundation было бы дороже, чем дождаться canonical shell.
- Helper refactor затрагивает не только `/pools/master-data`, но и `/pools/catalog`.
  - Это приемлемо: token picker и registry adapters уже shared by design.
- Operator-facing account surfaces добавят новые состояния.
  - Они должны быть явными, потому что скрытая capability логика увеличивает ошибки настройки.
- В scope попадает небольшой cleanup shared helpers, который сам по себе не даёт новую feature.
  - Это допустимо, потому что account UI всё равно проходит через те же token/bootstrap helpers, и оставлять там legacy conventions дороже.
