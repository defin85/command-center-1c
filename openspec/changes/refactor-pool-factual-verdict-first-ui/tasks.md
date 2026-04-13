## 1. Contract

- [ ] 1.1 Доработать `pool-factual-balance-monitoring`, чтобы factual workspace был обязан показывать operator verdict и aggregate движение по пулу before diagnostics.
- [ ] 1.2 Зафиксировать для master pane отдельный bounded factual overview contract, выровненный с route quarter context и не расширяющий generic `/api/v2/pools/`. (после 1.1)

## 2. Backend read model and contracts

- [ ] 2.1 Добавить lightweight factual overview API/read model для selection pane, который использует те же verdict inputs, что и selected detail, и поддерживает explicit `quarter_start` route context. (после 1.2)
- [ ] 2.2 Обновить OpenAPI/generated client surfaces и targeted backend coverage для overview contract без изменения generic `/api/v2/pools/` semantics. (после 2.1)

## 3. Frontend UI refactor

- [ ] 3.1 Интегрировать master pane с dedicated factual overview contract и ввести compact per-pool health summary без sequential detail fetch. (после 2.2)
- [ ] 3.2 Ввести deterministic overall health model для selected factual workspace и overview rows. (после 3.1)
- [ ] 3.3 Перестроить detail pane в `verdict-first` порядок: `Overall state` -> `Pool movement summary` -> secondary operational cards -> diagnostics/tables. (после 3.2)
- [ ] 3.4 Сделать `incoming_amount`, `outgoing_amount` и `open_balance` first-class visual summary с derived completion ratio или явным zero-incoming сообщением. (после 3.3)
- [ ] 3.5 Понизить `scope lineage`, per-checkpoint diagnostics, raw codes и handoff links до secondary disclosure без потери investigatory depth. (после 3.4)

## 4. Verification

- [ ] 4.1 Обновить unit coverage для one-glance verdict, aggregate movement summary, quarter-context alignment и master-pane problem scan. (после 3.5)
- [ ] 4.2 Добавить/обновить backend contract coverage для factual overview API и browser coverage для `/pools/factual`, подтверждающую, что verdict и aggregate movement видны до diagnostic details. (после 4.1)
- [ ] 4.3 Прогнать `./scripts/dev/pytest.sh -q apps/api_v2/tests/test_pool_factual_api.py`, `contracts/scripts/build-orchestrator-openapi.sh check`, `contracts/scripts/verify-generated-code.sh`, `cd frontend && npm run test:run -- src/pages/Pools/__tests__/PoolFactualPage.test.tsx`, `cd frontend && npm run test:browser:ui-platform`, `openspec validate refactor-pool-factual-verdict-first-ui --strict --no-interactive`. (после 4.2)
