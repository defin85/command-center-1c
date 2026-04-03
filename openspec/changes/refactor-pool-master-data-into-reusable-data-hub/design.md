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
- Сделать capability matrix исполняемым runtime contract, а не только описанием в proposal/spec.
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

### Decision: Canonical identity `GLAccount` отделяется от IB-local object refs
`GLAccount` в CC в этом change трактуется как tenant-scoped semantic account, а не как materialized row конкретной ИБ.

`Ref_Key` (или иной OData object reference) НЕ ДОЛЖЕН использоваться как cross-infobase identity, потому что на живых published OData surfaces один и тот же `ChartOfAccounts_Хозрасчетный` может иметь совпадающие `Code`, `Description` и `PredefinedDataName`, но разные `Ref_Key` в разных ИБ.

Поэтому:
- canonical entity определяется `canonical_id` и доменной семантикой счёта;
- concrete target object определяется только через per-infobase binding;
- publication/factual runtime получают `Ref_Key` исключительно из binding artifact для target ИБ, а не переносят его между ИБ.

Для predefined accounts `PredefinedDataName` МОЖЕТ использоваться как дополнительный deterministic marker в compatibility/admission внутри одного `chart_identity`, но НЕ ДОЛЖЕН заменять canonical identity или operator-facing key.

### Decision: Reusable account entities должны быть configuration-scoped
`GLAccount` и `GLAccountSet` в этом change сохраняют tenant-scoped canonical identity, но их runtime admission не должен считаться globally valid только по `canonical_id`, string account code, `PredefinedDataName` или локальному `Ref_Key`.

Для них нужен compatibility contract, согласованный с:
- target business configuration identity;
- metadata snapshot provenance/compatibility markers;
- chart-of-accounts identity внутри target configuration.

Это выравнивает reusable account layer с уже существующим metadata-aware contract `/decisions` и не допускает false-positive readiness только из-за совпавшего account code.

Operator-facing compatibility class для `GLAccount` и `GLAccountSet` в этом change фиксируется как:
- `config_name`;
- `config_version`;
- `chart_identity`.

Persisted provenance/pinning contract для runtime admission должен использовать уже существующий metadata/business-identity substrate и хранить как минимум:
- `metadata_catalog_snapshot_id`;
- `catalog_version`;
- `metadata_hash`;
- `provenance_database_id`;
- `confirmed_at`.

Совпадение `config_name + config_version + chart_identity` является необходимым, но недостаточным условием runtime admission. Publication/factual path дополнительно должны требовать pinned metadata provenance и positive published-surface evidence для target infobase, потому что published OData surface и доступные entities/functions выбираются per-infobase и не выводятся только из business version.

`metadata_hash`, `catalog_version` и snapshot provenance должны использоваться как first-class evidence и pinning surface, но НЕ как единственный operator-facing compatibility key. Иначе любой drift в snapshot lineage превратит compatibility в непрозрачную opaque coupling-модель и оторвёт reusable accounts от уже shipped shared metadata catalog behavior.

### Decision: Binding contract остаётся generic, но scope становится type-specific
Текущая binding семантика сохраняется:
- `Party`: role-specific scope;
- `Contract`: owner-scoped scope;
- `Item/TaxProfile`: simple per-database scope.

Для `GLAccount` вводится deterministic per-infobase binding scope с chart identity. В первой итерации нормой является `ChartOfAccounts_Хозрасчетный`, но модель не должна быть привязана к одному hardcoded chart forever.

`chart_identity` ДОЛЖЕН храниться как first-class persisted scope field и участвовать в uniqueness/lookup contract на том же уровне, что `database_id` и `canonical_id`. Прятать его только в `metadata` нельзя, потому что это ломает deterministic scope resolution и DB-level защиту от duplicate bindings.

`ib_ref_key` / `Ref_Key` для `GLAccount` должен оставаться strictly local binding field. Для predefined accounts можно дополнительно сохранять `PredefinedDataName` как compatibility/evidence marker, но он не заменяет binding scope и не устраняет необходимость target-specific binding.

### Decision: `GLAccountSet` revision/member contract должен быть first-class, а не metadata-only
`GLAccountSet` как grouped profile не должен существовать только как mutable blob в `metadata`.

Для change требуется first-class persisted contract:
- профиль;
- immutable revisions;
- member rows revision-а;
- compatibility markers revision-а;
- runtime-friendly projection effective members.

Это нужно, чтобы factual pinning, diff latest vs pinned и historical replay опирались на стабильный contract, а не на ad hoc JSON conventions.

### Decision: Capability matrix должна быть explicit, а не "автоматически как у master-data"
Registry для reusable entity types обязан явно определять capability matrix.

Для первой итерации:
- `GLAccount`: manual upsert `yes`, direct binding `yes`, token exposure `yes`, bootstrap import `yes`;
- `GLAccount`: automatic outbound sync `no`, bidirectional sync `no`;
- `GLAccountSet`: CC-owned profile `yes`, direct IB binding `no`, bootstrap import `no`, outbound sync `no`.

