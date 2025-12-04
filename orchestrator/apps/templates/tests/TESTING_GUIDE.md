# OperationType Registry Testing Guide

## Quick Start

Run all registry tests:
```bash
cd orchestrator
source venv/bin/activate
pytest apps/templates/tests/test_registry.py -v
```

Run all management command tests:
```bash
pytest apps/templates/tests/test_sync_command.py -v
```

Run both with coverage:
```bash
pytest apps/templates/tests/test_registry.py apps/templates/tests/test_sync_command.py \
  --cov=apps.templates.registry \
  --cov=apps.templates.management.commands.sync_operation_templates \
  --cov-report=html
```

## Test Structure

### File Organization

```
apps/templates/tests/
├── test_registry.py              # 50 tests for registry core
├── test_sync_command.py          # 24 tests for management command
├── test_operation_type_validation.py  # Existing validation tests
├── conftest.py                   # Shared fixtures
├── REGISTRY_TESTS_REPORT.md      # Coverage report
└── TESTING_GUIDE.md              # This file
```

## Test Categories

### Registry Tests (test_registry.py)

#### 1. ParameterSchema Tests (6 tests)
Tests for operation parameter definitions:
```python
# Example: Testing parameter creation
def test_required_parameter(self):
    param = ParameterSchema(
        name='database_id',
        type='string',
        required=True,
        description='Database identifier',
    )
    assert param.name == 'database_id'
    assert param.required is True
```

Coverage:
- Required and optional parameters
- Parameter types (string, integer, boolean, uuid, json)
- Default values
- Equality comparison

#### 2. OperationType Tests (7 tests)
Tests for operation type definitions:
```python
# Example: Creating full operation
op = OperationType(
    id='lock_scheduled_jobs',
    name='Lock Scheduled Jobs',
    description='Disable all scheduled jobs',
    backend=BackendType.RAS,
    target_entity=TargetEntity.INFOBASE,
    required_parameters=[
        ParameterSchema('cluster_id', 'string'),
    ],
    is_async=True,
    timeout_seconds=600,
)
```

Coverage:
- Minimal and full operation creation
- Conversion to Django choices
- Template data generation
- Backend and entity type handling

#### 3. Singleton Tests (4 tests)
Tests for thread-safe singleton pattern:
```python
# Example: Singleton verification
def test_singleton_instance(self):
    r1 = OperationTypeRegistry()
    r2 = OperationTypeRegistry()
    assert r1 is r2  # Same instance
```

Coverage:
- Singleton pattern enforcement
- Thread-safe access
- State preservation

#### 4. Registration Tests (6 tests)
Tests for operation registration:
```python
# Example: Registering operations
registry.register(op1)
registry.register(op2)

# Or batch registration
registry.register_many([op1, op2, op3])

# Idempotent - same operation twice is OK
registry.register(op1)
registry.register(op1)  # No error

# Error on backend conflict
# registry.register(op1_ras)  # First
# registry.register(op1_odata)  # Error!
```

Coverage:
- Single and batch registration
- Idempotent behavior
- Conflict detection
- Error handling

#### 5. Retrieval Tests (9 tests)
Tests for getting operations from registry:
```python
# Example: Retrieving operations
op = registry.get('lock_scheduled_jobs')  # By ID
all_ops = registry.get_all()              # All operations
ras_ops = registry.get_by_backend(BackendType.RAS)  # By backend
ids = registry.get_ids()                  # All IDs as set
choices = registry.get_choices()          # Django choices format
```

Coverage:
- Get by ID
- Get all
- Filter by backend
- Get IDs
- Get choices

#### 6. Validation Tests (3 tests)
Tests for operation validation:
```python
# Example: Validation
registry.validate('lock_scheduled_jobs')  # OK
registry.validate('unknown_op')  # Raises ValueError

# Check without raising
if registry.is_valid('op_id'):
    op = registry.get('op_id')
```

Coverage:
- Valid operation checking
- Error raising
- Error message quality

