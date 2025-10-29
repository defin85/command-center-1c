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
- Запуск тестов (любого типа)
- Проверка test coverage
- Debugging failed tests
- Анализ test results
- Пользователь упоминает: test, testing, pytest, go test, jest, coverage, failed, unittest

## Testing Strategy Overview

### Coverage Requirements

**КРИТИЧНО: Coverage > 70% обязательно!**

```
Component           Target Coverage    Current
─────────────────────────────────────────────────
Go API Gateway      > 70%             TBD
Go Worker           > 70%             TBD
Go Shared           > 80%             TBD
Django Apps         > 70%             TBD
React Components    > 60%             TBD
```

### Test Types

```
Unit Tests:        Тестируют отдельные функции/классы
Integration Tests: Тестируют взаимодействие между компонентами
E2E Tests:         Тестируют полный user flow (Phase 2+)
Load Tests:        Тестируют производительность (Phase 5)
```

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
make test-watch        # All tests
make test-watch-django # Django only
make test-watch-frontend # Frontend only
```

## Go Tests

### Running Go Tests

```bash
# All Go tests
cd go-services
go test ./...

# Specific package
go test ./api-gateway/internal/handlers

# With verbose output
go test -v ./...

# With coverage
go test -cover ./...
go test -coverprofile=coverage.out ./...

# View coverage in browser
go tool cover -html=coverage.out

# Specific test
go test -run TestHandlerName ./api-gateway/internal/handlers

# Benchmark tests
go test -bench=. ./...

# Race condition detection
go test -race ./...
```

### Go Test Examples

**Unit test example:**
```go
// api-gateway/internal/handlers/operations_test.go
package handlers

import (
    "testing"
    "github.com/stretchr/testify/assert"
)

func TestOperationHandler_ValidateRequest(t *testing.T) {
    tests := []struct {
        name    string
        input   OperationRequest
        wantErr bool
    }{
        {
            name: "valid request",
            input: OperationRequest{
                Name: "test operation",
                Type: "create_users",
            },
            wantErr: false,
        },
        {
            name: "empty name",
            input: OperationRequest{
                Name: "",
                Type: "create_users",
            },
            wantErr: true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            handler := NewOperationHandler(nil, nil)
            err := handler.ValidateRequest(&tt.input)

            if tt.wantErr {
                assert.Error(t, err)
            } else {
                assert.NoError(t, err)
            }
        })
    }
}
```

**Integration test example:**
```go
// worker/internal/processor/processor_integration_test.go
// +build integration

package processor

import (
    "testing"
    "github.com/stretchr/testify/require"
)

func TestProcessor_RealODataConnection(t *testing.T) {
    if testing.Short() {
        t.Skip("Skipping integration test")
    }

    processor := NewProcessor(Config{
        ODataURL: "http://localhost:8000/odata",
        Username: "test",
        Password: "test",
    })

    result, err := processor.Process(context.Background(), task)
    require.NoError(t, err)
    require.NotNil(t, result)
}
```

### Go Coverage Analysis

```bash
# Generate coverage report
go test -coverprofile=coverage.out ./...

# View summary
go tool cover -func=coverage.out

# Find uncovered code
go tool cover -func=coverage.out | grep -v "100.0%"

# HTML report
go tool cover -html=coverage.out -o coverage.html
```

## Django Tests

### Running Django Tests

```bash
# All Django tests
cd orchestrator
python manage.py test

# Specific app
python manage.py test apps.operations

# Specific test case
python manage.py test apps.operations.tests.test_views.OperationViewSetTest

# Specific test method
python manage.py test apps.operations.tests.test_views.OperationViewSetTest.test_create_operation

# With coverage
pytest --cov=apps --cov-report=html

# Verbose output
python manage.py test --verbosity=2

# Keep database (for debugging)
python manage.py test --keepdb

# Parallel execution
python manage.py test --parallel

# Failed tests only
pytest --lf  # last failed
pytest --ff  # failed first
```

### Django Test Examples

**Model test:**
```python
# apps/operations/tests/test_models.py
from django.test import TestCase
from apps.operations.models import Operation