Это нужно, чтобы current `pool-master-data-sync` contract не был неявно распространён на plan-of-accounts mutation.

Тот же capability contract должен определять operator-facing semantics:
- `GLAccount` не получает generic mutating sync action и в UI может отображаться только как `bootstrap-only` / `unsupported-by-design` для outbound/bidirectional directions;
- `GLAccountSet` не появляется как mutating sync entity и может быть либо скрыт из sync mutation list, либо показан как read-only profile state без action controls.

Capability matrix должна быть не только описана, но и исполняться через registry hooks в:
- canonical upsert;
- binding upsert;
- outbox fan-out;
- sync workflow enqueue;
- bootstrap import admission.

Наличие entity type в enum или API namespace не должно автоматически давать ему outbound/inbound/runtime privileges.

### Decision: Publication и factual используют один reusable-data source, но разные consumption patterns
- publication path резолвит concrete account refs для header/tabular account fields через `GLAccount` bindings;
- factual path резолвит bounded account scope через selected `GLAccountSet`, затем проверяет coverage member bindings по каждой target IB до старта worker execution.

Это даёт единый governance слой без ложного требования, чтобы factual и publication читали одну и ту же runtime структуру.

### Decision: `GLAccountSet` revision должна pin'иться в runtime artifacts
Как только factual monitoring начинает зависеть от grouped account profile, profile membership нельзя трактовать как mutable global state для уже рассчитанных периодов.

Поэтому:
- `GLAccountSet` должен публиковаться revisioned;
- factual preflight, checkpoints и downstream runtime artifacts должны сохранять first-class machine-readable scope contract c `gl_account_set_revision_id`, `effective_members` и stable `scope_fingerprint`;
- изменение latest revision не должно silently менять historical replay или readiness уже созданного execution context.

### Decision: Переход factual scope на `GLAccountSet` должен идти через versioned bridge
Текущий factual runtime и worker contract опираются на `account_codes`, поэтому прямой one-shot switch на `gl_account_set_revision_id + effective_members` создаст rollout/rollback risk.

В этом change требуется versioned bridge:
- верхнеуровневые runtime envelopes `pool_factual_sync_workflow.v1` и `pool_factual_read_lane.v1` остаются стабильными на bridge-периоде; coordinated top-level version bump не входит в scope этого change;
- versioned часть вводится как nested `factual_scope_contract.v2`, который хранит `gl_account_set_revision_id`, `effective_members`, `scope_fingerprint`, compatibility provenance и собственный `scope_contract_version`;
- transitional dual-write path продолжает записывать legacy `account_codes`, детерминированно derived из pinned `effective_members`;
- worker/read runtime в bridge-периоде должен работать в dual-read режиме: внутри текущих `v1` envelopes предпочитать nested `factual_scope_contract.v2`, но уметь безопасно продолжать чтение legacy `account_codes`;
- historical checkpoints/replay/inspect surfaces должны сохранять pinned effective member snapshot и версию nested scope contract, а не повторно materialize'ить latest revision;
- rollback на старый worker/runtime не должен требовать пересборки factual artifacts.

Bridge считается завершённым только после того, как live verification подтвердит:
- worker publication/factual path использует nested `factual_scope_contract.v2` внутри текущих `v1` envelopes;
- persisted checkpoints и inspect surfaces сохраняют эквивалентность legacy `account_codes`;
- replay historical quarter на bridge- и post-bridge runtime даёт тот же bounded account scope.

### Decision: Typed metadata validation должна опираться на OData metadata contract, а не на name heuristics
Поддержка `master_data.gl_account.<canonical_id>.ref` требует не просто проверки существования поля в metadata snapshot.

Compile/validation path должен:
- проверять, что field path существует;
- проверять, что тип field path соответствует published chart-of-accounts reference semantics;
- проверять compatibility между token entity markers и target business configuration / metadata provenance.

Проверка по имени поля, legacy allowlist или textual account code недопустима: это слишком хрупко и противоречит fail-closed цели change.

### Decision: Account token validation должна оставаться metadata-aware
Поддержка `master_data.gl_account.<canonical_id>.ref` допустима только для тех field paths, которые resolved metadata snapshot распознаёт как ссылку на chart-of-accounts object.

Система не должна принимать account token просто потому, что имя поля "похоже на счёт".

### Decision: Missing account coverage должен ловиться на readiness/preflight, а не глубоко в worker path
Текущий factual error `chart of accounts is missing factual account codes` слишком поздний и operator-hostile. После change система должна fail-closed раньше:
- в reusable-data coverage;
- в factual preflight;
- в publication compile/gate, если policy использует account token без binding.

### Decision: Frontend route foundation не должен fork'аться от active UI platform migration
`/pools/master-data` уже пересекается с active change `refactor-ui-platform-workflow-template-workspaces`, который делает route-level shell canonical multi-zone workspace.

