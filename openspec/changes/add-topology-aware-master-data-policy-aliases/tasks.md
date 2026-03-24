## 1. Контракт

- [x] 1.1 Зафиксировать в `pool-document-policy` topology-aware alias grammar для party/contract participants.
- [x] 1.2 Зафиксировать в `pool-document-policy`, что aliases резолвятся в static canonical `master_data.*`
  токены во время `document_plan_artifact` compile и не уходят downstream как unresolved syntax.
- [x] 1.3 Зафиксировать, что static canonical tokens для всех текущих master-data entity types (`party`, `item`,
  `contract`, `tax_profile`) остаются поддержанным runtime contract и не сужаются новым alias dialect.
- [x] 1.4 Зафиксировать в `pool-master-data-hub` role-aware resolution через `Organization.master_party` для
  `edge.parent` / `edge.child`.
- [x] 1.5 Зафиксировать fail-closed diagnostics для malformed alias, missing `Organization->Party` binding и
  missing party role.
- [x] 1.6 Явно задокументировать, что будущий operator-selected `item` / `tax_profile` path должен materialize'иться
  в существующие static canonical tokens, но сам UI/run-input contract не входит в scope этого change.

## 2. Backend runtime

- [x] 2.1 Реализовать parser/resolver topology-aware alias grammar в
  `orchestrator/apps/intercompany_pools/document_plan_artifact_contract.py`.
- [x] 2.2 Нормализовать alias-bearing `field_mapping` и `table_parts_mapping` в static canonical tokens на этапе
  compile `document_plan_artifact`.
- [x] 2.3 Расширить readiness/preflight blockers для topology participant resolution и role validation.
- [x] 2.4 Сохранить backward compatibility для existing static `master_data.party.<canonical>.*` и
  `master_data.contract.<canonical>.*` tokens.

## 3. Adoption для top-down execution pack

- [x] 3.1 Подготовить новую revision `realization` policy на topology-aware aliases вместо literal GUID.
- [x] 3.2 Подготовить новую revision `receipt` policy на topology-aware aliases вместо literal GUID.
- [x] 3.3 Перепинить `top-down` execution pack на новые policy revisions без изменения structural slot contract.

## 4. Проверка

- [x] 4.1 Добавить unit tests на compile-time rewrite aliases в static party/contract tokens для нескольких edges
  с одним и тем же slot.
- [x] 4.2 Добавить unit tests на `MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING` и
  `MASTER_DATA_PARTY_ROLE_MISSING` для topology participant resolution.
- [x] 4.3 Добавить regression test на `top-down`-подобный compile path, где один reusable `receipt` policy
  корректно подставляет разных counterparties на разных child edges.
- [x] 4.4 Добавить regression tests, что static `master_data.item.*.ref` и `master_data.tax_profile.*.ref`
  продолжают проходить compile/gate path без topology-aware rewrite.
- [x] 4.5 Выполнить `openspec validate add-topology-aware-master-data-policy-aliases --strict --no-interactive`.