#### 7. Choice Generation Tests (4 tests)
Tests for Django form choices:
```python
# Example: Getting choices
choices = registry.get_choices()
# Returns: [('lock_scheduled_jobs', 'Lock Scheduled Jobs'), ...]
# Always sorted alphabetically
```

Coverage:
- Choice format
- Sorting
- Empty registry

#### 8. Template Sync Tests (5 tests)
Tests for synchronization data format:
```python
# Example: Getting sync data
data = registry.get_for_template_sync()
# Returns list of dicts with:
# {
#     'id': 'tpl-lock-scheduled-jobs',  # Template ID
#     'name': 'Lock Scheduled Jobs',
#     'operation_type': 'lock_scheduled_jobs',
#     'target_entity': 'infobase',
#     'template_data': {...},  # Operation metadata
#     'is_active': True,
# }
```

Coverage:
- Data format verification
- ID conversion
- Template data inclusion

#### 9. Clear Tests (3 tests)
Tests for registry cleanup (testing only):
```python
# Example: Clearing registry
registry.clear()
assert len(registry.get_all()) == 0
```

Coverage:
- Cleanup functionality
- Re-registration after clear

#### 10. Thread Safety Tests (3 tests)
Tests for concurrent access:
```python
# Example: Concurrent singleton access
from threading import Thread
instances = []

def get_instance():
    instances.append(OperationTypeRegistry())

threads = [Thread(target=get_instance) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()

# All instances should be the same
assert all(i is instances[0] for i in instances)
```

Coverage:
- Concurrent access safety
- Thread-safe registration

### Management Command Tests (test_sync_command.py)

#### 1. Basic Functionality Tests (17 tests)
Tests for template creation and updates:
```python
# Example: Creating templates
call_command('sync_operation_templates')
assert OperationTemplate.objects.count() == 5

# Dry-run (no changes)
call_command('sync_operation_templates', '--dry-run')
# Output shows what would happen

# Updating existing
call_command('sync_operation_templates')  # First run
call_command('sync_operation_templates')  # Second run (idempotent)

# Force update unchanged
call_command('sync_operation_templates', '--force')
```

Coverage:
- Template creation
- Correct data assignment
- Dry-run behavior
- Idempotency
- Updates
- Force flag
- Unknown deactivation
- Error handling
- Output verification

#### 2. Edge Cases Tests (5 tests)
Tests for special scenarios:
```python
# Example: ID conversion
# Operation ID: lock_scheduled_jobs
# Template ID: tpl-lock-scheduled-jobs

# Large registry
registry.register_many([...] * 20)
call_command('sync_operation_templates')
assert OperationTemplate.objects.count() == 20

# Parameter changes
# Update registry with new parameters
call_command('sync_operation_templates')
# Templates have new parameters
```

Coverage:
- ID conversion
- All entity types
- Special characters
- Large registries
- Parameter changes

#### 3. Integration Tests (2 tests)
Tests with test setup:
```python
# Example: Integration test
registry.register(OperationType(...))
call_command('sync_operation_templates')
assert OperationTemplate.objects.filter(
    operation_type='test_op'
).exists()
```

## Common Test Patterns

### Pattern 1: Testing Registry Directly
```python
def test_operation_registration(self):
    registry = get_registry()

    op = OperationType(
        id='test_op',
        name='Test',
        description='',
        backend=BackendType.RAS,
        target_entity=TargetEntity.INFOBASE,
    )

    registry.register(op)

    assert registry.is_valid('test_op')
    assert registry.get('test_op') == op
```

### Pattern 2: Testing with Fixtures
```python
@pytest.fixture(autouse=True)
def setup_operations(self):
    registry = get_registry()
    registry.clear()

    # Setup operations
    registry.register(OperationType(...))

    yield

    registry.clear()

def test_with_setup(self):
    # Operations are already registered
    registry = get_registry()
    assert len(registry.get_all()) > 0
```

