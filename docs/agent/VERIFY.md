# Verification Guide

Статус: authoritative agent-facing guidance.

## Completion Profiles

### `analysis/review`

- Use when: нужен findings-first ответ, audit, review, архитектурный анализ или guidance-only результат.
- Минимум evidence: выводы, assumptions, file/spec/doc references и явная зона неопределённости.
- Проверка: read-only inspection и самый маленький релевантный command, если без него высок риск ошибиться.
- Не является default expectation: Beads status changes, commit, push, delivery-grade rollout steps.

### `local change`

- Use when: нужен scoped checked-in change без explicit merge-ready/rollout handoff.
- Минимум evidence: touched files, что изменено, какой минимальный automated check прогнан, какие residual risks остались.
- Проверка: smallest relevant validation set для изменённой поверхности; расширяй scope только если change пересекает несколько subsystems или contracts.
- Дополнительно: обнови routed docs/contracts, если change меняет workflow, source-of-truth reference или verification path.

### `delivery`

- Use when: approved OpenSpec execution, merge-ready handoff или change с explicit landing expectation.
- Минимум evidence: `Requirement -> Code -> Test` для всех mandatory requirements/scenarios.
- Проверка: полный релевантный gate для затронутых surfaces плюс alignment Beads/OpenSpec status.
- Delivery actions: `git pull --rebase`, commit и `git push` после успешных checks.
- Approved OpenSpec change implementation по умолчанию идёт как `delivery`.

## General Rule

Сначала запускай минимальный релевантный набор проверок, затем расширяй прогон только если change пересекает несколько подсистем, меняет contracts/runtime behavior или идёт как `delivery`.

## Canonical Validation By Change Type

### Agent Docs And Guidance

```bash
./scripts/dev/check-agent-doc-freshness.sh
```

### OpenSpec Change

```bash
openspec validate <change-id> --strict --no-interactive
```

### Frontend

UI skill routing lives in [ui-skills.md](./ui-skills.md). Выбор shared UI skills не заменяет проверки ниже.

Во время итераций предпочитай focused/shard `vitest` прогоны вместо repo-wide `cd frontend && npm run test:run`, если change локален и не затрагивает несколько тяжёлых route-level suites.

Перед handoff/landing frontend change полный `cd frontend && npm run test:run` остаётся обязательным, если не согласовано явное исключение.

```bash
cd frontend && npm run generate:api
cd frontend && npm run lint
cd frontend && npm run test:run -- <path>
cd frontend && npx vitest run <path...>
cd frontend && npm run test:browser:ui-platform
cd frontend && npm run validate:ui-platform
```

### Orchestrator

```bash
./scripts/dev/lint.sh --python
./scripts/dev/pytest.sh -q <path>
```

### API Gateway

```bash
./scripts/dev/lint.sh --go
cd go-services/api-gateway && go test ./...
```

### Worker / Worker-Workflows

```bash
./scripts/dev/lint.sh --go
cd go-services/worker && go test ./...
```

### Runtime Sanity

```bash
./debug/probe.sh all
```

### Pool Factual Monitoring

```bash
./scripts/dev/pytest.sh -q apps/intercompany_pools/tests/test_factual_scheduler_runtime.py apps/api_internal/tests/test_views_pools_factual.py
./scripts/dev/pytest.sh -q apps/intercompany_pools/tests/test_factual_preflight.py apps/intercompany_pools/tests/test_factual_preflight_command.py
./scripts/dev/pytest.sh -q apps/api_v2/tests/test_pool_factual_api.py apps/api_v2/tests/test_intercompany_pool_runs.py apps/api_v2/tests/test_pool_runs_openapi_contract_parity.py apps/intercompany_pools/tests/test_factual_preflight_docs_parity.py
./contracts/scripts/build-orchestrator-openapi.sh check
./contracts/scripts/validate-specs.sh
./contracts/scripts/verify-generated-code.sh
cd go-services/shared && go test ./config
cd go-services/worker && go test ./internal/drivers/poolops ./internal/orchestrator ./internal/scheduler/... ./cmd
cd frontend && npm run test:run -- src/pages/Pools/__tests__/PoolFactualPage.test.tsx
cd frontend && timeout 120 npx vitest run src/pages/Pools/__tests__/PoolRunsPage.test.tsx -t "batch-backed|creates a receipt batch"
cd frontend && npm run test:browser:ui-platform
cd frontend && npm run validate:ui-platform
./scripts/dev/check-agent-doc-freshness.sh
```

Live contour preflight before cohort widening:

```bash
cd orchestrator && ./venv/bin/python manage.py preflight_pool_factual_sync \
  --pool-id <pool-uuid> \
  --quarter-start 2026-01-01 \
  --requested-by-username <rbac-username-or-empty-when-service-mapping-exists> \
  --database-id <pilot-db-uuid> \
  --json \
  --strict
```

Operator path acceptance notes:

- `/pools/runs` is the default producer surface for canonical batch intake: use the `Create canonical batch` drawer from the create stage, then follow the auto-opened inspect context for the linked receipt run.
- Run-to-factual handoff must preserve `quarter_start` in the factual route so the settlement focus lands in the correct quarter, not just the latest pool snapshot.
- `Create canonical batch` is the shipped UI path, while `/pools/factual` is the shipped monitoring workspace for settlement and manual review.

## Runtime-Test Reference

Source of truth: `./debug/runtime-inventory.sh --json`

| Runtime | Canonical test command |
|---|---|
| `orchestrator` | `./scripts/dev/pytest.sh -q <path>` |
| `event-subscriber` | `./scripts/dev/pytest.sh -q orchestrator/apps/operations/tests` |
| `api-gateway` | `cd go-services/api-gateway && go test ./...` |
| `worker` | `cd go-services/worker && go test ./...` |
| `worker-workflows` | `cd go-services/worker && go test ./...` |
| `frontend` | `cd frontend && npm run test:run -- <path>` |

## Handoff Expectations

- `analysis/review`: findings или conclusion anchored to evidence, assumptions и residual uncertainty.
- `local change`: touched files, minimal check set, unresolved risks и sync затронутых docs/contracts.
- `delivery`: `Requirement -> Code -> Test`, актуальные Beads/OpenSpec statuses и выполненные delivery actions.