class OperationModelTest(TestCase):
    def setUp(self):
        self.operation = Operation.objects.create(
            name="Test Operation",
            operation_type="create_users",
            status="pending"
        )

    def test_operation_creation(self):
        """Test operation is created correctly"""
        self.assertEqual(Operation.objects.count(), 1)
        self.assertEqual(self.operation.name, "Test Operation")
        self.assertEqual(self.operation.status, "pending")

    def test_str_representation(self):
        """Test string representation"""
        expected = f"Operation {self.operation.id}: Test Operation"
        self.assertEqual(str(self.operation), expected)

    def test_default_status(self):
        """Test default status is pending"""
        op = Operation.objects.create(name="Test")
        self.assertEqual(op.status, "pending")
```

**ViewSet test:**
```python
# apps/operations/tests/test_views.py
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from apps.operations.models import Operation

class OperationViewSetTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.operation = Operation.objects.create(
            name="Test Operation",
            operation_type="create_users"
        )

    def test_list_operations(self):
        """Test getting list of operations"""
        response = self.client.get('/api/operations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_operation(self):
        """Test creating new operation"""
        data = {
            'name': 'New Operation',
            'operation_type': 'update_users',
            'template_id': 1
        }
        response = self.client.post('/api/operations/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Operation.objects.count(), 2)

    def test_retrieve_operation(self):
        """Test getting single operation"""
        response = self.client.get(f'/api/operations/{self.operation.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Operation')

    def test_update_operation(self):
        """Test updating operation"""
        data = {'name': 'Updated Name'}
        response = self.client.patch(
            f'/api/operations/{self.operation.id}/',
            data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.name, 'Updated Name')
```

**Service layer test:**
```python
# apps/operations/tests/test_services.py
from django.test import TestCase
from unittest.mock import Mock, patch
from apps.operations.services import OperationService
from apps.operations.models import Operation

class OperationServiceTest(TestCase):
    def setUp(self):
        self.service = OperationService()

    @patch('apps.operations.tasks.process_operation_task.delay')
    def test_create_operation_dispatches_task(self, mock_task):
        """Test that creating operation dispatches Celery task"""
        data = {
            'name': 'Test Operation',
            'operation_type': 'create_users',
            'template_id': 1
        }

        operation = self.service.create_operation(data)

        self.assertIsNotNone(operation)
        mock_task.assert_called_once_with(operation.id)

    def test_validate_operation_data(self):
        """Test operation data validation"""
        invalid_data = {'name': ''}  # Empty name

        with self.assertRaises(ValueError):
            self.service.create_operation(invalid_data)
```

**Celery task test:**
```python
# apps/operations/tests/test_tasks.py
from django.test import TestCase
from unittest.mock import Mock, patch
from apps.operations.tasks import process_operation_task
from apps.operations.models import Operation

class TasksTest(TestCase):
    def setUp(self):
        self.operation = Operation.objects.create(
            name="Test Operation",
            operation_type="create_users"
        )

    @patch('apps.operations.tasks.WorkerClient')
    def test_process_operation_task(self, mock_worker):
        """Test operation processing task"""
        mock_worker.return_value.process.return_value = {'status': 'success'}

        result = process_operation_task(self.operation.id)

        self.assertEqual(result['status'], 'success')
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.status, 'completed')
```

### Django Coverage

```bash
# Install coverage
pip install coverage pytest-cov

# Run with coverage
pytest --cov=apps --cov-report=term-missing

# HTML report
pytest --cov=apps --cov-report=html
# Open htmlcov/index.html in browser

# Check specific app
pytest --cov=apps.operations --cov-report=term-missing

# Fail if coverage below threshold
pytest --cov=apps --cov-fail-under=70
```

## React/Frontend Tests

### Running React Tests

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

# Update snapshots
npm test -- -u

# Run once (CI mode)
npm test -- --watchAll=false
```

### React Test Examples

**Component test:**
```typescript
// frontend/src/components/OperationForm.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import OperationForm from './OperationForm';

describe('OperationForm', () => {
  it('renders form fields', () => {
    render(<OperationForm onSubmit={jest.fn()} />);

    expect(screen.getByLabelText('Название')).toBeInTheDocument();
    expect(screen.getByLabelText('Тип операции')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Создать' })).toBeInTheDocument();
  });

  it('validates required fields', async () => {
    render(<OperationForm onSubmit={jest.fn()} />);

    const submitButton = screen.getByRole('button', { name: 'Создать' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Пожалуйста введите название')).toBeInTheDocument();
    });
  });

  it('calls onSubmit with form data', async () => {
    const mockSubmit = jest.fn();
    render(<OperationForm onSubmit={mockSubmit} />);

    const nameInput = screen.getByLabelText('Название');
    const typeSelect = screen.getByLabelText('Тип операции');

    fireEvent.change(nameInput, { target: { value: 'Test Operation' } });
    fireEvent.change(typeSelect, { target: { value: 'create_users' } });

    const submitButton = screen.getByRole('button', { name: 'Создать' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledWith({
        name: 'Test Operation',
        operation_type: 'create_users'
      });
    });
  });
});
```

**API client test:**
```typescript
// frontend/src/api/endpoints/operations.test.ts
import { operationsApi } from './operations';
import { apiClient } from '../client';

jest.mock('../client');

describe('operationsApi', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it('fetches all operations', async () => {
    const mockData = [{ id: 1, name: 'Operation 1' }];
    (apiClient.get as jest.Mock).mockResolvedValue({ data: mockData });

    const result = await operationsApi.getAll();

    expect(apiClient.get).toHaveBeenCalledWith('/operations/');
    expect(result).toEqual(mockData);
  });

  it('creates new operation', async () => {
    const newOperation = { name: 'New Op', operation_type: 'create_users' };
    const mockResponse = { id: 1, ...newOperation };
    (apiClient.post as jest.Mock).mockResolvedValue({ data: mockResponse });

    const result = await operationsApi.create(newOperation);

    expect(apiClient.post).toHaveBeenCalledWith('/operations/', newOperation);
    expect(result).toEqual(mockResponse);
  });
});
```

**Store test (Zustand):**
```typescript
// frontend/src/stores/useOperations.test.ts
import { renderHook, act } from '@testing-library/react-hooks';
import { useOperations } from './useOperations';
import { operationsApi } from '../api/endpoints/operations';

jest.mock('../api/endpoints/operations');

describe('useOperations', () => {
  it('fetches operations on fetchData call', async () => {
    const mockData = [{ id: 1, name: 'Op 1' }];
    (operationsApi.getAll as jest.Mock).mockResolvedValue(mockData);

    const { result } = renderHook(() => useOperations());

    await act(async () => {
      await result.current.fetchData();
    });

    expect(result.current.data).toEqual(mockData);
    expect(result.current.loading).toBe(false);
  });

  it('handles errors during fetch', async () => {
    (operationsApi.getAll as jest.Mock).mockRejectedValue(new Error('API Error'));

    const { result } = renderHook(() => useOperations());

    await act(async () => {
      await result.current.fetchData();
    });

    expect(result.current.error).toBe('API Error');
    expect(result.current.loading).toBe(false);
  });
});
```

### React Coverage

```bash
# Coverage with thresholds
npm test -- --coverage --coverageThreshold='{"global":{"branches":60,"functions":60,"lines":60,"statements":60}}'

# View uncovered lines
npm test -- --coverage --verbose

# Coverage for specific files
npm test -- --coverage --collectCoverageFrom='src/components/**/*.tsx'
```

## Integration Tests

### End-to-End Flow Test

```python
# tests/integration/test_operation_flow.py
import pytest
from django.test import TestCase
from apps.operations.models import Operation
from apps.databases.models import Database

@pytest.mark.integration
class OperationFlowTest(TestCase):
    """Test complete operation flow"""

    def setUp(self):
        # Create test databases
        self.db1 = Database.objects.create(
            name="Test DB 1",
            odata_url="http://localhost:8000/odata1",
            username="test",
            password="test"
        )

    def test_create_and_execute_operation(self):
        """Test operation creation and execution"""

        # 1. Create operation
        operation = Operation.objects.create(
            name="Integration Test Operation",
            operation_type="create_users",
            template_id=1
        )

        self.assertEqual(operation.status, "pending")

        # 2. Dispatch to worker
        from apps.operations.tasks import process_operation_task
        task = process_operation_task.delay(operation.id)

        # 3. Wait for completion
        result = task.get(timeout=30)

        # 4. Verify result
        operation.refresh_from_db()
        self.assertEqual(operation.status, "completed")
        self.assertIsNotNone(result)
```

### Running Integration Tests

```bash
# Django integration tests
python manage.py test --tag=integration

# Go integration tests
go test -tags=integration ./...

# With test database cleanup
python manage.py test --tag=integration --keepdb=False
```

## Debugging Failed Tests

### Common Failure Patterns

**1. Intermittent failures (flaky tests)**
```bash
# Run test multiple times
pytest -x --count=10 apps/operations/tests/test_views.py::TestOperationView::test_create

# If passes sometimes, fails sometimes = flaky test
# Common causes:
# - Race conditions
# - Timing issues
# - Shared state between tests
```

**Fix:** Add proper setup/teardown, use transactions, fix race conditions

**2. Database state issues**
```python
# Problem: Tests depend on order
# Solution: Proper setUp/tearDown

class MyTest(TestCase):
    def setUp(self):
        # Create fresh data for EACH test
        self.user = User.objects.create(username="test")

    def tearDown(self):
        # Clean up if needed
        pass
```

**3. Mock issues**
```python
# Problem: Mock not applied correctly
# Solution: Check patch path

# Wrong:
@patch('my_module.function')  # Won't work if imported differently

# Correct:
@patch('apps.operations.services.function')  # Patch where it's used
```

### Debugging Commands

```bash
# Run with debugger
pytest --pdb  # Drop into debugger on failure

# Verbose output
pytest -vv

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Re-run only failed tests
pytest --lf

# Show locals on failure
pytest -l
```

### Go Test Debugging

```bash
# Verbose with test output
go test -v ./...

# Show test coverage line-by-line
go test -coverprofile=coverage.out ./...
go tool cover -func=coverage.out

# Run specific failing test
go test -v -run TestMyFailingTest ./package

# With race detector
go test -race ./...

# With debugging prints
go test -v ./... 2>&1 | grep "FAIL"
```

## Test Coverage Analysis

### Checking Coverage

```bash
# Overall project coverage
make coverage

# Component-specific
make coverage-go
make coverage-django
make coverage-frontend

# Generate reports
make coverage-report
```

### Coverage Goals by Component

```
Component              Current    Target    Priority
────────────────────────────────────────────────────
Go Shared              -          >80%      HIGH
Go API Gateway         -          >70%      HIGH
Go Worker              -          >70%      HIGH
Django Operations      -          >70%      HIGH
Django Databases       -          >70%      MEDIUM
Django Templates       -          >70%      MEDIUM
React Components       -          >60%      MEDIUM
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
# Should see coverage increase
```

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  go-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-go@v2
        with:
          go-version: 1.21
      - name: Run Go tests
        run: |
          cd go-services
          go test -v -cover ./...

  django-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Run Django tests
        run: |
          cd orchestrator
          pip install -r requirements.txt
          pytest --cov=apps --cov-fail-under=70

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-node@v2
        with:
          node-version: 18
      - name: Run Frontend tests
        run: |
          cd frontend
          npm install
          npm test -- --coverage --watchAll=false
```

## Performance/Load Tests (Phase 5)

### Load Test Example

```python
# tests/performance/test_load.py
import time
import concurrent.futures
from apps.operations.models import Operation

def test_concurrent_operations(num_operations=100):
    """Test system under load"""

    def create_operation(i):
        operation = Operation.objects.create(
            name=f"Load Test Op {i}",
            operation_type="create_users"
        )
        return operation.id

    start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_operation, i) for i in range(num_operations)]
        results = [f.result() for f in futures]

    elapsed = time.time() - start

    print(f"Created {num_operations} operations in {elapsed:.2f}s")
    print(f"Rate: {num_operations/elapsed:.2f} ops/sec")

    assert len(results) == num_operations
    assert elapsed < 30  # Should complete in 30 seconds
```

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

- Testing strategy: `CLAUDE.md` - Testing Strategy section
- CI/CD config: `.github/workflows/test.yml`
- Test fixtures: `tests/fixtures/`
- Project conventions: `CLAUDE.md`

## Related Skills

После запуска тестов используй:
- `cc1c-service-builder` - для исправления failed tests
- `cc1c-navigator` - для поиска связанного кода при debugging
- `cc1c-devops` - для проверки окружения при integration test failures
- `cc1c-odata-integration` - для отладки OData-related test failures

---

**Version:** 1.0
**Last Updated:** 2025-01-17
**Changelog:**
- 1.0 (2025-01-17): Initial release with multi-language test support
