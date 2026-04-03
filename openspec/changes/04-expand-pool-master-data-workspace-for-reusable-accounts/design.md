## Context
`/pools/master-data` уже является частью отдельной platform migration волны. Поэтому этот change не должен заново решать route foundation, responsive shell или page-level layout contract. Его задача уже уже внутри canonical shell: расширить доменные зоны и authoring surfaces под reusable accounts.

Без такого разделения UI rollout рискует:
- закрепить временный legacy shell как новую норму;
- разойтись с generated registry contract;
- дублировать sync affordances и token catalogs.
- закрепить мелкие legacy conventions в shared helper layer вместо того, чтобы дочистить их вместе с account expansion.

## Goals / Non-Goals

### Goals
- Добавить operator-facing зоны `GLAccount` и `GLAccountSet`.
- Показать revision lifecycle, bindings и compatibility markers явно.
- Подключить UI к generated registry contract и capability matrix.
- Дочистить оставшиеся shared registry UI helpers, чтобы account expansion не тащил legacy labels/defaults как новый baseline.
- Сохранить один canonical route foundation для `/pools/master-data`.

### Non-Goals
- Не поставлять route shell вне зависимости от platform prerequisite.
- Не делать raw `Card + Tabs` долгосрочным foundation.

## Decisions

### Decision: UI change расширяет только canonical shell
Все новые workspace zones, forms и remediation states должны встраиваться в shell из `refactor-ui-platform-workflow-template-workspaces`. Второй parallel page foundation запрещён.

### Decision: Account authoring должен показывать binding scope и compatibility явно
Оператор должен видеть `chart_identity`, compatibility markers, binding coverage и immutable revision semantics `GLAccountSet`, а не редактировать их как opaque JSON.

### Decision: Token picker и sync affordances читают generated registry contract
Frontend не должен держать отдельный handwritten catalog entity types и capabilities. UI decisions о token exposure и sync actions должны читаться из того же generated contract, что и backend.

### Decision: Shared registry UI helpers закрывают residual compatibility tail из foundation change
Этот change также забирает оставшийся неблокирующий UI-tail после `01-add-reusable-data-registry-and-capability-gates`, если он всё ещё живёт в shared helper layer:
- option labels читаются из registry `label`, а не из raw `entity_type`;
- bootstrap default selection не опирается на string-specific exclusion вроде `'binding'`, если page-level intent уже может быть выражен через registry contract;
- account expansion не должна закреплять эти legacy conventions как baseline для следующих reusable entity families.

### Decision: Sync UX остаётся capability-gated
`GLAccount` не получает generic mutating outbound/bidirectional actions. `GLAccountSet` показывается как profile state, draft/publish lifecycle и runtime/readiness context, но не как mutating sync entity.

## Verification Gates
- `/pools/master-data` живёт внутри canonical shell, а не во втором route foundation.
- Mobile fallback продолжает работать через platform layer.
- Token picker, bindings UI и bootstrap import читают generated registry contract.
- Browser regression не показывает raw horizontal overflow как primary mode.

## Risks / Trade-offs
- UI change зависит от landing отдельного platform prerequisite.
  - Это намеренно: форкнуть foundation было бы дороже, чем дождаться canonical shell.
- Operator-facing account surfaces добавят новые состояния.
  - Они должны быть явными, потому что скрытая capability логика увеличивает ошибки настройки.
- В scope попадает небольшой cleanup shared helpers, который сам по себе не даёт новую feature.
  - Это допустимо, потому что account UI всё равно проходит через те же token/bootstrap helpers, и оставлять там legacy conventions дороже.
