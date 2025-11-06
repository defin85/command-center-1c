# Test Debugging Reference

Продвинутые техники отладки падающих тестов в CommandCenter1C.

## Common Failure Patterns

### 1. Intermittent Failures (Flaky Tests)

**Симптомы:**
- Тест иногда проходит, иногда падает
- Разное поведение при запуске несколько раз

**Диагностика:**
```bash
# Run test multiple times (pytest)
pytest -x --count=10 apps/operations/tests/test_views.py::TestOperationView::test_create

# Go tests
for i in {1..10}; do go test -run TestMyTest ./package || break; done
```

**Общие причины:**
- Race conditions
- Timing issues
- Shared state between tests
- External dependencies (network, time)

**Решение:**
```python
# Bad: Timing dependent
time.sleep(1)  # Assumes 1 second is enough

# Good: Wait for condition
def wait_for_condition(condition, timeout=5):
    start = time.time()
    while not condition():
        if time.time() - start > timeout:
            raise TimeoutError("Condition not met")
        time.sleep(0.1)

wait_for_condition(lambda: operation.status == "completed")
```

### 2. Database State Issues

**Симптомы:**
- Tests fail when run together, pass individually
- "IntegrityError: duplicate key value"

**Диагностика:**
```bash
# Run tests in isolation
pytest apps/operations/tests/test_models.py::TestA  # passes
pytest apps/operations/tests/test_models.py::TestB  # passes
pytest apps/operations/tests/test_models.py  # fails!
```

**Решение:**
```python
# Use proper setUp/tearDown
class MyTest(TestCase):
    def setUp(self):
        # Create fresh data for EACH test
        self.user = User.objects.create(username="test")

    def tearDown(self):
        # Clean up if needed (usually automatic with transactions)
        pass

# Or use pytest fixtures with autouse
@pytest.fixture(autouse=True)
def clean_db():
    yield
    # Cleanup after test
    MyModel.objects.all().delete()
```

### 3. Mock Issues

**Симптомы:**
- Mock не применяется
- "AttributeError: Mock object has no attribute X"

**Диагностика:**
```python
# Check mock was called
mock.assert_called()
mock.assert_called_once()
mock.assert_called_with(expected_args)

# Print mock calls
print(mock.call_args_list)
```

**Решение:**
```python
# Problem: Patching wrong path
# Wrong: patch module where function is defined
@patch('my_module.function')  # May not work

# Correct: patch where function is used
@patch('apps.operations.services.function')

# Problem: Mock not configured
mock_client.process.return_value = None  # Returns None!

# Correct: Configure return value
mock_client.process.return_value = {'status': 'success'}
```

### 4. Async/Promise Issues

**Симптомы:**
- React tests fail with "act" warning
- "Warning: An update to X inside a test was not wrapped in act(...)"

**Решение:**
```typescript
// Bad: Not waiting for async updates
const { result } = renderHook(() => useMyHook());
result.current.fetchData();
expect(result.current.data).toBeTruthy(); // Fails!

// Good: Wrap in act() and wait
const { result } = renderHook(() => useMyHook());
await act(async () => {
  await result.current.fetchData();
});
expect(result.current.data).toBeTruthy(); // Passes
```

## Debugging Commands

### pytest

```bash
# Drop into debugger on failure
pytest --pdb

# Drop into debugger on first failure
pytest -x --pdb

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

# Specific test with all output
pytest -vv -s apps/operations/tests/test_views.py::TestOperation::test_create
```

### Go Tests

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

# With debugging prints (use t.Logf in tests)
go test -v ./... 2>&1 | grep "FAIL"

# Stop on first failure
go test -failfast ./...
```

### npm/Jest

```bash
# Run with verbose output
npm test -- --verbose

# Run specific test
npm test -- OperationForm.test.tsx

# Watch mode for debugging
npm test -- --watch

# Show full error details
npm test -- --no-coverage --maxWorkers=1
```

## Debugging Strategies

### 1. Isolate the Problem

```bash
# Run just one test
pytest apps/operations/tests/test_views.py::TestOperation::test_create

# Disable other tests temporarily
@pytest.mark.skip("Debugging other test")
def test_something():
    pass
```

### 2. Add Logging

```python
# Django/Python
import logging
logger = logging.getLogger(__name__)

def test_my_function():
    logger.debug(f"Operation status: {operation.status}")
    logger.debug(f"Expected: completed, Got: {operation.status}")
    assert operation.status == "completed"
```

```go
// Go
func TestMyFunction(t *testing.T) {
    t.Logf("Operation status: %s", operation.Status)
    t.Logf("Expected: completed, Got: %s", operation.Status)
    assert.Equal(t, "completed", operation.Status)
}
```

### 3. Use Debugger

```python
# pytest with pdb
pytest --pdb apps/operations/tests/test_views.py

# In test file
def test_my_function():
    import pdb; pdb.set_trace()  # Breakpoint
    # Test code
```

### 4. Check Test Dependencies

```bash
# List test dependencies
pip list | grep test
npm list --depth=0 | grep test

# Update testing libraries
pip install --upgrade pytest pytest-django pytest-cov
npm update @testing-library/react @testing-library/jest-dom
```

### 5. Compare Working vs Failing

```bash
# Run test that works
pytest apps/operations/tests/test_models.py::TestOperationModel::test_create -v

# Run test that fails
pytest apps/operations/tests/test_models.py::TestOperationModel::test_update -v

# Compare outputs
# Look for differences in setup, mocks, assertions
```

## Performance Debugging

### Slow Tests

```bash
# Django: find slow tests
python manage.py test --timing

# pytest with duration report
pytest --durations=10

# Go: benchmark tests
go test -bench=. ./... -benchmem
```

## Integration Test Debugging

### Database Issues

```bash
# Keep test database for inspection
python manage.py test --keepdb

# Connect to test database
docker exec -it postgres psql -U commandcenter -d test_commandcenter

# Check database state
SELECT * FROM operations WHERE status = 'pending';
```

### Network Issues

```bash
# Check services are running
./scripts/dev/health-check.sh

# Check ports
netstat -ano | findstr :8080  # API Gateway
netstat -ano | findstr :8000  # Orchestrator
```

## Common Error Messages

### "AssertionError: X != Y"
- Check expected vs actual values
- Verify test data setup
- Check for timezone issues (datetime)

### "AttributeError: Mock object has no attribute"
- Configure mock return values
- Check mock is being used (assert_called)

### "IntegrityError: duplicate key"
- Clean database between tests
- Use unique values in test data

### "Timeout" errors
- Increase timeout values
- Check for deadlocks
- Verify async operations complete
