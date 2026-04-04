## 1. Domain Model And Contracts
- [x] 1.1 Добавить persisted storage contract для `GLAccount`, `GLAccountSet`, draft state, published revisions и members.
- [x] 1.2 Сделать `chart_identity` и account compatibility markers first-class persisted fields и частью deterministic lookup contract.
- [x] 1.3 Обновить OpenAPI/contracts для `gl-accounts` и `gl-account-sets`, включая revision read-model и mutating actions.

## 2. Backend Runtime
- [x] 2.1 Добавить validators и type-specific binding scope для `GLAccount` без смешения canonical identity и `Ref_Key`.
- [x] 2.2 Поддержать bootstrap import для `GLAccount` через existing master-data lifecycle.
- [x] 2.3 Добавить `master_data.gl_account.<canonical_id>.ref` в document-policy compile path с metadata-aware typed validation.
- [x] 2.4 Обновить publication payload resolve для account refs через binding artifact target ИБ.
- [x] 2.5 Зафиксировать registry-enforced bootstrap-only / no-outbound ownership contract для `GLAccount` и no-sync contract для `GLAccountSet`.

## 3. Verification
- [x] 3.1 Добавить backend tests на `GLAccount` bindings, uniqueness по `chart_identity`, compatibility validation и immutable `GLAccountSet` revisions.
- [x] 3.2 Добавить tests на account token compile/validation и publication account ref resolution.
- [x] 3.3 Прогнать `openspec validate 02-extend-master-data-hub-with-reusable-accounts --strict --no-interactive`.
