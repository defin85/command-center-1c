# Change: Refactor Pool Master Data into Reusable Data Hub

## Why
`Pool Master Data` сейчас решает только publication-centric задачу для `Party`, `Item`, `Contract`, `TaxProfile`, тогда как factual monitoring уже требует тот же класс reusable reference data для бухгалтерских счетов. На живой ИБ видно, что счета участвуют и в header, и в табличных частях опубликованных документов, а factual sync при этом использует отдельный hardcoded account scope, что создаёт дублирование модели и fail-closed ошибки совместимости.

## What Changes
- Расширить `Pool Master Data` из publication-only слоя в tenant-scoped reusable-data hub без нового top-level runtime и без замены текущего route `/pools/master-data`.
- Ввести executable reusable-data registry как единственный source-of-truth для capability matrix, sync/bootstrap routing и runtime gating по reusable entity types.
- Публиковать backend-owned reusable-data registry в generated contract/schema для `contracts/**` и frontend, чтобы UI и backend читали одну capability policy без ручного дублирования registry definitions.
- Ввести первую новую reusable entity family для бухгалтерских счетов:
  - `GLAccount` как tenant-scoped canonical semantic account с per-infobase binding;
  - `GLAccountSet` как versioned grouped canonical profile для factual/report scopes с lifecycle `draft -> publish -> immutable revision`.
- Сделать `GLAccount.chart_identity`, compatibility markers и `GLAccountSet` revision/member contract first-class persisted surfaces, а не opaque metadata-only convention.
- Зафиксировать operator/API lifecycle `GLAccountSet`:
  - `list/get/upsert` работают на уровне profile и current draft;
  - `publish` создаёт новую immutable revision;
  - runtime pin-ит published revision, а не mutable latest state.
- Явно отделить canonical identity `GLAccount` от target-IB object refs:
  - `Ref_Key` / `ib_ref_key` остаётся только per-infobase binding surface и не считается cross-infobase identity;
  - для predefined счетов `PredefinedDataName` может использоваться как дополнительный compatibility/admission marker внутри `chart_identity`, но не заменяет canonical identity.
- Зафиксировать compatibility contract для reusable accounts на базе существующего metadata/business-identity substrate:
  - operator-facing compatibility class: `config_name + config_version + chart_identity`;
  - runtime admission/pinning: `metadata_catalog_snapshot_id`, `catalog_version`, `metadata_hash`, `provenance_database_id`, `confirmed_at` и published-surface evidence по target infobase.
- Сохранить текущие `master_data.*` token contracts и существующие publication entity types как backward-compatible subset нового hub.
- Привязать `GLAccount` и `GLAccountSet` к configuration-scoped compatibility markers, согласованным с metadata snapshot provenance и target business configuration identity.
- Явно разделить operator-facing compatibility class и runtime admission: совпавший `config_name + config_version + chart_identity` нужен для discovery/grouping, но сам по себе не разрешает publication/factual use без pinned metadata snapshot и published-surface coverage target ИБ.
- Разрешить `document_policy` и publication compile использовать canonical account tokens и resolved account bindings вместо raw GUID/hardcoded literals, но только после metadata-typed field validation по target OData metadata snapshot.
- Перевести factual account scope с hardcoded defaults на first-class pinned revision `GLAccountSet` artifact + fail-closed preflight coverage по target infobases.
- Ввести versioned factual scope bridge между orchestrator и worker:
  - верхнеуровневые runtime contracts `pool_factual_sync_workflow.v1` и `pool_factual_read_lane.v1` остаются стабильными на bridge-периоде;
  - новый nested `factual_scope_contract.v2` становится first-class source-of-truth для `gl_account_set_revision_id`, `effective_members`, `scope_fingerprint`, compatibility provenance и target-specific `resolved_bindings`;
  - transitional dual-read/dual-write режим сохраняет legacy `account_codes` как derived compatibility projection, чтобы rollout и rollback не ломали historical replay и текущий worker contract.
- Зафиксировать replay-safe factual semantics:
  - historical replay использует pinned `resolved_bindings` snapshot из artifact;
  - runtime НЕ пере-резолвит latest bindings для уже созданных factual artifacts;
  - отсутствие pinned binding snapshot приводит к fail-closed blocker, а не к silent fallback на latest state.
- Явно зафиксировать capability matrix:
  - `GLAccount` поддерживает tenant-scoped canonical identity, manual upsert, binding и bootstrap import;
  - `GLAccount` в этом change НЕ поддерживает automatic outbound mutation/bidirectional sync в target ИБ;
  - `GLAccountSet` остаётся CC-owned profile и не materialize'ится как direct IB object.
- Зафиксировать operator UX для capability-gated sync surfaces:
  - `GLAccount` не получает generic mutating sync actions и показывается только как `bootstrap-only` / `unsupported-by-design` для outbound/bidirectional directions;
  - `GLAccountSet` не появляется как mutating sync entity и может отображаться только как non-actionable profile state.
- Подготовить hub к additive onboarding новых reusable entity types без создания отдельного ad hoc каталога и отдельного runtime path под каждый новый тип.
- Зафиксировать frontend dependency order:
  - route-level shell и responsive fallback для `/pools/master-data` поставляются через active change `refactor-ui-platform-workflow-template-workspaces`;
  - текущий change добавляет новые zones/forms/contracts внутри canonical shell и НЕ вводит второй parallel page foundation;
  - UI-delivery по этому change не считается завершённым, пока canonical shell dependency не влита или не перенесена в scope этого change как явный prerequisite, а не как ad hoc fork.

## Impact
- Affected specs:
  - `pool-master-data-hub`
  - `pool-master-data-hub-ui`
  - `pool-master-data-sync`
  - `pool-document-policy`
  - `pool-odata-publication`
  - `pool-factual-balance-monitoring`
- Affected code:
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/api_v2/views/intercompany_pools_master_data.py`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `frontend/src/pages/Pools/**`
  - `contracts/**`
  - `go-services/worker/internal/drivers/poolops/**`
- Related changes:
  - `refactor-ui-platform-workflow-template-workspaces`
