---
name: cc1c-test-runner
description: "Run and debug tests across all components: Go unit tests, Django tests, React tests, integration tests. Check coverage, analyze failures, suggest fixes. Use when user wants to run tests, check test coverage, debug test failures, or mentions testing, pytest, go test, jest."
allowed-tools: ["Bash", "Read", "Grep"]
---

# cc1c-test-runner

## Purpose

Запускать и отлаживать тесты для всех компонентов проекта CommandCenter1C, обеспечивать требуемый coverage (> 70%) и помогать исправлять failing tests.

## When to Use

Используй этот skill когда:
- Запуск тестов (любого типа: unit, integration, E2E)
- Проверка test coverage
- Debugging failed tests
- Анализ test results и улучшение coverage
- Пользователь упоминает: test, testing, pytest, go test, jest, coverage, failed, unittest

## Quick Commands

### Run All Tests

```bash
# All tests (all components)
make test

# Specific component
make test-go           # Go services
make test-django       # Django orchestrator
make test-frontend     # React frontend

# With coverage
make test-coverage     # All with coverage
make coverage-go       # Go coverage only
make coverage-django   # Django coverage only
```

### Watch Mode (Development)

```bash
# Auto-rerun tests on file changes
make test-watch              # All tests
make test-watch-django       # Django only
make test-watch-frontend     # Frontend only
```

## Coverage Requirements

**⚠️ КРИТИЧНО: Coverage > 70% обязательно!**

```
Component           Target Coverage    Priority
──────────────────────────────────────────────
Go Shared           > 80%              HIGH
Go API Gateway      > 70%              HIGH
Go Worker           > 70%              HIGH
Django Apps         > 70%              HIGH
React Components    > 60%              MEDIUM
```

## Testing Strategy

### Test Types

```
Unit Tests:        Тестируют отдельные функции/классы
Integration Tests: Тестируют взаимодействие между компонентами
E2E Tests:         Тестируют полный user flow (Phase 2+)
Load Tests:        Тестируют производительность (Phase 5)
```

## Go Tests

### Quick Start

```bash
# All Go tests
cd go-services
go test ./...

# With verbose output
go test -v ./...

# With coverage
go test -cover ./...
go test -coverprofile=coverage.out ./...

# View coverage in browser
go tool cover -html=coverage.out

# Specific test
go test -run TestHandlerName ./api-gateway/internal/handlers

# Race condition detection
go test -race ./...
```

**Детали:** {baseDir}/reference/go-testing.md
**Пример:** {baseDir}/examples/go-test-example.go

## Django Tests

### Quick Start

```bash
# All Django tests
cd orchestrator
python manage.py test

# Specific app
python manage.py test apps.operations

# With coverage (using pytest)
pytest --cov=apps --cov-report=html

# Parallel execution
python manage.py test --parallel

# Failed tests only (pytest)
pytest --lf  # last failed
pytest --ff  # failed first
```

**Детали:** {baseDir}/reference/django-testing.md
**Пример:** {baseDir}/examples/django-test-example.py

## React/Frontend Tests

### Quick Start

```bash
# All tests
cd frontend
npm test

# Watch mode (interactive)
npm test -- --watch

# Coverage
npm test -- --coverage

# Specific test file
npm test -- OperationForm.test.tsx

# Run once (CI mode)
npm test -- --watchAll=false
```

**Детали:** {baseDir}/reference/react-testing.md
**Пример:** {baseDir}/examples/react-test-example.tsx

## Debugging Failed Tests

### Quick Diagnosis

```bash
# pytest - drop into debugger on failure
pytest --pdb

# pytest - verbose with print statements
pytest -vv -s

# Go - verbose with test output
go test -v ./...

# Go - run specific failing test
go test -v -run TestMyFailingTest ./package

# npm/Jest - run with verbose output
npm test -- --verbose
```

### Common Failure Patterns

**1. Intermittent failures (flaky tests)**
- **Причина:** Race conditions, timing issues, shared state
- **Решение:** Wait for conditions, isolate state, fix race conditions

**2. Database state issues**
- **Причина:** Tests depend on order, shared database state
- **Решение:** Proper setUp/tearDown, use transactions

**3. Mock issues**
- **Причина:** Mock not applied correctly, wrong path
- **Решение:** Patch where used (not where defined), configure return values

**Полный troubleshooting:** {baseDir}/reference/debugging.md

## Coverage Analysis

### Checking Coverage

```bash
# Overall project coverage
make coverage

# Component-specific
make coverage-go
make coverage-django
make coverage-frontend

# Generate HTML reports
make coverage-report
```

### Improving Coverage

**1. Find uncovered code:**
```bash
# Django
pytest --cov=apps --cov-report=term-missing | grep "0%"

# Go
go tool cover -func=coverage.out | grep "0.0%"
```

**2. Write tests for uncovered code:**
- Start with critical paths
- Then edge cases
- Then error handling

**3. Verify improvement:**
```bash
# Before
pytest --cov=apps

# After new tests
pytest --cov=apps
# Coverage should increase
```

## Integration Tests

### Running Integration Tests

```bash
# Django integration tests
python manage.py test --tag=integration

# Go integration tests
go test -tags=integration ./...

# With test database cleanup
python manage.py test --tag=integration --keepdb=False
```

## Critical Constraints

1. **Coverage > 70%** - обязательно для Go/Django, > 60% для React
2. **No Flaky Tests** - все тесты должны быть стабильными (pass 100%)
3. **Fast Tests** - unit tests < 1s, integration tests < 10s
4. **Isolated Tests** - тесты НЕ зависят друг от друга или от порядка
5. **CI/CD Ready** - тесты проходят в GitHub Actions (без ручных зависимостей)

## Common Test Commands Cheatsheet

```bash
# Quick test runs
make test                    # All tests
make test-quick              # Fast tests only
make test-integration        # Integration tests only

# Coverage
make coverage                # All coverage
make coverage-report         # Generate HTML reports

# Debugging
make test-debug              # With debugger
make test-verbose            # Verbose output

# Continuous
make test-watch              # Auto-rerun on changes

# Specific
make test-go                 # Go only
make test-django             # Django only
make test-frontend           # Frontend only
```

## References

### Detailed Documentation
- {baseDir}/reference/go-testing.md - Go test patterns, coverage, debugging
- {baseDir}/reference/django-testing.md - Django/DRF test patterns
- {baseDir}/reference/react-testing.md - React Testing Library patterns
- {baseDir}/reference/debugging.md - отладка падающих тестов

### Code Examples
- {baseDir}/examples/go-test-example.go - table-driven test pattern
- {baseDir}/examples/django-test-example.py - DRF ViewSet test
- {baseDir}/examples/react-test-example.tsx - React component test

### Related Skills
- `cc1c-service-builder` - для исправления failed tests
- `cc1c-navigator` - для поиска связанного кода при debugging
- `cc1c-devops` - для проверки окружения при integration test failures

### Project Documentation
- [CLAUDE.md](../../../CLAUDE.md) - Testing Strategy section
- [CI/CD config](../../../.github/workflows/test.yml) - GitHub Actions setup

---

**Version:** 2.0 (Optimized)
**Last Updated:** 2025-11-06
**Changelog:**
- 2.0 (2025-11-06): Refactored to 180 lines, moved details to reference/ and examples/
- 1.0 (2025-01-17): Initial release with multi-language test support
