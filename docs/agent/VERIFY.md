# Verification Guide

Статус: authoritative agent-facing guidance.

## General Rule

Сначала запускай минимальный релевантный набор проверок, затем расширяй прогон только если change пересекает несколько подсистем или меняет contracts/runtime behavior.

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

```bash
cd frontend && npm run generate:api
cd frontend && npm run lint
cd frontend && npm run test:run -- <path>
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
cd go-services/shared && go test ./config
cd go-services/worker && go test ./internal/drivers/poolops ./internal/orchestrator ./internal/scheduler/... ./cmd
cd frontend && npm run test:run -- src/pages/Pools/__tests__/PoolFactualPage.test.tsx
./scripts/dev/check-agent-doc-freshness.sh
```

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

## Review Before Handoff

- требование связано с конкретным кодом и проверкой
- выбран минимальный валидный check set
- нет silent fallback logic без явного согласования
- итоговый отчёт содержит `Requirement -> Code -> Test`
