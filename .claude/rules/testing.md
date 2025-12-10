# Testing & Linting

> Требования к тестированию и качеству кода.

## Linting (All Components)

```bash
./scripts/dev/lint.sh              # tsc + eslint + ruff + go vet
./scripts/dev/lint.sh --fix        # Auto-fix
./scripts/dev/lint.sh --ts         # TypeScript only
./scripts/dev/lint.sh --py         # Python only
./scripts/dev/lint.sh --go         # Go only
```

## Tests

### Django (orchestrator)

```bash
cd orchestrator && source venv/bin/activate
pytest                              # All tests
pytest apps/databases/              # Specific app
pytest -x                           # Stop on first failure
pytest --cov=apps                   # With coverage
```

### Go (go-services)

```bash
cd go-services/api-gateway && go test ./...
cd go-services/worker && go test ./...
cd go-services/ras-adapter && go test ./...
```

### Frontend (React)

```bash
cd frontend && npm test
npm run test:coverage               # With coverage
```

## Coverage Requirements

| Component | Minimum Coverage |
|-----------|-----------------|
| Django | > 70% |
| Go | > 70% |
| React | > 60% |

## Test Organization

### Django
```
orchestrator/
├── apps/
│   ├── databases/
│   │   └── tests/
│   │       ├── test_models.py
│   │       ├── test_views.py
│   │       └── test_services.py
│   └── operations/
│       └── tests/
```

### Go
```
go-services/
├── api-gateway/
│   └── internal/
│       └── handlers/
│           └── handlers_test.go
├── worker/
│   └── internal/
│       └── processor/
│           └── processor_test.go
```

### React
```
frontend/
└── src/
    ├── components/
    │   └── __tests__/
    │       └── Component.test.tsx
    └── pages/
        └── __tests__/
```

## Slash Command

```
/test-all  # Run all tests for all components
```
