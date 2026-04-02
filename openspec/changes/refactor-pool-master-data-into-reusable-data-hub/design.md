## Context
Текущий `Pool Master Data` уже решает важную часть reusable reference problem, но делает это только для publication path. В factual monitoring есть второй, параллельный контур reusable data: worker ограничивает чтение бухгалтерского регистра по account scope, но account scope пока задаётся hardcoded кодами, а не через canonical hub.

Это уже создаёт два разных источника моделирования reusable data:
- publication path: canonical master-data hub + bindings;
- factual path: ad hoc account codes + отдельный resolve в OData.

На живой ИБ дополнительно видно, что бухгалтерские счета нужны не только factual path, но и самим published документам: в `Document_РеализацияТоваровУслуг` есть account refs как в header, так и в табличной части.

## Goals / Non-Goals

### Goals
- Сделать `Pool Master Data` canonical reusable-data hub для publication и bounded factual scopes.
- Добавить first-class поддержку `GLAccount` и `GLAccountSet`.
- Сохранить backward compatibility для `/pools/master-data` и `master_data.*` token grammar.
- Ввести configuration-scoped compatibility markers для reusable account entities.
- Перестать hardcode'ить factual account scope в runtime.
- Обеспечить deterministic pinning versioned `GLAccountSet` в factual/runtime artifacts.
- Обеспечить additive расширение на будущие reusable entity types.

### Non-Goals
- Не вводить новый top-level service, новый frontend app или отдельный runtime boundary.
- Не делать big-bang переименование всех существующих API/route/token prefix в одну поставку.
- Не пытаться в этом change покрыть все возможные reference entity types.
- Не включать automatic outbound mutation или bidirectional sync для chart-of-accounts objects без отдельного change.
- Не делать schema-less/EAV-first модель, где типы теряют жёсткие инварианты и проверяемость.

## Decisions

### Decision: Эволюционно расширять текущий hub, а не строить второй каталог
`Pool Master Data` остаётся canonical operator surface и route `/pools/master-data`, но его доменная роль расширяется с publication-only слоя до reusable-data hub. Это сохраняет существующий UX и avoids split-brain между двумя каталогами reusable данных.

### Decision: Сохранить compatibility-оболочку для текущего token grammar
Префикс `master_data.*` остаётся canonical token surface для существующих и новых reusable entity types. Это intentionally несовершенное имя, но оно уже встроено в document-policy/runtime contracts; менять его сейчас означало бы unnecessary breaking wave.

### Decision: Использовать registry-driven type model с type-specific handlers
Core слой reusable-data должен описывать общие механики:
- canonical entity lifecycle;
- per-infobase binding;
- readiness/preflight coverage;
- token resolution;
- optional sync/bootstrap routing.

Но инварианты, binding scope, IB entity mapping и validation должны оставаться type-specific. Поэтому change вводит registry/handler pattern, а не одну giant generic сущность с неограниченным JSON.

### Decision: Первая additive entity family - `GLAccount` и `GLAccountSet`
`GLAccount` вводится как canonical reusable entity для link на published `ChartOfAccounts_*` objects.

`GLAccountSet` вводится как versioned canonical grouped profile для bounded runtime scopes, где нужны не отдельные account refs, а семантически именованный набор счетов, используемый:
- factual monitoring;
- report-aligned scopes;
- позже, при необходимости, publication templates/decision presets.

`GLAccountSet` не обязан иметь собственный IB object/binding; он является CC-side aggregate поверх member `GLAccount` и управляется как immutable revisioned profile.

### Decision: Reusable account entities должны быть configuration-scoped
`GLAccount` и `GLAccountSet` не должны считаться globally valid только по `canonical_id` и `chart_identity`.

Для них нужен compatibility contract, согласованный с:
- target business configuration identity;
- metadata snapshot provenance/compatibility markers;
- chart-of-accounts identity внутри target configuration.

Это выравнивает reusable account layer с уже существующим metadata-aware contract `/decisions` и не допускает false-positive readiness только из-за совпавшего account code.

### Decision: Binding contract остаётся generic, но scope становится type-specific
Текущая binding семантика сохраняется:
- `Party`: role-specific scope;
- `Contract`: owner-scoped scope;
- `Item/TaxProfile`: simple per-database scope.

