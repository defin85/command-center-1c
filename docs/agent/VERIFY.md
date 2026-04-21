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

Во время итераций предпочитай project-aware focused/shard `vitest` прогоны вместо repo-wide `cd frontend && npm run test:run`, если change локален и не затрагивает несколько тяжёлых route-level suites.

Checked-in heavy `vitest` perimeter deliberately runs its heavy projects последовательно, чтобы не разгонять CPU contention на low-core local contour.

Перед handoff/landing frontend change полный `cd frontend && npm run test:run` остаётся обязательным, если не согласовано явное исключение.

```bash
cd frontend && npm run generate:api
cd frontend && npm run generate:api:if-needed
cd frontend && npm run lint
cd frontend && npm run test:run:changed
cd frontend && npm run test:run:fast -- <path>
cd frontend && npm run test:run:heavy -- <path>
cd frontend && npm run test:run:related -- <source-file...>
cd frontend && npm run test:run:pools-heavy
cd frontend && npm run test:run:decisions-heavy
cd frontend && npm run test:run -- <path>
cd frontend && npx vitest run <path...>
cd frontend && npm run validate:ui-platform:iter
cd frontend && npm run test:browser:ui-platform:workspaces
cd frontend && npm run test:browser:ui-platform:runtime-surfaces
cd frontend && npm run test:browser:ui-platform:governance-settings
cd frontend && npm run test:browser:ui-platform:shell-contracts
cd frontend && npm run test:browser:ui-platform
cd frontend && npm run measure:ui-validation -- --artifact ../docs/observability/artifacts/ui-validation-runtime/<run-id>.json
cd frontend && npm run validate:ui-platform
```

`generate:api:if-needed` предназначен для локальной итерации: он пропускает `orval`, если inputs/generator hooks не менялись, и fail-closed останавливается на dirty generated tree вместо тихого overwrite.

`test:run:changed` использует builtin `vitest --changed`; при изменении `package.json` или `vitest.config.ts` runner сам расширяет прогон до полного scope. `test:run:related -- <source-file...>` полезен, когда нужно явно прогнать тесты, статически связанные с конкретными source files.

`validate:ui-platform:iter` — это быстрый локальный iteration gate без browser contract. Перед handoff он не заменяет обязательные `npm run test:browser:ui-platform` и `npm run validate:ui-platform`.

`test:browser:ui-platform:*` — это repo-owned focused browser reruns по checked-in shard families (`workspaces`, `runtime-surfaces`, `governance-settings`, `shell-contracts`). Они ускоряют локальную итерацию, но не заменяют полный `npm run test:browser:ui-platform`.

`measure:ui-validation` по умолчанию делает `3` последовательных samples и пишет отдельные summaries для `vitest` и browser gate. Если один full run резко расходится с недавним baseline, perf verdict не считается авторитетным без repeated measurement или явного diagnostic explanation. Checked-in artifact directory: `docs/observability/artifacts/ui-validation-runtime/`.

### Orchestrator

```bash
./scripts/dev/lint.sh --python
./scripts/dev/pytest.sh -q <path>
```

### UI Observability / Agent Access

```bash
./scripts/dev/pytest.sh -q apps/api_v2/tests/test_ui_incident_telemetry.py
./contracts/scripts/export-django-openapi.sh
bash -n debug/_cc1c_api.sh debug/query-ui-incidents.sh debug/query-ui-timeline.sh debug/get-trace.sh
./debug/query-ui-incidents.sh --help
./debug/query-ui-timeline.sh --help
./debug/get-trace.sh --help
```

Если change затрагивает live runtime wiring, добавь targeted smoke по canonical surfaces:

```bash
./debug/export-ui-journal.sh "<url-pattern>"
./debug/query-ui-incidents.sh limit=5
./debug/query-ui-timeline.sh request_id=<request-id>
./debug/get-trace.sh <trace-id>
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
cd frontend && timeout 120 npx vitest run src/pages/Pools/__tests__/PoolRunsPage.authoring.test.tsx -t "batch-backed|creates a receipt batch"
cd frontend && npm run test:browser:ui-platform
cd frontend && npm run measure:ui-validation -- --artifact ../docs/observability/artifacts/ui-validation-runtime/<run-id>.json
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

| Runtime            | Canonical test command                                          |
| ------------------ | --------------------------------------------------------------- |
| `orchestrator`     | `./scripts/dev/pytest.sh -q <path>`                             |
| `event-subscriber` | `./scripts/dev/pytest.sh -q orchestrator/apps/operations/tests` |
| `api-gateway`      | `cd go-services/api-gateway && go test ./...`                   |
| `worker`           | `cd go-services/worker && go test ./...`                        |
| `worker-workflows` | `cd go-services/worker && go test ./...`                        |
| `frontend`         | `cd frontend && npm run test:run -- <path>`                     |

## Handoff Expectations

- `analysis/review`: findings или conclusion anchored to evidence, assumptions и residual uncertainty.
- `local change`: touched files, minimal check set, unresolved risks и sync затронутых docs/contracts.
- `delivery`: `Requirement -> Code -> Test`, актуальные Beads/OpenSpec statuses и выполненные delivery actions.
