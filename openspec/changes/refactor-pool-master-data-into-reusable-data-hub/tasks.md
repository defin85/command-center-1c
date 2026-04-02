## 1. Domain Model And Contracts
- [ ] 1.1 Спроектировать registry-driven reusable-data model поверх текущего `Pool Master Data` без поломки существующих entity/API contracts.
- [ ] 1.2 Добавить canonical entity type `GLAccount` и versioned profile `GLAccountSet`, а также type-specific binding scope для `GLAccount`.
- [ ] 1.3 Зафиксировать explicit capability matrix для `GLAccount` и `GLAccountSet`, включая запрет automatic outbound/bidirectional sync для plan-of-accounts semantics в этом change.
- [ ] 1.4 Добавить configuration-scoped compatibility markers для reusable account entities и их связь с metadata snapshot provenance / target business configuration identity.
- [ ] 1.5 Обновить OpenAPI/contracts для новых `/api/v2/pools/master-data/gl-accounts/` и `/api/v2/pools/master-data/gl-account-sets/` surfaces.
- [ ] 1.6 Подготовить миграцию/backfill для default-compatible factual account set revision, который заменит current hardcoded defaults.

## 2. Backend Runtime
- [ ] 2.1 Расширить orchestrator read/write model, validators и bindings для новых reusable entity types.
- [ ] 2.2 Расширить bootstrap/sync routing так, чтобы `GLAccount` использовал тот же staged job lifecycle без отдельного ad hoc pipeline, а `GLAccountSet` не попадал в direct sync-to-IB path.
- [ ] 2.3 Поддержать `master_data.gl_account.<canonical_id>.ref` в document-policy compile и token resolution с metadata-aware field typing validation.
- [ ] 2.4 Обновить publication compile/runtime так, чтобы account fields могли резолвиться через reusable-data bindings.
- [ ] 2.5 Перевести factual preflight/runtime/scheduler с hardcoded account codes на selected pinned `GLAccountSet` revision и fail-closed coverage checks.
- [ ] 2.6 Сохранять pinned `gl_account_set_revision_id` и effective member snapshot в factual checkpoints/preflight artifacts, чтобы historical replay не зависел от поздних правок профиля.

## 3. Frontend And Operator UX
- [ ] 3.1 Расширить `/pools/master-data` workspace вкладками `GLAccount` и `GLAccountSet`, сохранив текущие operator entry points.
- [ ] 3.2 Расширить token picker и related authoring flows поддержкой `GLAccount`.
- [ ] 3.3 Добавить operator-facing readiness/remediation signals для missing account bindings, incompatible configuration markers и incomplete factual/publication account coverage.
- [ ] 3.4 Расширить bootstrap import wizard поддержкой import/resolution для `GLAccount`.
- [ ] 3.5 Показать revision/pinning semantics для `GLAccountSet`, чтобы оператор видел draft/latest vs pinned runtime revision.

## 4. Verification
- [ ] 4.1 Добавить backend tests на reusable-data registry, capability matrix, `GLAccount` bindings, configuration compatibility validation, factual coverage fail-closed и publication account token resolution.
- [ ] 4.2 Добавить frontend tests на новые workspace zones, forms, token picker и remediation states.
- [ ] 4.3 Добавить tests на pinning `GLAccountSet` revision в factual artifacts и на отсутствие automatic outbound sync для `GLAccount` / `GLAccountSet`.
- [ ] 4.4 Провести live verification на published OData ИБ: подтвердить account refs в document header/table parts, configuration-compatible resolve и успешный reusable-data path.
- [ ] 4.5 Прогнать `openspec validate refactor-pool-master-data-into-reusable-data-hub --strict --no-interactive`.