### Pattern 3: Testing Management Command
```python
@pytest.mark.django_db
def test_command(self):
    out = StringIO()
    call_command('sync_operation_templates', stdout=out)

    output = out.getvalue()
    assert 'Created:' in output
    assert OperationTemplate.objects.count() > 0
```

### Pattern 4: Testing with Assertions
```python
def test_with_multiple_assertions(self):
    op = OperationType(...)

    # Behavior test
    data = op.to_template_data()

    assert 'backend' in data
    assert data['backend'] == 'ras'
    assert data['is_async'] is False
```

## Fixture Usage

### Registry Cleanup Fixture
All tests have automatic cleanup:
```python
@pytest.fixture(autouse=True)
def clean_registry(self):
    registry = get_registry()
    registry.clear()
    yield
    registry.clear()
```

This ensures:
- Registry is empty before test
- Registry is cleaned after test
- Tests don't interfere with each other

### Database Fixture
Command tests use Django DB:
```python
@pytest.mark.django_db
class TestCommand:
    # Automatic database setup/teardown
    def test_creates_template(self):
        call_command('sync_operation_templates')
```

## Debugging Tests

### Run Single Test
```bash
pytest apps/templates/tests/test_registry.py::TestOperationType::test_minimal_operation_type -v
```

### Run Test Class
```bash
pytest apps/templates/tests/test_registry.py::TestOperationType -v
```

### Run with Print Output
```bash
pytest apps/templates/tests/test_registry.py -v -s
```

### Run with Extra Verbosity
```bash
pytest apps/templates/tests/test_registry.py -vv
```

### Run with Traceback
```bash
pytest apps/templates/tests/test_registry.py --tb=long
```

## Coverage Analysis

### Generate HTML Coverage Report
```bash
pytest apps/templates/tests/test_registry.py \
  --cov=apps.templates.registry \
  --cov-report=html
# Open htmlcov/index.html in browser
```

### Check Specific Module Coverage
```bash
pytest apps/templates/tests/test_sync_command.py \
  --cov=apps.templates.management.commands.sync_operation_templates \
  --cov-report=term-missing
```

### Current Coverage: 95%
- registry/__init__.py: 100%
- registry/types.py: 100%
- registry/registry.py: 100%
- sync_operation_templates.py: 89%

## Best Practices

### When Writing Tests
1. Use descriptive test names that explain intent
2. One assertion per test when possible
3. Use fixtures for setup/teardown
4. Clear registry before and after tests
5. Test both success and failure paths
6. Include docstrings explaining what and why

### When Running Tests
1. Always run full test suite before committing
2. Check coverage for new code (>80%)
3. Fix flaky tests immediately
4. Document test failures and reasons
5. Keep tests fast (<2 seconds total)

### When Debugging Failures
1. Run single failing test with `-s` flag
2. Add print statements for debugging
3. Check test isolation (clean fixtures)
4. Verify test assumptions
5. Check for timing-dependent code

## Integration with CI/CD

These tests should be run in CI/CD pipeline:
```bash
# Full test suite
pytest apps/templates/tests/test_registry.py \
        apps/templates/tests/test_sync_command.py \
        --cov=apps.templates \
        --cov-report=xml
```

## Related Documentation

- [Registry Implementation](../registry/registry.py)
- [Type Definitions](../registry/types.py)
- [Management Command](../management/commands/sync_operation_templates.py)
- [Model Definition](../models.py)
- [Test Report](./REGISTRY_TESTS_REPORT.md)

## FAQ

**Q: How do I run tests in CI?**
A: Use `pytest` with coverage reporting. See CI configuration in project root.

**Q: Why do tests clear the registry?**
A: To ensure test isolation. Each test starts with clean state.

**Q: Can I run individual test files?**
A: Yes, run `pytest path/to/test_file.py -v`

**Q: How do I add new tests?**
A: Add test class/method to appropriate file following existing patterns.

**Q: What if tests fail?**
A: Check test output, use `-v` and `-s` flags, verify registry state.

---

**Total Tests:** 74
**Coverage:** 95%
**Status:** Production Ready