Поэтому текущий change:
- НЕ должен вводить второй parallel page shell, второй route-level layout contract или второй набор responsive fallback правил;
- ДОЛЖЕН рассматривать route foundation как dependency и расширять только domain zones/forms/contracts внутри canonical shell;
- МОЖЕТ временно использовать compatibility wrappers в page code до слияния с UI platform change, но не должен фиксировать их как новую long-term архитектуру;
- НЕ ДОЛЖЕН закрывать UI-delivery как complete, пока dependency `refactor-ui-platform-workflow-template-workspaces` не дала canonical shell или не была явно импортирована в scope этого change как отдельный prerequisite.

Это снижает риск merge-conflict между domain expansion и route-shell refactor и оставляет один source-of-truth для `/pools/master-data` page foundation.

### Decision: Registry phase должна заменить hardcoded seams до расширения surface area
Сейчас ключевые seams по reusable data жёстко привязаны к enum и if/else logic:
- canonical entity enums;
- sync policy resolution;
- bootstrap dependency order;
- master-data token parsing;
- guided token picker.

Чтобы additive onboarding не остался декларацией, change должен сначала ввести executable registry contract и только потом расширять:
- backend enums/API surfaces;
- frontend token picker entity catalogs;
- bootstrap entity scope;
- sync/outbox eligibility.

На bridge-периоде допустимы compatibility wrappers вокруг existing enums и parsers, но source-of-truth должен быть один: registry/type handlers.

## Risks / Trade-offs
- Расширение hub добавит доменную сложность в уже существующий publication-centric код.
  - Mitigation: additive delivery через registry/type handlers и отдельные tests per entity family.
- First-class storage contract для `GLAccount`/`GLAccountSet` увеличит объём миграций по сравнению с metadata-only shortcut.
  - Mitigation: отдельно зафиксировать persisted scope/revision schema до UI и API rollout.
- Сохранение префикса `master_data.*` оставляет legacy naming debt.
  - Mitigation: зафиксировать это как compatibility shell и не делать hidden second prefix.
- `GLAccountSet` может оказаться слишком узким названием, если позже появятся другие grouped profiles.
  - Mitigation: внутреннюю архитектуру строить через generic profile pattern, но shipped operator semantics первой итерации оставить domain-specific и понятными.
- Configuration-scoped compatibility усложнит UX настройки reusable accounts.
  - Mitigation: показывать compatibility markers/operator coverage явно и fail-closed до runtime enqueue.
- UI delivery зависит от активного platform-shell change и может заблокировать domain rollout.
  - Mitigation: считать canonical shell explicit prerequisite и не закрывать UI scope через временный fork route foundation.

## Migration Plan
1. Добавить executable reusable-data registry и capability hooks до расширения entity enums/API surfaces.
2. Зафиксировать разделение между tenant-scoped canonical identity `GLAccount` и per-infobase binding `ib_ref_key` / `Ref_Key`; для predefined accounts разрешить `PredefinedDataName` только как additional compatibility/admission marker.
3. Зафиксировать reusable-account compatibility contract на базе существующего metadata/business-identity substrate: `config_name + config_version + chart_identity` как operator-facing compatibility class, а snapshot provenance + published-surface evidence как runtime admission/evidence layer.
4. Добавить first-class persisted storage contract для `GLAccount`, `GLAccountSet`, immutable revisions/members и `chart_identity` binding scope.
5. Перевести sync/outbox/bootstrap admission на registry-enforced capability matrix с fail-closed behavior для unsupported directions.
6. Ввести versioned default-compatible `GLAccountSet` для текущего sales/factual scope и backfill миграцию с existing defaults.
7. Ввести factual scope bridge: сохранить верхнеуровневые `pool_factual_sync_workflow.v1` / `pool_factual_read_lane.v1`, добавить nested `factual_scope_contract.v2`, dual-write legacy `account_codes`, dual-read worker/runtime и replay-safe checkpoints.
8. Перевести factual preflight/runtime на first-class pinned `GLAccountSet` scope artifact resolution.
9. Добавить support для `master_data.gl_account.<canonical_id>.ref` в document-policy/publication compile с metadata-aware typed field validation.
10. Перевести publication account fields на resolved reusable-data refs там, где policy использует account tokens.
11. После появления canonical shell из `refactor-ui-platform-workflow-template-workspaces` расширить workspace/API/bindings без удаления текущих entity surfaces и без silent metadata fallback для account scope.
12. Сохранить текущие static GUID-based policies и legacy factual `account_codes` как compatibility path до завершения explicit remediation и bridge cutover proof.

## Open Questions
- Нужен ли operator-facing generic label `Reusable Data`, или shipped UI должен сохранить продуктовый бренд `Pool Master Data` и расширяться по вкладкам без rename на первом этапе.
