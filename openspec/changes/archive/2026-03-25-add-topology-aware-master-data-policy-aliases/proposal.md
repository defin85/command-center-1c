# Change: add-topology-aware-master-data-policy-aliases

## Почему

Сейчас reusable `document_policy` можно выразить только через статические master-data токены вида
`master_data.party.<canonical_id>.<role>.ref` и `master_data.contract.<canonical_id>.<owner_counterparty>.ref`.
Для `top-down-pool` это уже привело к тому, что `realization` и `receipt` policy зашиты literal GUID-ами и не
могут переиспользоваться на разных ребрах одной и той же topology.

Одного заполнения `Pool Master Data` недостаточно: даже после sync текущие policy останутся topology-blind и не
смогут детерминированно подставлять продавца/покупателя по отношению `parent -> child` на каждом edge.

## Что меняется

- Все текущие поддержанные master-data entity types (`Party`, `Item`, `Contract`, `TaxProfile`) остаются валидным
  runtime input contract для publication path.
- `document_policy.v1` получает topology-aware alias dialect для master-data participant resolution на уровне
  `field_mapping` и `table_parts_mapping`, но только для topology-derived participants.
- `document_plan_artifact` резолвит эти aliases per edge в стабильные canonical `master_data.*` токены до
  downstream publication/runtime path.
- `pool master-data hub` становится каноническим источником topology participant resolution через
  `Organization.master_party` и role validation.
- Readiness/preflight и compile path блокируют preview/create-run fail-closed, если для topology participant нет
  `Organization->Party` binding или не хватает нужной роли.
- `Item` и `TaxProfile` не получают topology-aware alias grammar в рамках этого change: они продолжают использовать
  static canonical tokens и должны оставаться совместимыми с будущим operator-driven выбором на старте run.
- После появления capability текущие reusable decision resources `realization` и `receipt` для `top-down`
  переводятся с literal GUID / hardcoded counterparties на новый alias dialect.

## Impact

- Affected specs:
  - `pool-document-policy`
  - `pool-master-data-hub`
- Affected code:
  - `orchestrator/apps/intercompany_pools/document_plan_artifact_contract.py`
  - `orchestrator/apps/intercompany_pools/pool_domain_steps.py`
  - `orchestrator/apps/intercompany_pools/master_data_gate.py`
  - тесты `document_plan_artifact`, `pool_domain_steps`, `workflow_runtime`
  - seeded/live top-down decision resources (`realization`, `receipt`) и связанный execution pack
