---
description: Run all tests for all components (Python, Go, TypeScript)
---

Запустить все тесты для всех компонентов проекта.

## Usage

```bash
# Через Make
make test

# Или компоненты отдельно
make test-go        # Go только
make test-django    # Django только
make test-frontend  # React только
```

## With Coverage

```bash
make test-coverage
```

## Manual Testing

**Django tests:**
```bash
cd orchestrator
pytest -v --cov --cov-report=html
```

**Go tests:**
```bash
cd go-services
go test -v -race -coverprofile=coverage.out ./...
```

**Frontend tests:**
```bash
cd frontend
npm test -- --coverage
```

## When to Use

- Перед коммитом
- После изменения кода
- Перед PR
- В CI/CD pipeline

## Expected Results

**Success criteria:**
- All tests pass
- Coverage > 70% (Go, Django)
- Coverage > 60% (React)

## Common Issues

**Tests fail:**
```bash
# Запустить только падающий компонент
make test-go
make test-django
make test-frontend
```

**Database connection error:**
```bash
docker-compose logs postgres
docker-compose restart postgres
```

**Module not found:**
```bash
# Python
pip install -r orchestrator/requirements.txt

# Go
go mod download

# TypeScript
cd frontend && npm install
```

Детали: skill `cc1c-test-runner`

## Coverage Reports

После тестов доступны:
- Python: `orchestrator/htmlcov/index.html`
- Go: `go-services/coverage.html`
- TypeScript: `frontend/coverage/index.html`

## Related

- Skill: `cc1c-test-runner` - детальное тестирование
