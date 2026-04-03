## 1. Domain Model And Contracts
- [ ] 1.1 Спроектировать executable registry-driven reusable-data model поверх текущего `Pool Master Data`, чтобы capability matrix, sync/bootstrap routing и runtime gating читались из одного registry contract.
- [ ] 1.2 Зафиксировать reusable-account compatibility contract на базе существующего metadata/business-identity substrate: `config_name + config_version + chart_identity` как operator-facing compatibility class, а `metadata_catalog_snapshot_id`, `catalog_version`, `metadata_hash`, `provenance_database_id`, `confirmed_at` вместе с published-surface evidence как runtime admission/pinning contract.
- [ ] 1.3 Добавить first-class persisted storage contract для `GLAccount`, `GLAccountSet`, immutable revisions/members и type-specific binding scope для `GLAccount`, явно разделив tenant-scoped canonical identity `GLAccount` и per-infobase `ib_ref_key` / `Ref_Key` binding.
- [ ] 1.4 Сделать `chart_identity` first-class persisted binding scope field с DB-level uniqueness и deterministic lookup contract; для predefined accounts разрешить optional `PredefinedDataName` как additional compatibility marker, не заменяющий canonical identity и target-specific binding.
- [ ] 1.5 Зафиксировать explicit capability matrix для `GLAccount` и `GLAccountSet`, включая registry-enforced запрет automatic outbound/bidirectional sync для plan-of-accounts semantics в этом change.
- [ ] 1.6 Обновить OpenAPI/contracts для новых `/api/v2/pools/master-data/gl-accounts/` и `/api/v2/pools/master-data/gl-account-sets/` surfaces, а также для versioned factual scope artifact/pinning payload.
- [ ] 1.7 Спроектировать versioned factual scope bridge как nested `factual_scope_contract.v2` внутри стабильных `pool_factual_sync_workflow.v1` / `pool_factual_read_lane.v1`, сохранив legacy compatibility fields для replay-safe rollout/rollback между orchestrator и worker.
- [ ] 1.8 Подготовить миграцию/backfill для default-compatible factual account set revision, который заменит current hardcoded defaults.

## 2. Backend Runtime
- [ ] 2.1 Расширить orchestrator read/write model, validators и bindings для новых reusable entity types без размывания type-specific invariants.
- [ ] 2.2 Перевести canonical upsert, binding upsert, outbox fan-out, sync workflow enqueue и bootstrap import admission на registry-enforced capability checks.
- [ ] 2.3 Вывести token parsing, token picker catalogs, bootstrap dependency order и type eligibility из executable reusable-data registry, оставив существующие enum/if-else paths только как compatibility wrappers на bridge-период.
- [ ] 2.4 Расширить bootstrap/sync routing так, чтобы `GLAccount` использовал тот же staged job lifecycle без отдельного ad hoc pipeline, а `GLAccountSet` и `GLAccount` outbound/bidirectional mutation plan-of-accounts не попадали в direct sync-to-IB path.
- [ ] 2.5 Поддержать `master_data.gl_account.<canonical_id>.ref` в document-policy compile и token resolution с metadata-aware typed field validation по target OData metadata snapshot и pinned compatibility provenance.
- [ ] 2.6 Обновить publication compile/runtime так, чтобы account fields могли резолвиться через reusable-data bindings только из typed-validated binding artifact target ИБ; `Ref_Key` не должен трактоваться как cross-infobase identity.
- [ ] 2.7 Внедрить factual scope bridge: dual-write nested `factual_scope_contract.v2` с `gl_account_set_revision_id`, `effective_members`, `scope_fingerprint`, provenance и `scope_contract_version`, плюс legacy `account_codes`; worker/runtime должны работать в dual-read режиме внутри текущих `v1` envelopes до cutover.
- [ ] 2.8 Перевести factual preflight/runtime/scheduler с hardcoded account codes на selected pinned `GLAccountSet` revision и fail-closed coverage checks.
- [ ] 2.9 Сохранять first-class factual scope artifact с pinned `gl_account_set_revision_id`, effective member snapshot и stable scope fingerprint, чтобы historical replay не зависел от поздних правок профиля.

## 3. Frontend And Operator UX
- [ ] 3.1 Выполнить route-level foundation `/pools/master-data` через canonical shell из `refactor-ui-platform-workflow-template-workspaces`; текущий change не должен вводить второй parallel page foundation и не может закрыть UI-delivery, пока этот prerequisite не landed явно.
- [ ] 3.2 Расширить `/pools/master-data` workspace вкладками `GLAccount` и `GLAccountSet`, сохранив текущие operator entry points внутри canonical shell.
- [ ] 3.3 Расширить token picker и related authoring flows поддержкой `GLAccount`.
- [ ] 3.4 Сделать `chart_identity`, compatibility markers, snapshot provenance и revision/member semantics явными operator-facing полями, а не скрытым metadata blob.
- [ ] 3.5 Добавить operator-facing readiness/remediation signals для missing account bindings, incompatible configuration markers и incomplete factual/publication account coverage.
- [ ] 3.6 Расширить bootstrap import wizard поддержкой import/resolution для `GLAccount`.
- [ ] 3.7 Показать revision/pinning semantics для `GLAccountSet`, чтобы оператор видел draft/latest vs pinned runtime revision.
- [ ] 3.8 Сделать capability-gated `Sync` UX явным: `GLAccount` не получает mutating outbound/bidirectional actions, а `GLAccountSet` скрывается из mutation-oriented sync list или показывается только как non-actionable profile state.

## 4. Verification
- [ ] 4.1 Добавить backend tests на reusable-data registry, capability matrix, registry-enforced sync gating, `GLAccount` bindings, DB-level uniqueness по `chart_identity`, separation canonical identity vs per-infobase `Ref_Key`, optional `PredefinedDataName` handling для predefined accounts, configuration compatibility validation, factual coverage fail-closed и publication account token resolution.
- [ ] 4.2 Добавить backend/runtime tests на factual scope bridge: nested `factual_scope_contract.v2` внутри `v1` envelopes, dual-write payload, dual-read worker compatibility, rollback-safe replay и эквивалентность derived legacy `account_codes`.
- [ ] 4.3 Добавить frontend tests на новые workspace zones, forms, token picker, provenance surfaces, capability-gated sync states и remediation states внутри canonical shell.
- [ ] 4.4 Добавить tests на pinning `GLAccountSet` revision в factual artifacts, stable effective member snapshot и на отсутствие automatic outbound sync для `GLAccount` / `GLAccountSet`.
- [ ] 4.5 Провести live verification на published OData ИБ: подтвердить account refs в document header/table parts, configuration-compatible resolve, successful `v2` factual scope handoff и rollback-safe reusable-data path.
- [ ] 4.6 Прогнать `openspec validate refactor-pool-master-data-into-reusable-data-hub --strict --no-interactive`.