Для `GLAccount` вводится deterministic per-infobase binding scope с chart identity. В первой итерации нормой является `ChartOfAccounts_Хозрасчетный`, но модель не должна быть привязана к одному hardcoded chart forever.

### Decision: Capability matrix должна быть explicit, а не "автоматически как у master-data"
Registry для reusable entity types обязан явно определять capability matrix.

Для первой итерации:
- `GLAccount`: manual upsert `yes`, direct binding `yes`, token exposure `yes`, bootstrap import `yes`;
- `GLAccount`: automatic outbound sync `no`, bidirectional sync `no`;
- `GLAccountSet`: CC-owned profile `yes`, direct IB binding `no`, bootstrap import `no`, outbound sync `no`.

Это нужно, чтобы current `pool-master-data-sync` contract не был неявно распространён на plan-of-accounts mutation.

### Decision: Publication и factual используют один reusable-data source, но разные consumption patterns
- publication path резолвит concrete account refs для header/tabular account fields через `GLAccount` bindings;
- factual path резолвит bounded account scope через selected `GLAccountSet`, затем проверяет coverage member bindings по каждой target IB до старта worker execution.

Это даёт единый governance слой без ложного требования, чтобы factual и publication читали одну и ту же runtime структуру.

### Decision: `GLAccountSet` revision должна pin'иться в runtime artifacts
Как только factual monitoring начинает зависеть от grouped account profile, profile membership нельзя трактовать как mutable global state для уже рассчитанных периодов.

Поэтому:
- `GLAccountSet` должен публиковаться revisioned;
- factual preflight, checkpoints и downstream runtime artifacts должны сохранять pinned `gl_account_set_revision_id` и effective member snapshot;
- изменение latest revision не должно silently менять historical replay или readiness уже созданного execution context.

### Decision: Account token validation должна оставаться metadata-aware
Поддержка `master_data.gl_account.<canonical_id>.ref` допустима только для тех field paths, которые resolved metadata snapshot распознаёт как ссылку на chart-of-accounts object.

Система не должна принимать account token просто потому, что имя поля "похоже на счёт".

### Decision: Missing account coverage должен ловиться на readiness/preflight, а не глубоко в worker path
Текущий factual error `chart of accounts is missing factual account codes` слишком поздний и operator-hostile. После change система должна fail-closed раньше:
- в reusable-data coverage;
- в factual preflight;
- в publication compile/gate, если policy использует account token без binding.

## Risks / Trade-offs
- Расширение hub добавит доменную сложность в уже существующий publication-centric код.
  - Mitigation: additive delivery через registry/type handlers и отдельные tests per entity family.
- Сохранение префикса `master_data.*` оставляет legacy naming debt.
  - Mitigation: зафиксировать это как compatibility shell и не делать hidden second prefix.
- `GLAccountSet` может оказаться слишком узким названием, если позже появятся другие grouped profiles.
  - Mitigation: внутреннюю архитектуру строить через generic profile pattern, но shipped operator semantics первой итерации оставить domain-specific и понятными.
- Configuration-scoped compatibility усложнит UX настройки reusable accounts.
  - Mitigation: показывать compatibility markers/operator coverage явно и fail-closed до runtime enqueue.

## Migration Plan
1. Добавить reusable-data type registry и новые entity types `GLAccount`, `GLAccountSet` с explicit capability matrix.
2. Добавить configuration-scoped compatibility markers и validation against target metadata/business identity.
3. Расширить workspace/API/bindings без удаления текущих entity surfaces.
4. Ввести versioned default-compatible `GLAccountSet` для текущего sales/factual scope и backfill миграцию с existing defaults.
5. Перевести factual preflight/runtime на pinned `GLAccountSet` revision resolution.
6. Добавить support для `master_data.gl_account.<canonical_id>.ref` в document-policy/publication compile с metadata-aware field validation.
7. Перевести publication account fields на resolved reusable-data refs там, где policy использует account tokens.
8. Сохранить текущие static GUID-based policies как compatibility path до явной operator remediation.

## Open Questions
- Нужен ли operator-facing generic label `Reusable Data`, или shipped UI должен сохранить продуктовый бренд `Pool Master Data` и расширяться по вкладкам без rename на первом этапе.
